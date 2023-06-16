import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError
from sagemaker.estimator import Estimator
from sagemaker.inputs import FileSystemInput, TrainingInput
from sagemaker.processing import NetworkConfig, ProcessingInput, ProcessingOutput
from sagemaker.workflow.entities import PipelineVariable
from sagemaker.workflow.parameters import Parameter
from sagemaker.workflow.pipeline import Pipeline

from sagemaker_rightline.model import Rule, Validation, ValidationResult
from sagemaker_rightline.rules import Equals


class PipelineParametersAsExpected(Validation):
    """Validate Pipeline Parameters.

    This validation will check if the parameters in the pipeline are as
    expected.
    """

    def __init__(
        self, parameters_expected: List[Parameter], rule: Rule, ignore_default_value: bool = False
    ) -> None:
        """Validate Pipeline Parameters."""
        super().__init__(name="PipelineParametersAsExpected", paths=[".parameters[]"], rule=rule)
        if not parameters_expected:
            raise ValueError("parameters_expected cannot be empty.")
        self.parameters_expected: List[Parameter] = parameters_expected
        self.ignore_default_value: bool = ignore_default_value

    def run(self, sagemaker_pipeline: Pipeline) -> ValidationResult:
        """Runs validation of Parameters on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: Dict containing ValidationResult
        :rtype: ValidationResult
        """
        parameters_observed = Validation.get_attribute(sagemaker_pipeline, self.paths)
        if self.ignore_default_value:
            for ix, parameter in enumerate(parameters_observed):
                parameters_observed[ix].default_value = None
        result = self.rule.run(parameters_observed, self.parameters_expected, self.name)
        return result


class StepKmsKeyIdAsExpected(Validation):
    """Validate KmsKeyId or output_kms_key in Step.

    Supported only for ProcessingStep and TrainingStep (output_kms_key).
    This validation is useful when you want to ensure that the KmsKeyId
    or output_kms_key of a Pipeline Step is as expected.
    """

    def __init__(
        self, kms_key_id_expected: str, rule: Rule, step_name: Optional[str] = None
    ) -> None:
        """Initialize StepKmsKeyIdAsExpected validation."""
        self.step_filter: str = f"name=={step_name}" if step_name else ""
        super().__init__(
            name="StepKmsKeyIdAsExpected",
            paths=[
                f".steps[{self.step_filter} && step_type/value==Processing].kms_key",
                f".steps[{self.step_filter} && step_type/value==Training].estimator.output_kms_key",
            ],
            rule=rule,
        )
        self.kms_key_id_expected: str = kms_key_id_expected

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of Parameters on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """
        kms_keys_observed = Validation.get_attribute(sagemaker_pipeline, self.paths)
        result = self.rule.run(kms_keys_observed, [self.kms_key_id_expected], self.name)
        return result


@dataclass
class ContainerImage:
    """Container Image dataclass."""

    uri: str

    def __post_init__(self) -> None:
        """Decompose ImageUri into its components."""
        self.account_id = self.uri.split(".")[0]
        self.repository = re.search("/(.*):", self.uri).group(1)
        self.region = self.uri.split(".")[3]
        self.tag = self.uri.split(":")[1]


class StepImagesExist(Validation):
    """Check if container images exist in ECR.

    Supported only for ProcessingStep and TrainingStep.
    """

    def __init__(
        self,
        boto3_client: Union["boto3.client('ecr')", str] = "ecr",  # noqa F821
        step_name: Optional[str] = None,
    ) -> None:
        """Initialize ImageExists validation.

        :param boto3_client: boto3 client to use, defaults to "ecr"
        :type boto3_client: Union["boto3.client('ecr')", str], optional
        :param step_name: Step name to filter on, defaults to None
        :type step_name: Optional[str], optional
        :return: None
        :rtype: None
        """
        self.step_filter: str = f"name=={step_name}" if step_name else ""
        super().__init__(
            name="StepImagesExist",
            paths=[
                f".steps[{self.step_filter} && step_type/value==Processing].processor.image_uri",
                f".steps[{self.step_filter} && step_type/value==Training].estimator.image_uri",
            ],
        )
        if isinstance(boto3_client, str) and boto3_client != "ecr":
            raise ValueError(f"boto3_client must be 'ecr', not {boto3_client}.")
        if boto3_client:
            self.client = (
                boto3_client if not isinstance(boto3_client, str) else boto3.client(boto3_client)
            )

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of whether Image URIs referenced in Pipeline Steps
        exist in ECR.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """
        paginator = self.client.get_paginator("describe_images")

        uris = Validation.get_attribute(sagemaker_pipeline, self.paths)
        # return uris
        not_exist = []
        exist = []
        for uri in uris:
            container_image = ContainerImage(uri=uri)
            try:
                _ = list(
                    paginator.paginate(
                        repositoryName=container_image.repository,
                        registryId=container_image.account_id,
                        imageIds=[{"imageTag": container_image.tag}],
                    )
                )
                exist.append(uri)
            except ClientError:
                not_exist.append(uri)
        if not_exist:
            return ValidationResult(
                validation_name=self.name,
                success=False,
                negative=False,
                message=f"Images {not_exist} do not exist.",
                subject=str(not_exist),
            )
        return ValidationResult(
            validation_name=self.name,
            success=True,
            negative=False,
            message=f"Images {exist} exist.",
            subject=str(exist),
        )


class StepNetworkConfigAsExpected(Validation):
    """Validate NetworkConfig in Step.

    This Validation currently supports only ProcessingStep. This
    validation is useful when you want to ensure that the NetworkConfig
    of a Pipeline Step's Processor is as expected.
    """

    def __init__(
        self, network_config_expected: NetworkConfig, rule: Rule, step_name: Optional[str] = None
    ) -> None:
        """Initialize StepNetworkConfigAsExpected validation.

        :param network_config_expected: Expected NetworkConfig
        :type network_config_expected: NetworkConfig
        :param rule: Rule to apply
        :type rule: Rule
        :param step_name: Name of Step to validate, defaults to None
        :type step_name: Optional[str], optional
        :return: None
        :rtype: None
        """
        self.step_filter: str = f"name=={step_name}" if step_name else ""
        super().__init__(
            name="StepNetworkConfigAsExpected",
            paths=[
                f".steps[{self.step_filter}].processor.network_config",
            ],
            rule=rule,
        )
        self.network_config_expected: NetworkConfig = network_config_expected

    @staticmethod
    def get_training_step_network_config(
        training_step_estimators: List[Estimator],
    ) -> List[NetworkConfig]:
        """Get NetworkConfig of each training step estimator.

        :param training_step_estimators: List of training step estimators
        :type training_step_estimators: List[Estimator]
        :return: List of NetworkConfig of each training step estimator
        :rtype: List[NetworkConfig]
        """
        default_network_config = NetworkConfig()
        training_step_network_configs = []
        for step in training_step_estimators:
            step_dict = {}
            for attr_name in default_network_config.__dict__.keys():
                attr_value = getattr(step, attr_name)
                # Some attributes of NetworkConfig are callable and return the value,
                # so we need to call them
                step_dict[attr_name] = (
                    attr_value
                    if any([isinstance(attr_value, bool), isinstance(attr_value, list)])
                    else attr_value()
                )
            training_step_network_configs.append(NetworkConfig(**step_dict))
        return training_step_network_configs

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of NetworkConfigs on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """
        network_configs_observed = Validation.get_attribute(sagemaker_pipeline, self.paths)

        # Compatibility with TrainingStep, which does not have a NetworkConfig object
        # as attribute, but takes the attributes of NetworkConfig as individual arguments.
        training_step_estimators = [
            step.estimator
            for step in sagemaker_pipeline.steps
            if step.step_type.value == "Training"
            and step.name == self.step_filter.replace("name==", "")
        ]
        if training_step_estimators:
            network_configs_observed += (
                StepNetworkConfigAsExpected.get_training_step_network_config(
                    training_step_estimators
                )
            )

        network_configs_observed_dict = []
        for nwc in network_configs_observed:
            if nwc:
                network_configs_observed_dict.append(nwc.__dict__)
            else:
                network_configs_observed_dict.append(None)
        network_config_expected_dict = (
            self.network_config_expected.__dict__
            if self.network_config_expected
            else self.network_config_expected
        )
        result = self.rule.run(
            network_configs_observed_dict, [network_config_expected_dict], self.name
        )
        return result


class StepLambdaFunctionExists(Validation):
    """Validate whether Lambda Function referenced in LambdaSteps exists."""

    def __init__(
        self,
        boto3_client: Union["boto3.client('lambda')", str] = "lambda",  # noqa F821
    ) -> None:
        """Initialize StepLambdaFunctionArnExists validation.

        :param boto3_client: Boto3 client to use for checking Lambda Function existence,
        defaults to "lambda"
        :type boto3_client: Union["boto3.client('lambda')", str], optional
        :raises ValueError: boto3_client must be 'lambda'
        :return: None
        :rtype: None
        """
        if isinstance(boto3_client, str) and boto3_client != "lambda":
            raise ValueError(f"boto3_client must be 'lambda', not {boto3_client}.")
        if boto3_client:
            self.client = (
                boto3_client if not isinstance(boto3_client, str) else boto3.client(boto3_client)
            )

        super().__init__(
            name="StepLambdaFunctionExists",
            paths=[
                ".steps[step_type/value==Lambda].lambda_func",
            ],
        )

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of Parameters on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """
        lambda_func_observed = Validation.get_attribute(sagemaker_pipeline, self.paths)
        exist = []
        not_exist = []
        for func in lambda_func_observed:
            try:
                _ = self.client.get_function(
                    FunctionName=func,
                )
                exist.append(func)
            except ClientError:
                not_exist.append(func)
        if not_exist:
            return ValidationResult(
                success=False,
                negative=False,
                message=f"Lambda Function {not_exist} does not " f"exist.",
                subject=str(lambda_func_observed),
                validation_name=self.name,
            )
        else:
            return ValidationResult(
                success=True,
                negative=False,
                message=f"Lambda Function {exist} exists.",
                subject=str(lambda_func_observed),
                validation_name=self.name,
            )


class StepRoleNameAsExpected(Validation):
    """Validate Role of Pipeline Step.

    Supported only for ProcessingStep and TrainingStep. This validation
    is useful when you want to ensure that the Role of a Pipeline Step
    is as expected.
    """

    def __init__(
        self,
        role_name_expected: str,
        rule: Rule,
        step_name: Optional[str] = None,
    ) -> None:
        """Initialize StepRole validation.

        :param role_name_expected: Expected Role name
        :type role_name_expected: str
        :param rule: Rule to use for validation
        :type rule: Rule
        :param step_name: Name of Step to validate, defaults to None
        :type step_name: Optional[str], optional
        :return: None
        :rtype: None
        """
        self.step_filter: str = f"name=={step_name}" if step_name else ""

        super().__init__(
            name="StepRole",
            paths=[
                f".steps[{self.step_filter} && step_type/value==Processing].processor.role",
                f".steps[{self.step_filter} && step_type/value==Training].estimator.role",
            ],
            rule=rule,
        )
        self.role_name_expected: str = role_name_expected

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of Parameters on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """
        role_arns_observed = Validation.get_attribute(sagemaker_pipeline, self.paths)
        role_name_observed = [role_arn.split("/")[-1] for role_arn in role_arns_observed]
        result = self.rule.run(role_name_observed, [self.role_name_expected], self.name)
        return result


class StepRoleNameExists(Validation):
    """Validate existence of Role of Pipeline Step.

    Supported only for ProcessingStep and TrainingStep. This validation
    is useful when you want to ensure that Roles of Pipeline Steps
    exist.
    """

    def __init__(
        self,
        step_name: Optional[str] = None,
        boto3_client: Union["boto3.client('iam')", str] = "iam",  # noqa F821
    ) -> None:
        """Initialize StepRole validation.

        :param step_name: Name of Step to validate, defaults to None
        :type step_name: Optional[str], optional
        :param boto3_client: Boto3 client to use for checking Role existence, defaults to "iam"
        :type boto3_client: Union["boto3.client('iam')", str], optional
        :return: None
        :rtype: None
        """
        self.step_filter: str = f"name=={step_name}" if step_name else ""
        if isinstance(boto3_client, str) and boto3_client != "iam":
            raise ValueError(f"boto3_client must be 'iam', not {boto3_client}.")
        if boto3_client:
            self.client = (
                boto3_client if not isinstance(boto3_client, str) else boto3.client(boto3_client)
            )

        super().__init__(
            name="StepRoleExists",
            paths=[
                f".steps[{self.step_filter} && step_type/value==Processing].processor.role",
                f".steps[{self.step_filter} && step_type/value==Training].estimator.role",
            ],
        )

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of Parameters on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """
        role_arns_observed = Validation.get_attribute(sagemaker_pipeline, self.paths)
        role_name_observed = [role_arn.split("/")[-1] for role_arn in role_arns_observed]

        exist = []
        not_exist = []
        for role_name in role_name_observed:
            try:
                _ = self.client.get_role(
                    RoleName=role_name,
                )
                exist.append(role_name)
            except ClientError:
                not_exist.append(role_name)
        if not_exist:
            return ValidationResult(
                success=False,
                negative=False,
                message=f"Role {not_exist} does not exist.",
                subject=str(role_name_observed),
                validation_name=self.name,
            )
        else:
            return ValidationResult(
                success=True,
                negative=False,
                message=f"Role {exist} exists.",
                subject=str(role_name_observed),
                validation_name=self.name,
            )


class StepTagsAsExpected(Validation):
    """Validate Tags of Pipeline Step.

    Supported only for ProcessingStep and TrainingStep. This validation
    is useful when you want to ensure that the Tags of a Pipeline Step
    are as expected.
    """

    def __init__(
        self,
        tags_expected: List[Dict[str, Union[str, PipelineVariable]]],
        rule: Rule,
        step_name: Optional[str] = None,
    ) -> None:
        """Initialize StepTagsAsExpected validation.

        :param tags_expected: Expected Tags
        :type tags_expected: List[Dict[str, Union[str, PipelineVariable]]]
        :param rule: Rule to use for validation
        :type rule: Rule
        :param step_name: Name of Step to validate, defaults to None
        :type step_name: Optional[str], optional
        :return: None
        :rtype: None
        """
        self.step_filter: str = f"name=={step_name}" if step_name else ""

        super().__init__(
            name="StepTagsAsExpected",
            paths=[
                f".steps[{self.step_filter} && step_type/value==Processing].processor.tags",
                f".steps[{self.step_filter} && step_type/value==Training].estimator.tags",
            ],
            rule=rule,
        )
        self.tags_expected: List[Dict[str, Union[str, PipelineVariable]]] = tags_expected

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of Parameters on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """
        tags_observed = Validation.get_attribute(sagemaker_pipeline, self.paths)
        result = self.rule.run(tags_observed[0], self.tags_expected, self.name)
        return result


class StepInputsAsExpected(Validation):
    """Validate Inputs of Pipeline Step.

    Supported only for ProcessingStep and TrainingStep. This validation
    is useful when you want to ensure that the Inputs of a Pipeline Step
    are as expected.
    """

    def __init__(
        self,
        inputs_expected: List[
            Union[Dict[str, Union[str, TrainingInput, FileSystemInput]], ProcessingInput]
        ],
        rule: Rule,
        step_type: Optional[Union["Training", "Processing"]] = None,  # noqa F821
        step_name: Optional[str] = None,
    ) -> None:
        """Initialize StepTagsAsExpected validation.

        :param inputs_expected: Expected Inputs
        :type inputs_expected: List[Dict[str, Union[str, TrainingInput, ProcessingInput,
        FileSystemInput]]]
        :param rule: Rule to use for validation
        :type rule: Rule
        :param step_type: Type of Step to validate
        :type step_type: Union["Training", "Processing"]
        :param step_name: Name of Step to validate, defaults to None
        :type step_name: Optional[str], optional
        :return: None
        :rtype: None
        """
        if step_type and step_name:
            raise ValueError("step_type and step_name cannot be specified together.")
        if not step_type and not step_name:
            raise ValueError("Either step_type or step_name must be specified.")
        if step_type not in ("Training", "Processing") and not step_name:
            raise ValueError(f"step_type must be 'Training' or 'Processing', not {step_type}.")

        self.step_filter: str = f"name=={step_name}" if step_name else ""
        self.step_type_filter: str = f"step_type/value=={step_type}" if step_type else ""

        super().__init__(
            name="StepInputsAsExpected",
            paths=[
                f".steps[{self.step_filter} && {self.step_type_filter}].inputs",
            ],
            rule=rule,
        )
        self.inputs_expected: List[
            Dict[str, Union[str, TrainingInput, ProcessingInput, FileSystemInput]]
        ] = inputs_expected

    @staticmethod
    def format_training_inputs(
        inputs: List[Dict[str, Union[str, TrainingInput, FileSystemInput]]]
    ) -> List[Dict[str, Union[dict, str]]]:
        """Format Training Inputs.

        :param inputs: Training Inputs
        :type inputs: List[Dict[str, Union[str, TrainingInput, FileSystemInput]]]
        :return: Formatted Training Inputs
        :rtype: List[Dict[str, Union[dict, str]]]
        """
        formatted_inputs = []
        for item in inputs:
            for key, value in item.items():
                formatted_inputs.append(
                    {
                        key: value.__dict__
                        if isinstance(value, TrainingInput) or isinstance(value, FileSystemInput)
                        else value
                    }
                )
        return formatted_inputs

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of Step Inputs on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """
        if self.step_filter:
            step_type = Validation.get_attribute(
                sagemaker_pipeline, [f".steps[{self.step_filter}].step_type.value"]
            )[0]
            self.step_type_filter = f"step_type/value=={step_type}"

        inputs_observed = Validation.get_attribute(sagemaker_pipeline, self.paths)

        if self.step_type_filter == "step_type/value==Processing":
            # ProcessingStep has a list of ProcessingInput
            inputs_observed_formatted = [x.__dict__ for y in inputs_observed for x in y]
            inputs_expected_formatted = [x.__dict__ for x in self.inputs_expected]
        elif self.step_type_filter == "step_type/value==Training":
            # TrainingStep has a dict with values potentially being TrainingInput or FileSystemInput
            inputs_observed_formatted = StepInputsAsExpected.format_training_inputs(inputs_observed)
            inputs_expected_formatted = StepInputsAsExpected.format_training_inputs(
                self.inputs_expected
            )
        result = self.rule.run(inputs_observed_formatted, inputs_expected_formatted, self.name)
        return result


class StepOutputsAsExpected(Validation):
    """Validate Outputs of Pipeline Step.

    Supported only for ProcessingStep. This validation is useful when
    you want to ensure that the Outputs of a Pipeline Step are as
    expected.
    """

    def __init__(
        self,
        outputs_expected: List[ProcessingOutput],
        rule: Rule,
        step_name: Optional[str] = None,
    ) -> None:
        """Initialize StepTagsAsExpected validation.

        :param outputs_expected: Expected Inputs
        :type outputs_expected: List[ProcessingOutput]
        :param rule: Rule to use for validation
        :type rule: Rule
        :param step_name: Name of Step to validate, defaults to None
        :type step_name: Optional[str], optional
        :return: None
        :rtype: None
        """

        self.step_filter: str = f"name=={step_name}" if step_name else ""

        super().__init__(
            name="StepOutputsAsExpected",
            paths=[
                f".steps[{self.step_filter} && step_type/value==Processing]].outputs",
            ],
            rule=rule,
        )
        self.outputs_expected: List[ProcessingOutput] = outputs_expected

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of StepOutputs on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """

        outputs_observed = Validation.get_attribute(sagemaker_pipeline, self.paths)
        outputs_observed_formatted = [x.__dict__ for y in outputs_observed for x in y]
        outputs_expected_formatted = [x.__dict__ for x in self.outputs_expected]
        result = self.rule.run(outputs_observed_formatted, outputs_expected_formatted, self.name)
        return result


class StepOutputsMatchInputsAsExpected(Validation):
    """Validate Outputs <> Inputs of Pipeline Step."""

    def __init__(self, inputs_outputs_expected: List[Dict[str, Dict[str, str]]]) -> None:
        """Initialize StepTagsAsExpected validation.

        :param inputs_outputs_expected: Expected Input and Output per step name
        :type inputs_outputs_expected: Dict[str, Dict[str, str]]
        :return: None
        :rtype: None
        """
        name = "StepOutputsMatchInputsAsExpected"
        super().__init__(
            name=name,
            rule=Equals(),
        )
        self.inputs_outputs_expected: List[Dict[str, Dict[str, str]]] = inputs_outputs_expected

    @staticmethod
    def get_step_by_name(
        sagemaker_pipeline: Pipeline, step_name: str
    ) -> "ProcessingStep":  # noqa F821
        """Get ProcessingStep by name.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :param step_name: Name of Step
        :type step_name: str
        :return: ProcessingStep
        :rtype: ProcessingStep
        """
        for step in sagemaker_pipeline.steps:
            if step.name == step_name:
                return step
        raise ValueError(f"Step {step_name} not found in Pipeline")

    @staticmethod
    def get_input_output_by_name(
        step: "ProcessingStep", name: str, kind: str  # noqa F821
    ) -> Union["ProcessingInput", "ProcessingOutput"]:
        """Get ProcessingInput or ProcessingOutput by name.

        :param step: ProcessingStep
        :type step: ProcessingStep
        :param name: Name of Input or Output
        :type name: str
        :return: ProcessingInput or ProcessingOutput
        :rtype: Union[ProcessingInput, ProcessingOutput]
        """
        if kind == "input":
            for input in step.inputs:
                if input.input_name == name:
                    return input
        elif kind == "output":
            for output in step.outputs:
                if output.output_name == name:
                    return output
        else:
            raise ValueError(f"Kind {kind} not supported. Must be one of 'input' or 'output'.")

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Runs validation of Step Inputs on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: validation result
        :rtype: ValidationResult
        """

        input_kw = "input"
        output_kw = "output"

        results = []
        for pair in self.inputs_outputs_expected:
            input_step_name = pair[input_kw]["step_name"]
            input_name = pair[input_kw]["input_name"]
            output_step_name = pair[output_kw]["step_name"]
            output_name = pair[output_kw]["output_name"]

            input_step = StepOutputsMatchInputsAsExpected.get_step_by_name(
                sagemaker_pipeline, input_step_name
            )
            output_step = StepOutputsMatchInputsAsExpected.get_step_by_name(
                sagemaker_pipeline, output_step_name
            )

            input = StepOutputsMatchInputsAsExpected.get_input_output_by_name(
                input_step, input_name, input_kw
            )
            output = StepOutputsMatchInputsAsExpected.get_input_output_by_name(
                output_step, output_name, output_kw
            )
            results.append((input.source, output.destination))
        return self.rule.run(
            observed=[x[0] for x in results],
            expected=[x[1] for x in results],
            validation_name=self.name,
        )

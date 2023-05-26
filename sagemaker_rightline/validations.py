import re
from dataclasses import dataclass
from inspect import isfunction
from typing import Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError
from sagemaker.processing import NetworkConfig
from sagemaker.workflow.parameters import Parameter
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import TrainingStep

from sagemaker_rightline.model import Rule, Validation, ValidationResult


class PipelineParameters(Validation):
    """Validate Pipeline Parameters.

    This validation will check if the parameters in the pipeline are as
    expected.
    """

    def __init__(
        self, parameters_expected: List[Parameter], rule: Rule, ignore_default_value: bool = False
    ) -> None:
        """Validate Pipeline Parameters."""
        super().__init__(name="PipelineParameters", paths=[".parameters[]"], rule=rule)
        if not parameters_expected:
            raise ValueError("parameters_expected cannot be empty.")
        self.parameters_expected: List[Parameter] = parameters_expected
        self.ignore_default_value: bool = ignore_default_value

    def run(self, sagemaker_pipeline: Pipeline) -> Dict[str, ValidationResult]:
        """Runs validation of Parameters on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: Dict containing ValidationResult
        :rtype: Dict[str, ValidationResult]
        """
        parameters_observed = self.get_attribute(sagemaker_pipeline)
        if self.ignore_default_value:
            for ix, parameter in enumerate(parameters_observed):
                parameters_observed[ix].default_value = None
        result = self.rule.run(parameters_observed, self.parameters_expected)
        return {self.name: result}


class StepKmsKeyId(Validation):
    """Validate KmsKeyId or output_kms_key in Step.

    Supported only for ProcessingStep and TrainingStep (output_kms_key).
    This validation is useful when you want to ensure that the KmsKeyId
    or output_kms_key of a Pipeline Step is as expected.
    """

    def __init__(
        self, kms_key_id_expected: str, rule: Rule, step_name: Optional[str] = None
    ) -> None:
        """Initialize StepKmsKeyId validation."""
        self.step_filter: str = f"name=={step_name}" if step_name else ""
        super().__init__(
            name="StepKmsKeyId",
            paths=[
                f".steps[{self.step_filter}].kms_key",
                f".steps[{self.step_filter}].estimator.output_kms_key",
            ],
            rule=rule,
        )
        self.kms_key_id_expected: str = kms_key_id_expected

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> Dict[str, ValidationResult]:
        """Runs validation of Parameters on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: Dict containing the validation result
        :rtype: Dict[str, ValidationResult]
        """
        kms_keys_observed = self.get_attribute(sagemaker_pipeline)
        results = self.rule.run(kms_keys_observed, [self.kms_key_id_expected])
        return {self.name: results}


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


class StepImagesExistOnEcr(Validation):
    """Check if container images exist in ECR.

    Supported only for ProcessingStep and TrainingStep.
    """

    def __init__(
        self,
        boto3_client: Union["boto3.client('ecr')", str] = "ecr",  # noqa: F821
    ) -> None:
        """Initialize ImageExists validation."""
        super().__init__(
            name="StepImagesExistOnEcr",
            paths=[
                ".steps[].processor.image_uri",
                ".steps[].estimator.image_uri",
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
    ) -> Dict[str, ValidationResult]:
        """Runs validation of whether Image URIs referenced in Pipeline Steps
        exist in ECR.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: Dict containing the validation result
        :rtype: Dict[str, ValidationResult]
        """
        paginator = self.client.get_paginator("describe_images")

        uris = self.get_attribute(sagemaker_pipeline)
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
            return {
                self.name: ValidationResult(
                    success=False,
                    message=f"Images {not_exist} do not exist.",
                    subject=str(not_exist),
                )
            }
        return {
            self.name: ValidationResult(
                success=True,
                message=f"Images {exist} exist.",
                subject=str(exist),
            )
        }


class StepNetworkConfig(Validation):
    """Validate NetworkConfig in Step.

    Supported for ProcessingStep, TrainingStep. This validation is
    useful when you want to ensure that the NetworkConfig of a Pipeline
    Step's Processor is as expected.
    """

    def __init__(
        self, network_config_expected: NetworkConfig, rule: Rule, step_name: Optional[str] = None
    ) -> None:
        """Initialize StepNetworkConfig validation."""
        self.step_filter: str = f"name=={step_name}" if step_name else ""
        super().__init__(
            name="StepNetworkConfig",
            paths=[
                f".steps[{self.step_filter}].processor.network_config",
            ],
            rule=rule,
        )
        self.network_config_expected: NetworkConfig = network_config_expected

    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> Dict[str, ValidationResult]:
        """Runs validation of NetworkConfigs on Pipeline.

        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: Dict containing the validation result
        :rtype: Dict[str, ValidationResult]
        """
        network_configs_observed = self.get_attribute(sagemaker_pipeline)

        # Compatibility with TrainingStep
        default_network_config = NetworkConfig()
        training_step_estimators = [
            step.estimator for step in sagemaker_pipeline.steps if isinstance(step, TrainingStep)
        ]
        for step in training_step_estimators:
            step_dict = {}
            for attr_name in default_network_config.__dict__.keys():
                attr_value = getattr(step, attr_name)
                step_dict[attr_name] = attr_value() if isfunction(attr_value) else attr_value
        network_configs_observed.append(NetworkConfig(**step_dict))
        # Converting objects to dicts to make it comparable
        # Handling None values
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
        results = self.rule.run(network_configs_observed_dict, [network_config_expected_dict])
        return {self.name: results}

import pytest
from moto import mock_ecr, mock_iam, mock_lambda
from sagemaker.inputs import FileSystemInput, TrainingInput
from sagemaker.processing import NetworkConfig, ProcessingInput, ProcessingOutput
from sagemaker.workflow.parameters import ParameterString

from sagemaker_rightline.model import Validation, ValidationResult
from sagemaker_rightline.rules import Contains, Equals
from sagemaker_rightline.validations import (
    ContainerImage,
    PipelineParametersAsExpected,
    StepImagesExist,
    StepInputsAsExpected,
    StepKmsKeyIdAsExpected,
    StepLambdaFunctionExists,
    StepNetworkConfigAsExpected,
    StepOutputsAsExpected,
    StepOutputsMatchInputsAsExpected,
    StepRoleNameAsExpected,
    StepRoleNameExists,
    StepTagsAsExpected,
)
from tests.fixtures.constants import (
    TEST_ACCOUNT_ID,
    TEST_LAMBDA_FUNC_NAME,
    TEST_REGION_NAME,
    TEST_ROLE_NAME,
)
from tests.fixtures.image_details import (
    IMAGE_1_REPOSITORY_NAME,
    IMAGE_1_TAG,
    IMAGE_1_URI,
    IMAGE_2_URI,
)
from tests.fixtures.pipeline import DUMMY_BUCKET, get_sagemaker_pipeline
from tests.utils import (
    create_iam_role,
    create_image,
    create_lambda_function,
    ecr_client,
    iam_client,
    lambda_client,
)


@pytest.fixture
def sagemaker_pipeline():
    return get_sagemaker_pipeline()


def test_container_image() -> None:
    container_image = ContainerImage(uri=IMAGE_1_URI)
    assert container_image.uri == IMAGE_1_URI
    assert container_image.account_id == TEST_ACCOUNT_ID
    assert container_image.repository == IMAGE_1_REPOSITORY_NAME
    assert container_image.region == TEST_REGION_NAME
    assert container_image.tag == IMAGE_1_TAG


def test_validation_result() -> None:
    success = True
    negative = True
    message = "test-message"
    subject = "test-subject"
    validation_name = "test"
    vr = ValidationResult(
        success=success,
        negative=negative,
        message=message,
        subject=subject,
        validation_name=validation_name,
    )
    assert vr.success == success
    assert vr.negative == negative
    assert vr.message == message
    assert vr.subject == subject
    assert vr.validation_name == validation_name


@mock_ecr
def test_step_image_exists_run_positive(ecr_client, sagemaker_pipeline) -> None:
    container_images = [
        ContainerImage(uri=IMAGE_1_URI),
        ContainerImage(uri=IMAGE_2_URI),
    ]
    with create_image(ecr_client, container_images):
        image_exists = StepImagesExist()
        result = image_exists.run(sagemaker_pipeline)

    assert result.success
    assert not result.negative
    assert result.message.endswith(" exist.")


@mock_ecr
def test_step_image_exists_run_negative(sagemaker_pipeline) -> None:
    image_exists = StepImagesExist()
    result = image_exists.run(sagemaker_pipeline)

    assert not result.success
    assert result.message.endswith(" not exist.")


def test_step_image_exists_wrong_client() -> None:
    with pytest.raises(ValueError):
        _ = StepImagesExist(boto3_client="not-a-boto3-client")


def test_step_lambda_function_exists_wrong_client() -> None:
    with pytest.raises(ValueError):
        _ = StepLambdaFunctionExists(boto3_client="not-a-boto3-client")


def test_step_role_name_exists_wrong_client() -> None:
    with pytest.raises(ValueError):
        _ = StepRoleNameExists(boto3_client="not-a-boto3-client")


@pytest.mark.parametrize(
    "parameters_expected,success",
    [
        [
            [
                ParameterString(name="parameter-1", default_value="some-value-1"),
                ParameterString(name="parameter-2", default_value="some-value-2"),
            ],
            True,
        ],
        [[ParameterString(name="parameter-1", default_value="some-value-1")], False],
        [
            [
                ParameterString(name="parameter-1", default_value="some-value-1"),
                ParameterString(name="nonexistent-parameter", default_value="some-value-2"),
            ],
            False,
        ],
        [
            [
                ParameterString(name="parameter-1"),
                ParameterString(name="parameter-2", default_value="some-value-2"),
            ],
            False,
        ],
    ],
)
def test_pipeline_parameters_equals(parameters_expected, success, sagemaker_pipeline) -> None:
    pipeline_parameters = PipelineParametersAsExpected(
        parameters_expected=parameters_expected,
        rule=Equals(),
    )
    result = pipeline_parameters.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "parameters_expected,ignore_default_value,success",
    [
        [
            [
                ParameterString(name="parameter-1"),
                ParameterString(name="parameter-2"),
            ],
            True,
            True,
        ],
        [
            [
                ParameterString(name="parameter-1", default_value="some-value-1"),
                ParameterString(name="parameter-2", default_value="different-default-value"),
            ],
            False,
            False,
        ],
    ],
)
def test_pipeline_parameters_ignore_default_value(
    parameters_expected, ignore_default_value, success, sagemaker_pipeline
) -> None:
    pipeline_parameters = PipelineParametersAsExpected(
        parameters_expected=parameters_expected,
        ignore_default_value=ignore_default_value,
        rule=Equals(),
    )
    result = pipeline_parameters.run(sagemaker_pipeline)
    assert result.success == success


def test_has_parameters_raise() -> None:
    with pytest.raises(ValueError):
        _ = PipelineParametersAsExpected(parameters_expected=[], rule=Equals())


@pytest.mark.parametrize(
    "kms_key_id_expected,success",
    [
        ["some/kms-key-alias", True],
        ["does-not-exist", False],
    ],
)
def test_step_kms_key_id(kms_key_id_expected, success, sagemaker_pipeline) -> None:
    has_kms_key_id_in_processing_output = StepKmsKeyIdAsExpected(
        kms_key_id_expected=kms_key_id_expected,
        rule=Equals(),
    )
    result = has_kms_key_id_in_processing_output.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "kms_key_id_expected,success",
    [
        ["some/kms-key-alias", True],
        ["does-not-exist", False],
    ],
)
def test_step_kms_key_id_filter(kms_key_id_expected, success, sagemaker_pipeline) -> None:
    has_kms_key_id_in_processing_output = StepKmsKeyIdAsExpected(
        kms_key_id_expected=kms_key_id_expected,
        step_name="sm_processing_step_sklearn",
        rule=Equals(),
    )
    result = has_kms_key_id_in_processing_output.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "kms_key_id_expected,success",
    [
        ["some/kms-key-alias", True],
        ["does-not-exist", False],
    ],
)
def test_step_kms_key_id_no_filter(kms_key_id_expected, success, sagemaker_pipeline) -> None:
    has_kms_key_id_in_processing_output = StepKmsKeyIdAsExpected(
        kms_key_id_expected=kms_key_id_expected,
        rule=Equals(),
    )
    result = has_kms_key_id_in_processing_output.run(sagemaker_pipeline)
    assert result.success == success


def test_get_filtered_attributes_steps(sagemaker_pipeline) -> None:
    steps = Validation.get_filtered_attributes(
        filter_subject=sagemaker_pipeline.steps,
        path=".steps[name==sm_processing_step_sklearn && step_type.value==Processing].kms_key",
    )
    assert len(steps) == 1
    assert steps[0].name == "sm_processing_step_sklearn"


def test_step_network_config(
    sagemaker_pipeline,
) -> None:
    network_config_expected = NetworkConfig(
        enable_network_isolation=True,
        security_group_ids=["sg-12345"],
        subnets=["subnet-12345"],
        encrypt_inter_container_traffic=True,
    )
    step_network_config = StepNetworkConfigAsExpected(
        network_config_expected=network_config_expected,
        rule=Equals(),
    )
    result = step_network_config.run(sagemaker_pipeline)
    assert result.success


def test_step_network_config_none_observed(
    sagemaker_pipeline,
) -> None:
    network_config_expected = NetworkConfig(
        enable_network_isolation=True,
        security_group_ids=["sg-12345"],
        subnets=["subnet-12345"],
        encrypt_inter_container_traffic=True,
    )
    step_network_config = StepNetworkConfigAsExpected(
        network_config_expected=network_config_expected,
        rule=Equals(),
    )
    result = step_network_config.rule.run([None], network_config_expected, step_network_config.name)
    assert not result.success


@pytest.mark.parametrize(
    "network_config_expected,success,step_name",
    [
        [
            NetworkConfig(
                enable_network_isolation=True,
                security_group_ids=["sg-12345"],
                subnets=["subnet-12345"],
                encrypt_inter_container_traffic=True,
            ),
            True,
            "sm_processing_step_sklearn",
        ],
        [
            NetworkConfig(
                enable_network_isolation=True,
                security_group_ids=["sg-12345"],
                subnets=["other-subnet"],
                encrypt_inter_container_traffic=False,
            ),
            False,
            "sm_processing_step_sklearn",
        ],
        [NetworkConfig(), False, "sm_processing_step_sklearn"],
        [None, False, "sm_processing_step_sklearn"],
        [NetworkConfig(), False, "sm_processing_step_spark"],
        [
            NetworkConfig(
                enable_network_isolation=True,
                security_group_ids=["sg-12345"],
                subnets=["subnet-12345"],
                encrypt_inter_container_traffic=True,
            ),
            True,
            "sm_training_step_sklearn",
        ],
    ],
)
def test_step_network_config_filter(
    network_config_expected, success, step_name, sagemaker_pipeline
) -> None:
    step_network_config = StepNetworkConfigAsExpected(
        network_config_expected=network_config_expected,
        rule=Equals(),
        step_name=step_name,
    )
    result = step_network_config.run(sagemaker_pipeline)
    assert result.success == success


@mock_iam
@mock_lambda
def test_lambda_function_exists_positive(lambda_client, iam_client, sagemaker_pipeline) -> None:
    with create_lambda_function(lambda_client, iam_client, [TEST_LAMBDA_FUNC_NAME]):
        lambda_function_exists = StepLambdaFunctionExists()
        result = lambda_function_exists.run(sagemaker_pipeline)
    assert result.success


@mock_lambda
def test_lambda_function_exists_negative(lambda_client, sagemaker_pipeline) -> None:
    lambda_function_exists = StepLambdaFunctionExists()
    result = lambda_function_exists.run(sagemaker_pipeline)
    assert not result.success


@mock_iam
def test_role_exists_positive(iam_client, sagemaker_pipeline) -> None:
    with create_iam_role(iam_client, [TEST_ROLE_NAME]):
        role_exists = StepRoleNameExists()
        result = role_exists.run(sagemaker_pipeline)
    assert result.success


@mock_iam
def test_role_exists_negative(iam_client, sagemaker_pipeline) -> None:
    role_exists = StepRoleNameExists()
    result = role_exists.run(sagemaker_pipeline)
    assert not result.success


@pytest.mark.parametrize(
    "role_name_expected,success",
    [
        [TEST_ROLE_NAME, True],
        ["nonexistent-role-name", False],
    ],
)
def test_step_role_name_as_expected_filter(role_name_expected, success, sagemaker_pipeline) -> None:
    step_role_validation = StepRoleNameAsExpected(
        role_name_expected=role_name_expected,
        step_name="sm_processing_step_sklearn",
        rule=Equals(),
    )
    result = step_role_validation.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "role_name_expected,success",
    [
        [TEST_ROLE_NAME, True],
        ["nonexistent-role-name", False],
    ],
)
def test_step_role_name_as_expected_no_filter(
    role_name_expected, success, sagemaker_pipeline
) -> None:
    step_role_validation = StepRoleNameAsExpected(
        role_name_expected=role_name_expected,
        rule=Equals(),
    )
    result = step_role_validation.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "rule,tags_expected,step_name,success",
    [
        [Equals, [{"Key": "some-key", "Value": "some-value"}], "sm_processing_step_spark", True],
        [Contains, [{"Key": "some-key", "Value": "some-value"}], "sm_processing_step_spark", True],
        [
            Contains,
            [{"Key": "some-key", "Value": "some-value"}],
            "sm_processing_step_sklearn",
            True,
        ],
        [
            Equals,
            [
                {
                    "Key": "some-key",
                    "Value": ParameterString(name="parameter-1", default_value="some-value-1"),
                }
            ],
            "sm_training_step_sklearn",
            False,
        ],
        [
            Equals,
            [
                {"Key": "some-key", "Value": "some-value"},
                {
                    "Key": "some-key",
                    "Value": ParameterString(name="parameter-1", default_value="some-value-1"),
                },
            ],
            "sm_training_step_sklearn",
            True,
        ],
        [
            Equals,
            [
                {"Key": "some-key", "Value": "some-value"},
                {"Key": "some-non-existent-key", "Value": "some-non-existent-value"},
            ],
            "sm_processing_step_spark",
            False,
        ],
        [
            Equals,
            [{"Key": "some-key", "Value": "some-non-existent-value"}],
            "sm_processing_step_spark",
            False,
        ],
        [
            Equals,
            [{"Key": "some-non-existent-key", "Value": "some-value"}],
            "sm_processing_step_spark",
            False,
        ],
        [Equals, [], "sm_processing_step_spark", False],
    ],
)
def test_step_tags_as_expected_filter(
    rule, tags_expected, step_name, success, sagemaker_pipeline
) -> None:
    step_role_validation = StepTagsAsExpected(
        tags_expected=tags_expected,
        step_name=step_name,
        rule=rule(),
    )
    result = step_role_validation.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "rule,tags_expected,success",
    [
        [Equals, [{"Key": "some-key", "Value": "some-value"}], False],
        [Equals, [{"Key": "some-non-existent-key", "Value": "some-non-existent-value"}], False],
        [
            Contains,
            [
                {
                    "Key": "some-key",
                    "Value": ParameterString(name="parameter-1", default_value="some-value-1"),
                }
            ],
            False,
        ],
        [Contains, [{"Key": "some-key", "Value": "some-value"}], True],
    ],
)
def test_step_tags_as_expected_no_filter(rule, tags_expected, success, sagemaker_pipeline) -> None:
    step_role_validation = StepTagsAsExpected(
        tags_expected=tags_expected,
        rule=rule(),
    )
    result = step_role_validation.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "rule,inputs_expected,step_type,success",
    [
        [
            Contains,
            [
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/input-2",
                    destination="/opt/ml/processing/input",
                    input_name="input-2",
                )
            ],
            "Processing",
            True,
        ],
        [
            Contains,
            [
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/input-2",
                    destination="/opt/ml/processing/input",
                    input_name="input-3",
                )
            ],
            "Processing",
            False,
        ],
        [
            Contains,
            [
                {
                    "train": TrainingInput(
                        s3_data=f"s3://{DUMMY_BUCKET}/some-prefix/validation",
                        content_type="text/csv",
                    )
                }
            ],
            "Training",
            True,
        ],
        [
            Contains,
            [
                {
                    "validation": FileSystemInput(
                        file_system_id="fs-1234",
                        file_system_type="EFS",
                        directory_path="/some/path",
                        file_system_access_mode="ro",
                    )
                }
            ],
            "Training",
            True,
        ],
    ],
)
def test_step_inputs_as_expected_no_filter(
    rule, inputs_expected, step_type, success, sagemaker_pipeline
) -> None:
    step_inputs_validation = StepInputsAsExpected(
        inputs_expected=inputs_expected,
        step_type=step_type,
        rule=rule(),
    )
    result = step_inputs_validation.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "rule,inputs_expected,step_name,success",
    [
        [
            Equals,
            [
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/output-1",
                    destination="/opt/ml/processing/input",
                    input_name="input-1",
                ),
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/input-2",
                    destination="/opt/ml/processing/input",
                    input_name="input-2",
                ),
            ],
            "sm_processing_step_sklearn",
            True,
        ],
        [
            Equals,
            [
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/input-2",
                    destination="/opt/ml/processing/input",
                    input_name="input-2",
                ),
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/output-1",
                    destination="/opt/ml/processing/input",
                    input_name="input-1",
                ),
            ],
            "sm_processing_step_sklearn",
            True,
        ],
        [
            Equals,
            [
                {
                    "train": TrainingInput(
                        s3_data=f"s3://{DUMMY_BUCKET}/some-prefix/validation",
                        content_type="text/csv",
                    ),
                    "validation": FileSystemInput(
                        file_system_id="fs-1234",
                        file_system_type="EFS",
                        directory_path="/some/path",
                        file_system_access_mode="ro",
                    ),
                    "some-key": "some-value",
                }
            ],
            "sm_training_step_sklearn",
            True,
        ],
        [
            Equals,
            [
                {
                    "train": TrainingInput(
                        s3_data=f"s3://{DUMMY_BUCKET}/some-prefix/validation",
                        content_type="text/csv",
                    ),
                    "some-key": "some-value",
                    "validation": FileSystemInput(
                        file_system_id="fs-1234",
                        file_system_type="EFS",
                        directory_path="/some/path",
                        file_system_access_mode="ro",
                    ),
                }
            ],
            "sm_training_step_sklearn",
            True,
        ],
        [
            Equals,
            [
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/does-not-match",
                    destination="/opt/ml/processing/input",
                    input_name="input-1",
                ),
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/input-1",
                    destination="/opt/ml/processing/input",
                    input_name="input-2",
                ),
            ],
            "sm_processing_step_sklearn",
            False,
        ],
    ],
)
def test_step_inputs_as_expected_filter(
    rule, inputs_expected, step_name, success, sagemaker_pipeline
) -> None:
    step_inputs_validation = StepInputsAsExpected(
        inputs_expected=inputs_expected,
        step_name=step_name,
        rule=rule(),
    )
    result = step_inputs_validation.run(sagemaker_pipeline)
    assert result.success == success


def test_step_inputs_as_expected_args_validation_step_type() -> None:
    with pytest.raises(ValueError):
        StepInputsAsExpected(
            inputs_expected=[],
            step_type="does-not-exist",
            rule=Equals(),
        )


def test_step_inputs_as_expected_args_validation_exclusive() -> None:
    with pytest.raises(ValueError):
        StepInputsAsExpected(
            inputs_expected=[],
            step_type="does-not-exist",
            step_name="does-not-exist",
            rule=Equals(),
        )


def test_step_inputs_as_expected_args_validation_neither() -> None:
    with pytest.raises(ValueError):
        StepInputsAsExpected(
            inputs_expected=[],
            rule=Equals(),
        )


@pytest.mark.parametrize(
    "rule,outputs_expected,success",
    [
        [
            Contains,
            [
                ProcessingOutput(
                    output_name="output-1",
                    source="/opt/ml/processing/output/1",
                    destination=f"s3://{DUMMY_BUCKET}/output-1",
                ),
                ProcessingOutput(
                    output_name="output-2",
                    source="/opt/ml/processing/output/2",
                    destination=f"s3://{DUMMY_BUCKET}/output-2",
                ),
            ],
            True,
        ],
        [
            Contains,
            [
                ProcessingOutput(
                    output_name="output-999",
                    source="/opt/ml/processing/output/1",
                    destination=f"s3://{DUMMY_BUCKET}/output-1",
                ),
                ProcessingOutput(
                    output_name="output-2",
                    source="/opt/ml/processing/output/2",
                    destination=f"s3://{DUMMY_BUCKET}/output-2",
                ),
            ],
            False,
        ],
        [
            Equals,
            [
                ProcessingOutput(
                    output_name="output-1",
                    source="/opt/ml/processing/output/1",
                    destination=f"s3://{DUMMY_BUCKET}/output-1",
                ),
                ProcessingOutput(
                    output_name="output-2",
                    source="/opt/ml/processing/output/2",
                    destination=f"s3://{DUMMY_BUCKET}/output-2",
                ),
            ],
            False,
        ],
    ],
)
def test_step_outputs_as_expected_no_filter(
    rule, outputs_expected, success, sagemaker_pipeline
) -> None:
    step_outputs_validation = StepOutputsAsExpected(
        outputs_expected=outputs_expected,
        rule=rule(),
    )
    result = step_outputs_validation.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "rule,outputs_expected,step_name,success",
    [
        [
            Equals,
            [
                ProcessingOutput(
                    output_name="output-1",
                    source="/opt/ml/processing/output/1",
                    destination=f"s3://{DUMMY_BUCKET}/output-1",
                ),
                ProcessingOutput(
                    output_name="output-2",
                    source="/opt/ml/processing/output/2",
                    destination=f"s3://{DUMMY_BUCKET}/output-2",
                ),
            ],
            "sm_processing_step_sklearn",
            True,
        ],
        [
            Contains,
            [
                ProcessingOutput(
                    output_name="output-2",
                    source="/opt/ml/processing/output/2",
                    destination=f"s3://{DUMMY_BUCKET}/output-2",
                ),
            ],
            "sm_processing_step_sklearn",
            True,
        ],
    ],
)
def test_step_outputs_as_expected_filter(
    rule, outputs_expected, step_name, success, sagemaker_pipeline
) -> None:
    step_outputs_validation = StepOutputsAsExpected(
        outputs_expected=outputs_expected,
        step_name=step_name,
        rule=rule(),
    )
    result = step_outputs_validation.run(sagemaker_pipeline)
    assert result.success == success


@pytest.mark.parametrize(
    "inputs_outputs_expected,success,raise_error",
    [
        [
            [
                {
                    "input": {
                        "step_name": "sm_processing_step_sklearn",
                        "input_name": "input-1",
                    },
                    "output": {
                        "step_name": "sm_processing_step_sklearn",
                        "output_name": "output-1",
                    },
                }
            ],
            True,
            False,
        ],
        [
            [
                {
                    "input": {
                        "step_name": "sm_processing_step_sklearn",
                        "input_name": "input-1",
                    },
                    "output": {
                        "step_name": "sm_processing_step_sklearn",
                        "output_name": "output-2",
                    },
                }
            ],
            False,
            False,
        ],
        [
            [
                {
                    "input": {
                        "step_name": "sm_processing_step_sklearn",
                        "input_name": "input-1",
                    },
                    "output": {
                        "step_name": "step_doesnt_exist",
                        "output_name": "output-1",
                    },
                }
            ],
            False,
            True,
        ],
        [
            [
                {
                    "input": {
                        "step_name": "sm_processing_step_sklearn",
                        "input_name": "input-doesnt-exist1",
                    },
                    "output": {
                        "step_name": "sm_processing_step_sklearn",
                        "output_name": "output-1",
                    },
                }
            ],
            False,
            True,
        ],
    ],
)
def test_step_outputs_match_inputs_as_expected(
    sagemaker_pipeline, inputs_outputs_expected, success, raise_error
) -> None:
    step_outputs_validation = StepOutputsMatchInputsAsExpected(
        inputs_outputs_expected=inputs_outputs_expected,
    )
    if raise_error:
        with pytest.raises((ValueError, AttributeError)):
            _ = step_outputs_validation.run(sagemaker_pipeline)
    else:
        result = step_outputs_validation.run(sagemaker_pipeline)
        assert result.success is success

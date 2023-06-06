import pytest
from moto import mock_ecr, mock_iam, mock_lambda
from sagemaker.processing import NetworkConfig
from sagemaker.workflow.parameters import ParameterString

from sagemaker_rightline.model import Validation, ValidationResult
from sagemaker_rightline.rules import Equals
from sagemaker_rightline.validations import (
    ContainerImage,
    PipelineParameters,
    StepImagesExistOnEcr,
    StepKmsKeyId,
    StepLambdaFunctionExists,
    StepNetworkConfig,
    StepRoleNameAsExpected,
    StepRoleNameExists,
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
from tests.fixtures.pipeline import get_sagemaker_pipeline
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
        image_exists = StepImagesExistOnEcr()
        result = image_exists.run(sagemaker_pipeline)

    assert result.success
    assert not result.negative
    assert result.message.endswith(" exist.")


@mock_ecr
def test_step_image_exists_run_negative(sagemaker_pipeline) -> None:
    image_exists = StepImagesExistOnEcr()
    result = image_exists.run(sagemaker_pipeline)

    assert not result.success
    assert result.message.endswith(" not exist.")


def test_step_image_exists_wrong_client() -> None:
    with pytest.raises(ValueError):
        _ = StepImagesExistOnEcr(boto3_client="not-a-boto3-client")


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
    pipeline_parameters = PipelineParameters(
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
    pipeline_parameters = PipelineParameters(
        parameters_expected=parameters_expected,
        ignore_default_value=ignore_default_value,
        rule=Equals(),
    )
    result = pipeline_parameters.run(sagemaker_pipeline)
    assert result.success == success


def test_has_parameters_raise() -> None:
    with pytest.raises(ValueError):
        _ = PipelineParameters(parameters_expected=[], rule=Equals())


@pytest.mark.parametrize(
    "kms_key_id_expected,success",
    [
        ["some/kms-key-alias", True],
        ["does-not-exist", False],
    ],
)
def test_step_kms_key_id(kms_key_id_expected, success, sagemaker_pipeline) -> None:
    has_kms_key_id_in_processing_output = StepKmsKeyId(
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
    has_kms_key_id_in_processing_output = StepKmsKeyId(
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
    has_kms_key_id_in_processing_output = StepKmsKeyId(
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
    step_network_config = StepNetworkConfig(
        network_config_expected=network_config_expected,
        rule=Equals(),
    )
    result = step_network_config.run(sagemaker_pipeline)
    assert not result.success


def test_step_network_config_none_observed(
    sagemaker_pipeline,
) -> None:
    network_config_expected = NetworkConfig(
        enable_network_isolation=True,
        security_group_ids=["sg-12345"],
        subnets=["subnet-12345"],
        encrypt_inter_container_traffic=True,
    )
    step_network_config = StepNetworkConfig(
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
    step_network_config = StepNetworkConfig(
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
def test_step_role_filter(role_name_expected, success, sagemaker_pipeline) -> None:
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
def test_step_role_no_filter(role_name_expected, success, sagemaker_pipeline) -> None:
    step_role_validation = StepRoleNameAsExpected(
        role_name_expected=role_name_expected,
        rule=Equals(),
    )
    result = step_role_validation.run(sagemaker_pipeline)
    assert result.success == success

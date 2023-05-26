import pytest
from moto import mock_ecr
from sagemaker.processing import NetworkConfig
from sagemaker.workflow.parameters import ParameterString

from sagemaker_rightline.model import ValidationResult
from sagemaker_rightline.rules import Equals
from sagemaker_rightline.validations import (
    ContainerImage,
    PipelineParameters,
    StepImagesExistOnEcr,
    StepKmsKeyId,
    StepNetworkConfig,
)
from tests.fixtures.constants import TEST_ACCOUNT_ID, TEST_REGION_NAME
from tests.fixtures.image_details import (
    IMAGE_1_REPOSITORY_NAME,
    IMAGE_1_TAG,
    IMAGE_1_URI,
    IMAGE_2_URI,
)
from tests.fixtures.pipeline import get_sagemaker_pipeline
from tests.utils import create_image, ecr_client


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
    message = "test-message"
    subject = "test-subject"
    vr = ValidationResult(
        success=success,
        message=message,
        subject=subject,
    )
    assert vr.success == success
    assert vr.message == message
    assert vr.subject == subject


@mock_ecr
def test_image_exists_run_positive(ecr_client, sagemaker_pipeline) -> None:
    container_images = [
        ContainerImage(uri=IMAGE_1_URI),
        ContainerImage(uri=IMAGE_2_URI),
    ]
    with create_image(ecr_client, container_images):
        image_exists = StepImagesExistOnEcr()
        results = image_exists.run(sagemaker_pipeline)

    assert results[image_exists.name].success
    assert results[image_exists.name].message.endswith(" exist.")


@mock_ecr
def test_image_exists_run_negative(sagemaker_pipeline) -> None:
    image_exists = StepImagesExistOnEcr()
    results = image_exists.run(sagemaker_pipeline)

    assert not results[image_exists.name].success
    assert results[image_exists.name].message.endswith(" not exist.")


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
    results = pipeline_parameters.run(sagemaker_pipeline)
    assert results[pipeline_parameters.name].success == success


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
    results = pipeline_parameters.run(sagemaker_pipeline)
    assert results[pipeline_parameters.name].success == success


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
    results = has_kms_key_id_in_processing_output.run(sagemaker_pipeline)[
        has_kms_key_id_in_processing_output.name
    ]
    assert results.success == success


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
    results = has_kms_key_id_in_processing_output.run(sagemaker_pipeline)[
        has_kms_key_id_in_processing_output.name
    ]
    assert results.success == success


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
    results = has_kms_key_id_in_processing_output.run(sagemaker_pipeline)[
        has_kms_key_id_in_processing_output.name
    ]
    assert results.success == success


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
    results = step_network_config.run(sagemaker_pipeline)[step_network_config.name]
    assert not results.success


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
        [None, False, "sm_processing_step_spark"],
        [NetworkConfig(), False, "sm_processing_step_spark"],
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
    results = step_network_config.run(sagemaker_pipeline)[step_network_config.name]
    assert results.success == success

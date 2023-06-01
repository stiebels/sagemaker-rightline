import pytest
from moto import mock_ecr

from sagemaker_rightline.model import Configuration, Report
from sagemaker_rightline.rules import Equals
from sagemaker_rightline.validations import (
    ContainerImage,
    StepImagesExistOnEcr,
    StepKmsKeyId,
    ValidationResult,
)
from tests.fixtures.image_details import IMAGE_1_URI, IMAGE_2_URI
from tests.fixtures.pipeline import get_sagemaker_pipeline
from tests.utils import create_image, ecr_client


@pytest.fixture
def sagemaker_pipeline():
    return get_sagemaker_pipeline()


@pytest.mark.parametrize(
    "validations,error",
    [
        [["not_validation"], True],
        ["not_list", True],
        [[], True],
        [[StepImagesExistOnEcr()], False],
        [[StepImagesExistOnEcr(), StepImagesExistOnEcr()], False],
    ],
)
def test_configuration_validate_input_validations(validations, error: bool) -> None:
    if error:
        with pytest.raises((ValueError, TypeError)):
            Configuration._validate_input_validations(validations=validations)
    else:
        Configuration._validate_input_validations(validations=validations)


@pytest.mark.parametrize(
    "results",
    [
        [
            ValidationResult(
                success=True,
                negative=False,
                message="test-message",
                subject="test-subject-1",
                validation_name="test",
            )
        ],
        [
            ValidationResult(
                success=True,
                negative=False,
                message="test-message-true",
                subject="test-subject-2",
                validation_name="test",
            ),
            ValidationResult(
                success=False,
                negative=False,
                message="test-message-false",
                subject="test-subject-3",
                validation_name="test",
            ),
        ],
    ],
)
def test_configuration_make_report(results) -> None:
    report = Configuration._make_report(results=results)
    assert report.results == results
    assert isinstance(report, Report)
    assert isinstance(report.results, list)
    assert isinstance(report.results[0], ValidationResult)


@mock_ecr
@pytest.mark.parametrize(
    "report_length,validations",
    [
        [1, [StepImagesExistOnEcr()]],
        [2, [StepImagesExistOnEcr(), StepImagesExistOnEcr()]],
    ],
)
def test_configuration_run(sagemaker_pipeline, ecr_client, report_length, validations) -> None:
    """Test run method of Configuration class."""
    container_images = [
        ContainerImage(uri=IMAGE_1_URI),
        ContainerImage(uri=IMAGE_2_URI),
    ]
    with create_image(ecr_client, container_images):
        cf = Configuration(validations=validations, sagemaker_pipeline=sagemaker_pipeline)
        report = cf.run(fail_fast=False)

    assert len(report.results) == report_length


@mock_ecr
@pytest.mark.parametrize(
    "report_length,validations",
    [
        [1, [StepImagesExistOnEcr()]],
        [1, [StepImagesExistOnEcr(), StepImagesExistOnEcr()]],
    ],
)
def test_configuration_run_fail_fast(sagemaker_pipeline, report_length, validations) -> None:
    """Test run method of Configuration class."""
    cf = Configuration(validations=validations, sagemaker_pipeline=sagemaker_pipeline)
    report = cf.run(fail_fast=True)
    assert len(report.results) == report_length


def test_report_to_df() -> None:
    """Test to_df method of Report class."""
    validation_name = "StepImagesExistOnEcr"
    report = Report(
        results=[
            ValidationResult(
                success=True,
                negative=False,
                message="test-message-0",
                subject="test-subject-0",
                validation_name=validation_name,
            ),
        ]
    )
    df = report.to_df()
    assert df.shape == (1, 5)
    assert df.columns.tolist() == list(ValidationResult.__annotations__.keys())
    assert df["success"].tolist() == [True]
    assert df["negative"].tolist() == [False]
    assert df["message"].tolist() == ["test-message-0"]
    assert df["validation_name"].tolist() == [validation_name]


def test_validation_get_attribute_filter(sagemaker_pipeline) -> None:
    """Test get_attribute method of Validation class."""
    kms_key_alias_expected = "some/kms-key-alias"
    validation = StepKmsKeyId(
        step_name="sm_processing_step_sklearn",
        rule=Equals(),
        kms_key_id_expected=kms_key_alias_expected,
    )
    assert validation.get_attribute(sagemaker_pipeline) == [kms_key_alias_expected]


def test_validation_get_attribute_no_filter(sagemaker_pipeline) -> None:
    """Test get_attribute method of Validation class."""
    kms_key_alias_expected = "some/kms-key-alias"
    validation = StepKmsKeyId(
        rule=Equals(),
        kms_key_id_expected=kms_key_alias_expected,
    )
    assert validation.get_attribute(sagemaker_pipeline) == [
        kms_key_alias_expected,
        kms_key_alias_expected,
        kms_key_alias_expected,
    ]

    validation = StepImagesExistOnEcr()
    assert validation.get_attribute(sagemaker_pipeline) == [IMAGE_1_URI, IMAGE_2_URI, IMAGE_1_URI]

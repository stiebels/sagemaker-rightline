import pandas as pd
import pytest
from moto import mock_ecr

from sagemaker_rightline.model import (
    Configuration,
    Report,
    Validation,
    ValidationFailedError,
)
from sagemaker_rightline.rules import Equals, Rule
from sagemaker_rightline.validations import (
    ContainerImage,
    StepImagesExist,
    StepKmsKeyIdAsExpected,
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
        [[StepImagesExist()], False],
        [[StepImagesExist(), StepImagesExist()], False],
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
    "expected_report_length,validations, return_df",
    [
        [1, [StepImagesExist()], False],
        [2, [StepImagesExist(), StepImagesExist()], True],
    ],
)
def test_configuration_run(
    sagemaker_pipeline, ecr_client, expected_report_length, validations, return_df
) -> None:
    """Test run method of Configuration class."""
    container_images = [
        ContainerImage(uri=IMAGE_1_URI),
        ContainerImage(uri=IMAGE_2_URI),
    ]
    with create_image(ecr_client, container_images):
        cf = Configuration(validations=validations, sagemaker_pipeline=sagemaker_pipeline)
        report = cf.run(fail_fast=False, return_df=return_df)

    if return_df:
        assert isinstance(report, pd.DataFrame)
        observed_report_len = len(report)
    else:
        assert isinstance(report, Report)
        observed_report_len = len(report.results)
    assert observed_report_len == expected_report_length


def test_configuration_handle_empty_results(sagemaker_pipeline) -> None:
    """Test run method of Configuration class."""
    validation = StepKmsKeyIdAsExpected(
        step_name="sm_processing_step_sklearn",
        rule=Equals(),
        kms_key_id_expected="some/kms-key-alias",
    )
    cf = Configuration(validations=[validation], sagemaker_pipeline=sagemaker_pipeline)
    validation_result = cf._handle_empty_results(
        result=None,
        validation=validation,
    )
    assert isinstance(validation_result, ValidationResult)
    assert "not return any results" in validation_result.message
    assert not validation_result.success


@mock_ecr
@pytest.mark.parametrize(
    "raises_error,validations",
    [
        [False, [StepImagesExist()]],
        [True, [StepImagesExist(), StepImagesExist()]],
    ],
)
def test_configuration_run_fail_fast(sagemaker_pipeline, raises_error, validations) -> None:
    """Test run method of Configuration class."""
    cf = Configuration(validations=validations, sagemaker_pipeline=sagemaker_pipeline)
    if raises_error:
        with pytest.raises(ValidationFailedError):
            cf.run(fail_fast=True)
    else:
        report = cf.run(fail_fast=True)
        assert len(report.results) == 1


def test_report_to_df() -> None:
    """Test to_df method of Report class."""
    validation_name = "StepImagesExist"
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
    validation = StepKmsKeyIdAsExpected(
        step_name="sm_processing_step_sklearn",
        rule=Equals(),
        kms_key_id_expected=kms_key_alias_expected,
    )
    assert Validation.get_attribute(sagemaker_pipeline, validation.paths) == [
        kms_key_alias_expected
    ]


def test_validation_get_attribute_no_filter(sagemaker_pipeline) -> None:
    """Test get_attribute method of Validation class."""
    kms_key_alias_expected = "some/kms-key-alias"
    validation = StepKmsKeyIdAsExpected(
        rule=Equals(),
        kms_key_id_expected=kms_key_alias_expected,
    )
    assert Validation.get_attribute(sagemaker_pipeline, validation.paths) == [
        kms_key_alias_expected,
        kms_key_alias_expected,
        kms_key_alias_expected,
    ]

    validation = StepImagesExist()
    assert Validation.get_attribute(sagemaker_pipeline, validation.paths) == [
        IMAGE_1_URI,
        IMAGE_2_URI,
        IMAGE_1_URI,
    ]


def test_validation_failed_error():
    """Test ValidationFailedError class."""
    validation_result = ValidationResult(
        success=False,
        negative=False,
        message="test-message",
        subject="test-subject",
        validation_name="test",
    )
    with pytest.raises(ValidationFailedError):
        try:
            raise ValidationFailedError(validation_result)
        except ValidationFailedError as e:
            assert isinstance(e.message, str)
            assert e.validation_result == validation_result
            assert isinstance(e, ValidationFailedError)
            assert isinstance(e, Exception)
            raise

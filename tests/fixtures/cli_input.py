from sagemaker_rightline.model import Configuration
from sagemaker_rightline.rules import Equals
from sagemaker_rightline.validations import StepKmsKeyIdAsExpected
from tests.fixtures.pipeline import get_sagemaker_pipeline


def get_configuration() -> Configuration:
    validation = StepKmsKeyIdAsExpected(
        step_name="sm_processing_step_sklearn",
        rule=Equals(),
        kms_key_id_expected="some/kms-key-alias",
    )
    return Configuration(validations=[validation], sagemaker_pipeline=get_sagemaker_pipeline())

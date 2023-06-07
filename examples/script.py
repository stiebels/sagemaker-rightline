import boto3
from moto import mock_ecr
from sagemaker.processing import NetworkConfig
from sagemaker.workflow.parameters import ParameterString

from sagemaker_rightline.model import Configuration
from sagemaker_rightline.rules import Contains, Equals
from sagemaker_rightline.validations import (
    ContainerImage,
    PipelineParametersAsExpected,
    StepImagesExist,
    StepKmsKeyIdAsExpected,
    StepLambdaFunctionExists,
    StepNetworkConfigAsExpected,
    StepRoleNameAsExpected,
    StepRoleNameExists,
    StepTagsAsExpected,
)
from tests.fixtures.image_details import IMAGE_1_URI, IMAGE_2_URI
from tests.fixtures.pipeline import get_sagemaker_pipeline
from tests.utils import create_image

if __name__ == "__main__":
    """Execute minimal example of sagemaker-rightline.
    NOTE: EXECUTE FROM PROJECT ROOT DIRECTORY

    .. highlight:: bash
    .. code-block:: bash
        cd sagemaker-rightline
        python script.py
    """
    sm_pipeline = get_sagemaker_pipeline()
    container_images = [
        ContainerImage(uri=IMAGE_1_URI),
        ContainerImage(uri=IMAGE_2_URI),
    ]
    with mock_ecr():
        ecr_client = boto3.client("ecr")
        with create_image(ecr_client, container_images):
            validations = [
                StepImagesExist(),
                PipelineParametersAsExpected(
                    parameters_expected=[
                        ParameterString(
                            name="parameter-1",
                            default_value="some-value",
                        ),
                    ],
                    rule=Contains(),
                ),
                StepKmsKeyIdAsExpected(
                    kms_key_id_expected="some/kms-key-alias",
                    step_name="sm_training_step_sklearn",  # if not set, will check all steps
                    rule=Equals(),
                ),
                StepNetworkConfigAsExpected(
                    network_config_expected=NetworkConfig(
                        enable_network_isolation=False,
                        security_group_ids=["sg-1234567890"],
                        subnets=["subnet-1234567890"],
                    ),
                    rule=Equals(negative=True),
                ),
                StepLambdaFunctionExists(),
                StepRoleNameExists(),
                StepRoleNameAsExpected(
                    role_name_expected="some-role-name",
                    step_name="sm_training_step_sklearn",  # if not set, will check all steps
                    rule=Equals(),
                ),
                StepTagsAsExpected(
                    tags_expected=[
                        {
                            "some-key": "some-value",
                        }
                    ],
                    step_name="sm_training_step_sklearn",  # if not set, will check all steps
                    rule=Equals(),
                ),
            ]
            cm = Configuration(
                validations=validations,
                sagemaker_pipeline=sm_pipeline,
            )
            df = cm.run()
    print(df)

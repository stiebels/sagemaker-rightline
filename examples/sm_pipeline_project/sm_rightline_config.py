import json
import sys

import boto3

sys.path.append(".")

from contextlib import contextmanager
from typing import List

from moto import mock_ecr
from sagemaker.processing import NetworkConfig, ProcessingInput, ProcessingOutput
from sagemaker.workflow.parameters import ParameterString

from sagemaker_rightline.model import Configuration
from sagemaker_rightline.rules import Contains, Equals
from sagemaker_rightline.validations import (
    ContainerImage,
    PipelineParametersAsExpected,
    StepCallbackSqsQueueExists,
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

TEST_ACCOUNT_ID = "0123456789"
TEST_ROLE_NAME = "TestRole"
TEST_ROLE_ARN = f"arn:aws:iam::{TEST_ACCOUNT_ID}:role/{TEST_ROLE_NAME}"
TEST_REGION_NAME = "eu-west-1"
TEST_AWS_ACCESS_KEY_ID = "access_key"
TEST_AWS_SECRET_ACCESS_KEY = "secret_key"
TEST_AWS_DEFAULT_REGION = "eu-west-1"
TEST_LAMBDA_FUNC_NAME = "test-lambda-func"
TEST_SQS_QUEUE_NAME = "test-queue"
TEST_SQS_QUEUE_URL_BASE = f"https://sqs.{TEST_REGION_NAME}.amazonaws.com/{TEST_ACCOUNT_ID}"
TEST_SQS_QUEUE_URL = f"{TEST_SQS_QUEUE_URL_BASE}/{TEST_SQS_QUEUE_NAME}"
IMAGE_MANIFEST = json.dumps(
    {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": {
            "mediaType": "application/vnd.docker.container.image.v1+json",
            "size": 3,
            "digest": "sdfiojsdfioasdf",
        },
        "layers": [],
    }
)

IMAGE_REPOSITORY_NAME_PREFIX = "some/repo/path"
IMAGE_1_REPOSITORY_NAME = f"{IMAGE_REPOSITORY_NAME_PREFIX}/image1"
IMAGE_1_TAG = "0.1.1"
IMAGE_2_TAG = "1.0.0"
IMAGE_2_REPOSITORY_NAME = f"{IMAGE_REPOSITORY_NAME_PREFIX}/image2"

IMAGE_1_URI = (
    f"{TEST_ACCOUNT_ID}.dkr.ecr.{TEST_REGION_NAME}.amazonaws.com/"
    f"{IMAGE_1_REPOSITORY_NAME}:{IMAGE_1_TAG}"
)
IMAGE_2_URI = (
    f"{TEST_ACCOUNT_ID}.dkr.ecr.{TEST_REGION_NAME}.amazonaws.com/"
    f"{IMAGE_2_REPOSITORY_NAME}:{IMAGE_2_TAG}"
)
DUMMY_BUCKET = "dummy-bucket"

import os

os.environ["AWS_DEFAULT_REGION"] = TEST_AWS_DEFAULT_REGION
os.environ["AWS_SECRET_ACCESS_KEY"] = TEST_AWS_SECRET_ACCESS_KEY
os.environ["AWS_ACCESS_KEY_ID"] = TEST_AWS_ACCESS_KEY_ID

from pipeline import get_sagemaker_pipeline


@contextmanager
def create_image(ecr_client, container_images: List[ContainerImage]) -> None:
    for container_image in container_images:
        ecr_client.create_repository(
            registryId=container_image.account_id,
            repositoryName=container_image.repository,
        )
        ecr_client.put_image(
            registryId=container_image.account_id,
            repositoryName=container_image.repository,
            imageTag=container_image.tag,
            imageManifest=IMAGE_MANIFEST,
        )
    yield
    for container_image in container_images:
        _ = ecr_client.batch_delete_image(
            registryId=container_image.account_id,
            repositoryName=container_image.repository,
            imageIds=[{"imageTag": container_image.tag}],
        )
        _ = ecr_client.delete_repository(
            registryId=container_image.account_id,
            repositoryName=container_image.repository,
            force=True,
        )


def get_configuration() -> Configuration:
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
                StepInputsAsExpected(
                    inputs_expected=[
                        ProcessingInput(
                            source=f"s3://{DUMMY_BUCKET}/input-1",
                            destination="/opt/ml/processing/input",
                            input_name="input-2",
                        )
                    ],
                    step_type="Processing",  # either step_type or step_name must be set to filter
                    rule=Contains(),
                ),
                StepOutputsAsExpected(
                    outputs_expected=[
                        ProcessingOutput(
                            source="/opt/ml/processing/output",
                            destination=f"s3://{DUMMY_BUCKET}/output-1",
                            output_name="output-1",
                        )
                    ],
                    step_name="sm_processing_step_spark",  # optional
                    rule=Contains(),
                ),
                StepOutputsMatchInputsAsExpected(
                    inputs_outputs_expected=[
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
                    ]
                ),
                StepCallbackSqsQueueExists(),
            ]
            return Configuration(
                validations=validations,
                sagemaker_pipeline=get_sagemaker_pipeline(),
            )

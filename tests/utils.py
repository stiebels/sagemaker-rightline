from contextlib import contextmanager
from typing import List

import boto3
import pytest

from sagemaker_rightline.validations import ContainerImage
from tests.fixtures.constants import TEST_REGION_NAME, TEST_ROLE_ARN
from tests.fixtures.image_details import IMAGE_MANIFEST


@pytest.fixture(autouse=False)
def ecr_client():
    return boto3.client("ecr", region_name=TEST_REGION_NAME)


@pytest.fixture(autouse=False)
def lambda_client():
    return boto3.client("lambda", region_name=TEST_REGION_NAME)


def get_iam_client():
    return boto3.client("iam", region_name=TEST_REGION_NAME)


@contextmanager
def create_lambda_function(lambda_client, function_names: List[str]) -> None:
    get_iam_client().create_role(
        RoleName=TEST_ROLE_ARN.split("/")[-1],
        AssumeRolePolicyDocument='{"Version": "2012-10-17","Statement": '
        '[{"Effect": "Allow","Principal": {"Service": '
        '"lambda.amazonaws.com"},"Action": '
        '"sts:AssumeRole"}]}',
    )
    for function_name in function_names:
        lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.8",
            Role=TEST_ROLE_ARN,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": "lambda code"},
        )
    yield
    for function_name in function_names:
        lambda_client.delete_function(FunctionName=function_name)


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

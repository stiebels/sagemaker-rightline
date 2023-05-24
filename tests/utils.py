from contextlib import contextmanager
from typing import List

import boto3
import pytest

from sagemaker_rightline.validations import ContainerImage
from tests.fixtures.constants import TEST_REGION_NAME
from tests.fixtures.image_details import IMAGE_MANIFEST


@pytest.fixture(autouse=False)
def ecr_client():
    return boto3.client("ecr", region_name=TEST_REGION_NAME)


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

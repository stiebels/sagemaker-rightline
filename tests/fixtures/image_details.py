import json

from tests.fixtures.constants import TEST_ACCOUNT_ID, TEST_REGION_NAME

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

import json

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

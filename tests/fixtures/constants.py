from moto.core import DEFAULT_ACCOUNT_ID as TEST_ACCOUNT_ID

TEST_ROLE_NAME = "TestRole"
TEST_ROLE_ARN = f"arn:aws:iam::{TEST_ACCOUNT_ID}:role/{TEST_ROLE_NAME}"
TEST_REGION_NAME = "eu-west-1"
TEST_AWS_ACCESS_KEY_ID = "access_key"
TEST_AWS_SECRET_ACCESS_KEY = "secret_key"
TEST_AWS_DEFAULT_REGION = "eu-west-1"
TEST_LAMBDA_FUNC_NAME = "test-lambda-func"
TEST_SQS_QUEUE_URL = f"https://sqs.{TEST_REGION_NAME}.amazonaws.com/{TEST_ACCOUNT_ID}/test-queue"

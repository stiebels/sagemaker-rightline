import os

from tests.fixtures.constants import (
    TEST_AWS_ACCESS_KEY_ID,
    TEST_AWS_DEFAULT_REGION,
    TEST_AWS_SECRET_ACCESS_KEY,
)


def pytest_configure(config):
    os.environ["AWS_DEFAULT_REGION"] = TEST_AWS_DEFAULT_REGION
    os.environ["AWS_SECRET_ACCESS_KEY"] = TEST_AWS_SECRET_ACCESS_KEY
    os.environ["AWS_ACCESS_KEY_ID"] = TEST_AWS_ACCESS_KEY_ID

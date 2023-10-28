import os
from argparse import Namespace
from unittest.mock import patch

import pytest

from sagemaker_rightline.cli.validate import main, parse_args
from sagemaker_rightline.model import Report, ValidationResult


@patch("sagemaker_rightline.cli.validate.parse_args")
def test_main_working_dir_change(parse_args) -> None:
    """Positive test for CLI validate command."""
    old_working_dir = os.getcwd()
    new_working_dir = "tests/fixtures"

    parse_args.return_value = Namespace(
        configuration="tests/fixtures/cli_input.py",
        working_dir=new_working_dir,
    )
    with pytest.raises(FileNotFoundError):
        main()

    try:
        assert os.getcwd().endswith(new_working_dir)
    except AssertionError:
        raise
    finally:
        os.chdir(old_working_dir)


@patch("sagemaker_rightline.cli.validate.parse_args")
def test_main_positive(parse_args) -> None:
    """Positive test for CLI validate command."""
    parse_args.return_value = Namespace(configuration="tests/fixtures/cli_input.py")
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 0


@patch("sagemaker_rightline.cli.validate.parse_args")
def test_main_negative(parse_args) -> None:
    """Negative test CLI validate command."""
    parse_args.return_value = Namespace(configuration="tests/fixtures/cli_input.py")
    with patch(
        "sagemaker_rightline.model.Configuration.run",
        return_value=Report(
            results=[
                ValidationResult(
                    success=False,
                    negative=False,
                    message="test-message",
                    subject="test-subject-1",
                    validation_name="test-validation-name",
                ),
                ValidationResult(
                    success=True,
                    negative=False,
                    message="test-message",
                    subject="test-subject-2",
                    validation_name="test-validation-name",
                ),
            ]
        ).to_df(),
    ):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1


def test_parse_args_fail_required() -> None:
    """Fail with SystemExit if required arguments are not provided."""
    with pytest.raises(SystemExit) as excinfo:
        parse_args()
    assert excinfo.value.code == 2

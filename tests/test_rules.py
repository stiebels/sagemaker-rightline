from typing import List

import pytest
from sagemaker.workflow.parameters import ParameterString

from sagemaker_rightline.rules import Contains, Equals


@pytest.mark.parametrize(
    "observed,expected,success",
    [
        [["test1"], ["test1"], True],
        [["test1"], ["test2"], False],
        [
            [ParameterString(name="test1"), ParameterString(name="test2")],
            [ParameterString(name="test1"), ParameterString(name="test2")],
            True,
        ],
        [
            [ParameterString(name="test1"), ParameterString(name="test2")],
            [ParameterString(name="test2"), ParameterString(name="test1")],
            True,
        ],
        [[ParameterString(name="test3")], [ParameterString(name="test1")], False],
    ],
)
def test_equals(observed: List, expected: List, success: bool) -> None:
    equals = Equals()
    vr = equals.run(
        observed=observed,
        expected=expected,
    )
    assert vr.success == success


@pytest.mark.parametrize(
    "observed,expected,success",
    [
        [["test1", "test2"], ["test1", "test2"], True],
        [["test1"], ["test1", "test2"], False],
        [["test1", "test2"], ["test2"], True],
        [["test1", "test2"], ["test3", "test4"], False],
        [
            [ParameterString(name="test1"), ParameterString(name="test2")],
            [ParameterString(name="test2"), ParameterString(name="test1")],
            True,
        ],
        [[ParameterString(name="test3")], [ParameterString(name="test1")], False],
    ],
)
def test_contains_str(observed: List[str], expected: List[str], success: bool) -> None:
    contains = Contains()
    vr = contains.run(
        observed=observed,
        expected=expected,
    )
    assert vr.success == success

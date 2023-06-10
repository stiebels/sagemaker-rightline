from typing import List

import pytest
from sagemaker.workflow.parameters import ParameterString

from sagemaker_rightline.rules import Contains, Equals


@pytest.mark.parametrize(
    "observed,expected,negative,success",
    [
        [["test1"], ["test1"], False, True],
        [["test1"], ["test1"], True, False],
        [["test1"], ["test2"], False, False],
        [["test1"], ["test2"], True, True],
        [
            [ParameterString(name="test1"), ParameterString(name="test2")],
            [ParameterString(name="test1"), ParameterString(name="test2")],
            False,
            True,
        ],
        [
            [ParameterString(name="test1"), ParameterString(name="test2")],
            [ParameterString(name="test2"), ParameterString(name="test1")],
            False,
            True,
        ],
        [[ParameterString(name="test3")], [ParameterString(name="test1")], False, False],
        [{"foo": "bar"}, {"foo": "bar"}, False, True],
        [{"bar": "foo", "foo": "bar"}, {"foo": "bar", "bar": "foo"}, False, True],
        [{"bar": "bar"}, {"foo": "bar"}, False, False],
    ],
)
def test_equals(observed: List, expected: List, negative: bool, success: bool) -> None:
    equals = Equals(negative=negative)
    vr = equals.run(
        observed=observed,
        expected=expected,
        validation_name="some-validation",
    )
    assert vr.success == success


@pytest.mark.parametrize(
    "observed,expected,negative,success",
    [
        [["test1", "test2"], ["test1", "test2"], False, True],
        [["test1"], ["test1", "test2"], False, False],
        [["test1", "test2"], ["test1", "test2"], True, False],
        [["test1"], ["test1", "test2"], True, True],
        [["test1", "test2"], ["test2"], False, True],
        [["test1", "test2"], ["test3", "test4"], False, False],
        [
            [ParameterString(name="test1"), ParameterString(name="test2")],
            [ParameterString(name="test2"), ParameterString(name="test1")],
            False,
            True,
        ],
        [[ParameterString(name="test3")], [ParameterString(name="test1")], False, False],
    ],
)
def test_contains_str(
    observed: List[str], expected: List[str], negative: bool, success: bool
) -> None:
    contains = Contains(negative=negative)
    vr = contains.run(
        observed=observed,
        expected=expected,
        validation_name="some-validation",
    )
    assert vr.success == success

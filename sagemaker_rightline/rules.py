from typing import Any, List, Union

from sagemaker_rightline.model import Rule, ValidationResult


class Equals(Rule):
    """Check if two lists are equal."""

    def __init__(self, negative: bool = False) -> None:
        """Check if two lists are equal.

        :param negative: whether the rule should be inverted, i.e. "not" (default: False)
        :type negative: bool
        :return:
        :rtype:
        """
        super().__init__("Equals", negative)

    def run(
        self,
        observed: List[Union[int, float, str, dict]],
        expected: List[Union[int, float, str, dict]],
        validation_name: str,
    ) -> ValidationResult:
        """Check if two lists are equal.

        :param observed: observed list
        :type observed: List[Any]
        :param expected: expected list
        :type expected: List[Any]
        :param validation_name: name of the validation
        :type validation_name: str
        :return: validation result
        :rtype: ValidationResult
        """
        try:
            # In case of int, float, str
            is_equal = set(observed) == set(expected)
        except TypeError:
            # In case of dict
            if isinstance(observed, dict) and isinstance(expected, dict):
                is_equal = observed == expected
            # In case of nested list
            elif isinstance(observed, list) and isinstance(expected, list):
                is_equal = all(True if item in observed else False for item in expected) and all(
                    True if item in expected else False for item in observed
                )
            else:
                is_equal = observed == expected

        is_equal = is_equal if not self.negative else not is_equal
        return ValidationResult(
            validation_name=validation_name,
            success=is_equal,
            negative=self.negative,
            message=f"{str(observed)} does {'not ' if not is_equal else ''}equal {str(expected)}",
            subject=str(expected),
        )


class Contains(Rule):
    """Check if a list contains another list."""

    def __init__(self, negative: bool = False) -> None:
        """Check if a list contains another list.

        :param negative: whether the rule should be inverted, i.e. "not" (default: False)
        :type negative: bool
        :return:
        :rtype:
        """
        super().__init__("Contains", negative)

    def run(
        self, observed: List[Any], expected: List[Any], validation_name: str
    ) -> ValidationResult:
        """Check if a list contains another list.

        :param observed: observed list
        :type observed: List[Any]
        :param expected: expected list
        :type expected: List[Any]
        :param validation_name: name of the validation
        :type validation_name: str
        :return: validation result
        :rtype: ValidationResult
        """
        is_contained = all(item in observed for item in expected)
        is_contained = is_contained if not self.negative else not is_contained
        return ValidationResult(
            validation_name=validation_name,
            success=is_contained,
            negative=self.negative,
            message=f"{str(observed)} does {'not ' if not is_contained else ''}contain "
            f"{str(expected)}",
            subject=str(expected),
        )

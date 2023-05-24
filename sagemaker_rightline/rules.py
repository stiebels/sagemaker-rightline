from typing import Any, List

from sagemaker_rightline.model import Rule, ValidationResult


class Equals(Rule):
    """Check if two lists are equal."""

    def __init__(self):
        """Check if two lists are equal."""
        super().__init__("Equals")

    def run(self, observed: List[Any], expected: List[Any]) -> ValidationResult:
        """Check if two lists are equal.

        :param observed: observed list
        :type observed: List[Any]
        :param expected: expected list
        :return: validation result
        :rtype: ValidationResult
        """
        is_equal = set(observed) == set(expected)
        return ValidationResult(
            success=True if is_equal else False,
            message=f"{str(observed)} does {'not ' if not is_equal else ''}equal {str(expected)}",
            subject=str(expected),
        )


class Contains(Rule):
    """Check if a list contains another list."""

    def __init__(self):
        """Check if a list contains another list."""
        super().__init__("Contains")

    def run(self, observed: List[Any], expected: List[Any]) -> ValidationResult:
        """Check if a list contains another list.

        :param observed: observed list
        :type observed: List[Any]
        :param expected: expected list
        :return: validation result
        :rtype: ValidationResult
        """
        is_contained = set(expected).issubset(set(observed))
        return ValidationResult(
            success=True if is_contained else False,
            message=f"{str(observed)} does {'not ' if not is_contained else ''}contain "
            f"{str(expected)}",
            subject=str(expected),
        )

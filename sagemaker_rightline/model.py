import logging
import re
from abc import ABC, abstractmethod
from copy import copy
from dataclasses import dataclass
from operator import attrgetter
from typing import Any, Iterable, List, Optional, Union

import pandas as pd
from sagemaker.workflow.pipeline import Pipeline


@dataclass
class ValidationResult:
    """Validation result dataclass."""

    validation_name: str
    success: bool
    negative: bool
    message: str
    subject: str


class Rule(ABC):
    """Rule abstract base class."""

    def __init__(self, name: str, negative: bool = False) -> None:
        """Initialize a Rule object.

        :param name: name of the rule
        :type name: str
        :param negative: whether the rule should be inverted, i.e. "not" (default: False)
        :type negative: bool
        :return:
        :rtype:
        """
        self.name: str = name
        self.negative: bool = negative

    @abstractmethod
    def run(self, observed: Any, expected: Any, validation_name: str) -> ValidationResult:
        """Run the rule.

        :param observed: observed value
        :type observed: Any
        :param expected: expected value
        :type expected: Any
        :param validation_name: name of the validation
        :type validation_name: str
        :return: validation result
        :rtype: ValidationResult
        """
        raise NotImplementedError


class Validation(ABC):
    """Abstract class for validations."""

    def __init__(
        self, name: str, paths: Optional[List[str]] = None, rule: Optional[Rule] = None
    ) -> None:
        """Initialize a Validation object.

        :param paths: list of paths to the attributes to be validated
        :type paths: List[str]
        :param name: name of the validation
        :type name: str
        :param rule: rule to be applied to the validation, defaults to None
        :type rule: Optional[Rule]
        :return:
        :rtype:
        """
        self.paths: List[Optional[str]] = paths if paths else []
        self.name: str = name
        self.rule: Rule = rule

    @staticmethod
    def get_filtered_attributes(filter_subject: Iterable[object], path: str) -> List[object]:
        """Get filtered attributes from path.

        :param filter_subject: subject to be filtered
        :type filter_subject: Iterable[object]
        :param path: path to the attribute to be filtered
        :type path: str
        :return: filtered attributes
        :rtype: List[object]
        """
        # TODO: refactor
        filtered_steps = []
        filter_conditions = (
            re.search("\[(.*?)\]", path).group(1).replace(" ", "").split("&&")  # noqa: W605
        )
        filter_conditions = [
            condition.replace("/", ".") for condition in filter_conditions if condition
        ]
        for subject in filter_subject:
            match = []
            for condition in filter_conditions:
                filter_key, filter_value = condition.split("==")
                if attrgetter(filter_key)(subject) != filter_value:
                    match.append(False)
                    continue
                match.append(True)
            if all(match):
                filtered_steps.append(subject)
        return filtered_steps

    @staticmethod
    def get_attribute(
        sagemaker_pipeline: Pipeline,
        paths: List[str],
    ) -> List:
        """Get attribute from pipeline.

        :param sagemaker_pipeline: sagemaker pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :param paths: list of paths to the attributes to be validated
        :type paths: List[str]
        :return: attribute
        :rtype: List
        """
        # TODO: refactor
        result = []
        for path in paths:
            attr_path = path.split(".")[1:]
            sm_pipeline_copy = copy(sagemaker_pipeline)
            for ix, attr in enumerate(attr_path):
                if attr.endswith("]"):
                    has_filter_dict = attr[-2] != "["
                    raw_attr = attr.split("[")[0]
                    sm_pipeline_copy = getattr(sm_pipeline_copy, raw_attr)
                    if has_filter_dict:
                        sm_pipeline_copy = Validation.get_filtered_attributes(
                            sm_pipeline_copy, ".".join(attr_path[ix:])
                        )
                else:
                    sm_pipeline_copy = [
                        getattr(sub_attr, attr)
                        for sub_attr in sm_pipeline_copy
                        if hasattr(sub_attr, attr)
                    ]
            result.append(sm_pipeline_copy)
        return [x for y in result for x in y]

    @abstractmethod
    def run(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> ValidationResult:
        """Run validation."""
        raise NotImplementedError


class Report:
    """Report class."""

    def __init__(self, results: List[ValidationResult]) -> None:
        """Initialize a Report object.

        :param results: list of validation results
        :type results: List[Dict[str, ValidationResult]]
        :return: None
        :rtype: None
        """
        self.results: List[ValidationResult] = results

    def to_df(self) -> pd.DataFrame:
        """Convert report to pandas DataFrame.

        :return: report as pandas DataFrame
        :rtype: pd.DataFrame
        """
        df = pd.DataFrame.from_records(
            data=[x.__dict__ for x in self.results],
            columns=ValidationResult.__annotations__.keys(),
        )
        return df.reset_index(drop=True)


class ValidationFailedError(Exception):
    """Validation exception class."""

    def __init__(self, validation_result: ValidationResult) -> None:
        """Initialize a ValidationFailedError object.

        :param validation: error message
        :type validation: Validation
        :return: None
        :rtype: None
        """
        self.validation_result = validation_result
        self.message = f"Validation failed: {validation_result.__dict__}"
        super().__init__(self.message)


class Configuration:
    """Configuration class."""

    def __init__(self, validations: List[Validation], sagemaker_pipeline: Pipeline) -> None:
        """Initialize a Configuration object.

        :param validations: List of validations.
        :type validations: List[Validation]
        :param sagemaker_pipeline: SageMaker Pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :raises ValueError: If validations is empty.
        :raises TypeError: If validations is not a list.
        :raises TypeError: If any validation is not of type Validation.
        :return: None
        :rtype: None
        """
        Configuration._validate_input_validations(validations)
        self.validations: List[Validation] = validations
        self.sagemaker_pipeline: Pipeline = sagemaker_pipeline

    @staticmethod
    def _validate_input_validations(validations: List[Validation]) -> None:
        """Validate input validations.

        :param validations: List of validations.
        :type validations: List[Validation]
        :raises ValueError: If validations is empty.
        :raises TypeError: If validations is not a list.
        :raises TypeError: If any validation is not of type Validation.
        :return: None
        :rtype: None
        """
        if not validations:
            raise ValueError("Validations cannot be empty.")
        if not isinstance(validations, list):
            raise TypeError("Validations must be a list.")
        if not all(isinstance(v, Validation) for v in validations):
            raise TypeError("All validations must be of type Validation.")

    @staticmethod
    def _make_report(
        results: List[ValidationResult], return_df: bool = False
    ) -> Union[Report, pd.DataFrame]:
        """Make a report from a list of results.

        :param results: List of results.
        :type results: List[ValidationResult
        :param return_df: If True, return a pandas.DataFrame instead of a Report object.
        :type return_df: bool
        :return: Report object or pd.DataFrame.
        :rtype: Report or pd.DataFrame
        """
        report = Report(results)
        if return_df:
            return report.to_df()
        return report

    @staticmethod
    def _handle_empty_results(
        result: Optional[ValidationResult], validation: Validation
    ) -> ValidationResult:
        """Handle empty results. If a Validation does not return any results
        (e.g. when no observation were made), a warning is logged and a
        ValidationResult indicating this is added to the result dict.

        :param result: validation_result.
        :type result: Optional[ValidationResult]
        :param validation: Validation object.
        :type validation: Validation
        :return: validation result.
        :rtype: ValidationResult
        """
        if not result:
            logging.warning(
                f"Validation {validation.name} did not return any results. "
                f"Please check if the paths {validation.paths} are correct."
            )
            return ValidationResult(
                validation_name=validation.name,
                success=False,
                message=f"Validation {validation.name} did not return any results. "
                f"Please check if the paths {validation.paths} are correct.",
                subject=validation.paths,
                negative=False,
            )
        return result

    def run(self, fail_fast: bool = False, return_df: bool = False) -> Union[Report, dict]:
        """Run all validations and return a report.

        :param fail_fast: If True, stop validation after the first failure.
        :type fail_fast: bool
        :param return_df: If True, return a pandas dataframe instead of a Report object.
        :type return_df: bool
        :raises ValidationFailedError: If fail_fast is True and a validation fails.
        :return: Report object or pandas dataframe.
        :rtype: Report or dict
        """
        results = []
        for ix, validation in enumerate(self.validations):
            result = validation.run(self.sagemaker_pipeline)
            result = Configuration._handle_empty_results(result, validation)
            results.append(result)
            if not result.success and fail_fast and not (ix == len(self.validations) - 1):
                logging.info(
                    "Validation failed and fail_fast is set to True. Stopping validation "
                    "prematurely."
                )
                raise ValidationFailedError(result)
        return self._make_report(results, return_df)

import logging
import re
from abc import ABC, abstractmethod
from copy import copy
from dataclasses import dataclass
from operator import attrgetter
from typing import Any, Dict, Iterable, List, Optional, Union

import pandas as pd
from sagemaker.workflow.pipeline import Pipeline


@dataclass
class ValidationResult:
    """Validation result dataclass."""

    success: bool
    message: str
    subject: str


class Rule(ABC):
    """Rule abstract base class."""

    def __init__(self, name: str) -> None:
        """Initialize a Rule object."""
        self.name: str = name

    @abstractmethod
    def run(self, observed: Any, expected: Any) -> ValidationResult:
        """Run the rule."""
        raise NotImplementedError


class Validation(ABC):
    """Abstract class for validations."""

    def __init__(self, paths: List[str], name: str, rule: Optional[Rule] = None) -> None:
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
        self.paths: List[str] = paths
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

    def get_attribute(
        self,
        sagemaker_pipeline: Pipeline,
    ) -> List:
        """Get attribute from pipeline.

        :param sagemaker_pipeline: sagemaker pipeline
        :type sagemaker_pipeline: sagemaker.workflow.pipeline.Pipeline
        :return: attribute
        :rtype: List
        """
        # TODO: refactor
        result = []
        for path in self.paths:
            attr_path = path.split(".")[1:]
            sm_pipeline_copy = copy(sagemaker_pipeline)
            for ix, attr in enumerate(attr_path):
                if attr.endswith("]"):
                    has_filter_dict = attr[-2] != "["
                    raw_attr = attr.split("[")[0]
                    sm_pipeline_copy = getattr(sm_pipeline_copy, raw_attr)
                    if has_filter_dict:
                        sm_pipeline_copy = self.get_filtered_attributes(
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
    ) -> Dict[str, ValidationResult]:
        """Run validation."""
        raise NotImplementedError


class Report:
    def __init__(self, results: List[Dict[str, ValidationResult]]) -> None:
        self.results: List[Dict[str, ValidationResult]] = results

    def to_df(self) -> pd.DataFrame:
        # TODO: refactor
        df = pd.DataFrame(columns=["validation_name", "subject", "success", "message"])
        for validation in self.results:
            col_name = str(list(validation.keys())[0])
            validations = [x.__dict__ for x in validation.values()]
            df_int = pd.DataFrame.from_records(validations)
            df_int["validation_name"] = col_name
            df = pd.concat([df, df_int])
        return df.reset_index(drop=True)


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
        results: List[Dict[str, ValidationResult]], return_df: bool = False
    ) -> Union[Report, pd.DataFrame]:
        """Make a report from a list of results.

        :param results: List of results.
        :type results: List[Dict[str, str]]
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
        result: Dict[str, ValidationResult], validation: Validation
    ) -> Dict[str, ValidationResult]:
        """Handle empty results. If a Validation does not return any results
        (e.g. when no observation were made), a warning is logged and a
        ValidationResult indicating this is added to the result dict.

        :param result: Result dict.
        :type result: Dict[str, ValidationResult]
        :param validation: Validation object.
        :type validation: Validation
        :return: Result dict.
        :rtype: Dict[str, ValidationResult]
        """
        if len(result) == 0:
            logging.warning(
                f"Validation {validation.name} did not return any results. "
                f"Please check if the path {validation.path} is correct."
            )
            result[validation.name] = ValidationResult(
                success=False,
                message=f"Validation {validation.name} did not return any results. "
                f"Please check if the path {validation.path} is correct.",
                subject=validation.path,
            )
        return result

    def run(self, fail_fast: bool = False, return_df: bool = False) -> Report:
        """Run all validations and return a report.

        :param fail_fast: If True, stop validation after the first failure.
        :type fail_fast: bool
        :param return_df: If True, return a pandas dataframe instead of a Report object.
        :type return_df: bool
        :return: Report object or pandas dataframe.
        :rtype: Report or dict
        """
        results = []
        for ix, validation in enumerate(self.validations):
            result = validation.run(self.sagemaker_pipeline)
            result = Configuration._handle_empty_results(result, validation)
            results.append(result)
            if (
                not result[validation.name].success
                and fail_fast
                and not (ix == len(self.validations) - 1)
            ):
                logging.info(
                    "Validation failed and fail_fast is set to True. Stopping validation "
                    "prematurely."
                )
                break
        return self._make_report(results, return_df)

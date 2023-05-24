![Test-Build-Workflow](https://github.com/stiebels/sagemaker-rightline/actions/workflows/python-package.yml/badge.svg)

# sagemaker-rightline

This repository contains the source code for sagemaker-rightline, a Python package that eases validation of properties of a SageMaker Pipeline object.

Note that at present this package is in an early stage of development and is not yet ready for production use. We welcome contributions!


## README Content

- [Features](#features)
- [Usage](#usage)
- [Contributing](#contributing)

## Features

### ⚙️ Configuration
The `Configuration` class is responsible for running the `Validations` against the `Pipeline` object and returning a `Report`.
The `Configuration` class is instantiated with a
 - `sagemaker.workflow.pipeline.Pipeline` object, and
 - a list of `Validations`.

### ✔️ Validations
A `Validation` is a class that inherits from the `Validation` base class.
It is responsible for validating a single property of the `Pipeline` object.
We differentiate between `Validations` that check the `Pipeline` object itself (class names beginning with "Pipeline") and `Validations` that check the `Pipeline` object's `Step` objects (class name starting with "Step").

For example, the `StepImagesExistOnEcr` validation checks that all ImageURI that
Steps of the `Pipeline` object reference indeed exist on the target ECR.

The following `Validations` are currently implemented:
  - `PipelineParameters`
  - `StepImagesExistOnEcr`
  - `StepKmsKeyId`

In most cases, a `Validation` subclass requires passing a `Rule` object to its constructor.

### 📜 Rules
A `Rule` is a class that inherits from the `Rule` base class.
It is responsible for defining the rule that a `Validation` checks for.
For example, passing the list of expected KMSKeyIDs and the `Rule` `Equals` to `StepKmsKeyId` will check that
all `Step` objects of the `Pipeline` object have a `KmsKeyId` property that matches the passed KMSKeyIDs.

Note that not all `Validations` require a `Rule` object, e.g. `StepImagesExistOnEcr`.

The following `Rules` are currently implemented:
  - `Equals`
  - `Contains`

### 📝 Report
A `Report` is a class whose instance is returned by the `Configuration` class (optionally a pandas.DataFrame instead).
It contains the results of the `Validations` that were run against the `Pipeline` object as well as additional information
to allow for further analysis.

## Usage
```python
from sagemaker.workflow.parameters import ParameterString
from sagemaker_rightline.model import Configuration
from sagemaker_rightline.rules import Contains, Equals
from sagemaker_rightline.validations import (
    PipelineParameters,
    StepImagesExistOnEcr,
    StepKmsKeyId,
)

# Import a dummy pipeline
from tests.fixtures.pipeline import get_sagemaker_pipeline
sm_pipeline = get_sagemaker_pipeline()

# Define Validations
validations = [
    StepImagesExistOnEcr(),
    PipelineParameters(
        parameters_expected=[
            ParameterString(
                name="parameter-1",
                default_value="some-value",
            ),
        ],
        rule=Contains(),
    ),
    StepKmsKeyId(
        kms_key_id_expected="some/kms-key-alias",
        step_name="output-1",  # optional: if not set, will check all steps
        rule=Equals(),
    ),
]

# Add Validations and SageMaker Pipeline to Configuration
cm = Configuration(
    validations=validations,
    sagemaker_pipeline=sm_pipeline,
)

# Run the full Configuration
df = cm.run()

# Show the report
df
```
![img.png](./docs/report.png)


## Contributing [![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/stiebels/sagemaker-rightline/issues)
Contributions welcome! We'll add a guide shortly.

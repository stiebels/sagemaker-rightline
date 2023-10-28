Usage
=====

Python
------

.. code:: python

   from sagemaker.processing import NetworkConfig, ProcessingInput, ProcessingOutput
   from sagemaker.workflow.parameters import ParameterString
   from sagemaker_rightline.model import Configuration
   from sagemaker_rightline.rules import Contains, Equals
   from sagemaker_rightline.validations import (
       PipelineParametersAsExpected,
       StepImagesExist,
       StepKmsKeyIdAsExpected,
       StepNetworkConfigAsExpected,
       StepLambdaFunctionExists,
       StepRoleNameExists,
       StepRoleNameAsExpected,
       StepTagsAsExpected,
       StepInputsAsExpected,
       StepOutputsAsExpected,
       StepOutputsMatchInputsAsExpected,
       StepCallbackSqsQueueExists,
   )

   # Import a dummy pipeline
   from tests.fixtures.pipeline import get_sagemaker_pipeline, DUMMY_BUCKET

   sm_pipeline = get_sagemaker_pipeline()

   # Define Validations
   validations = [
       StepImagesExist(),
       PipelineParametersAsExpected(
           parameters_expected=[
               ParameterString(
                   name="parameter-1",
                   default_value="some-value",
               ),
           ],
           rule=Contains(),
       ),
       StepKmsKeyIdAsExpected(
           kms_key_id_expected="some/kms-key-alias",
           step_name="sm_training_step_sklearn",  # optional: if not set, will check all steps
           rule=Equals(),
       ),
       StepNetworkConfigAsExpected(
           network_config_expected=NetworkConfig(
               enable_network_isolation=False,
               security_group_ids=["sg-1234567890"],
               subnets=["subnet-1234567890"],
           ),
           rule=Equals(negative=True),
       ),
       StepLambdaFunctionExists(),
       StepRoleNameExists(),
       StepRoleNameAsExpected(
           role_name_expected="some-role-name",
           step_name="sm_training_step_sklearn",  # optional: if not set, will check all steps
           rule=Equals(),
       ),
       StepTagsAsExpected(
           tags_expected=[{
               "some-key": "some-value",
           }],
           step_name="sm_training_step_sklearn",  # optional: if not set, will check all steps
           rule=Equals(),
       ),
       StepInputsAsExpected(
           inputs_expected=[
               ProcessingInput(
                   source=f"s3://{DUMMY_BUCKET}/input-1",
                   destination="/opt/ml/processing/input",
                   input_name="input-2",
               )
           ],
           step_type="Processing",  # either step_type or step_name must be set to filter
           rule=Contains(),
       ),
       StepOutputsAsExpected(
           outputs_expected=[
               ProcessingOutput(
                   source="/opt/ml/processing/output",
                   destination=f"s3://{DUMMY_BUCKET}/output-1",
                   output_name="output-1",
               )
           ],
           step_name="sm_processing_step_spark",  # optional
           rule=Contains(),
       ),
       StepOutputsMatchInputsAsExpected(
           inputs_outputs_expected=[
               {
                   "input": {
                       "step_name": "sm_processing_step_sklearn",
                       "input_name": "input-1",
                   },
                   "output": {
                       "step_name": "sm_processing_step_sklearn",
                       "output_name": "output-1",
                   },
               }
           ]
       ),
       StepCallbackSqsQueueExists(),
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

.. figure:: report.png
   :alt: report.png


Command Line
------------
The `sagemaker-rightline` package can be used as a command line tool.

.. code:: bash

   pip install sagemaker-rightline
   cd <your-project-directory>
   sagemaker-rightline --configuration <relative-path-to-file-containing-get-configuration-function>.py

Try it out in the context of the `sagemaker-rightline` project example:

.. code:: bash

   git clone git@github.com:stiebels/sagemaker-rightline.git
   cd sagemaker-rightline
   pip install -e .
   cd sagemaker_rightline/examples/sm_pipeline_project
   sagemaker-rightline --configuration sm_rightline_config.py


Use the `--help` flag to get an overview of the available options:

.. code:: bash

   $ sagemaker-rightline --help
   Usage: sagemaker-rightline [OPTIONS] COMMAND [ARGS]...

   Options:
     --help  Show this message and exit.
     --configuration Path to the configuration file that holds the get_configuration function, which returns a sagemaker_rightline.model.Configuration object
     --working-dir [OPTIONAL] Path to the working directory. If not set, the current working directory will be used.


Pre-Commit Hook
---------------
To use the `sagemaker-rightline` package as a pre-commit hook, add the following to your `.pre-commit-config.yaml`:

.. code:: yaml
   repos:
   - repo: https://github.com/stiebels/sagemaker-rightline@main
      hooks:
      - id: sagemaker-rightline
        name: sagemaker-rightline
        entry: sagemaker-rightline
        language: system
        types: [python]
        pass_filenames: false
        args: ['--configuration', '<relative-path-to-file-containing-get-configuration-function>.py']

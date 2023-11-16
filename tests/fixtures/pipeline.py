from sagemaker.inputs import FileSystemInput, TrainingInput, TransformInput
from sagemaker.processing import NetworkConfig, ScriptProcessor
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.spark.processing import PySparkProcessor
from sagemaker.transformer import Transformer
from sagemaker.tuner import ContinuousParameter, HyperparameterTuner
from sagemaker.workflow.callback_step import (
    CallbackOutput,
    CallbackOutputTypeEnum,
    CallbackStep,
)
from sagemaker.workflow.functions import Join
from sagemaker.workflow.lambda_step import LambdaStep
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.pipeline import ExecutionVariables, Pipeline
from sagemaker.workflow.steps import (
    ProcessingInput,
    ProcessingOutput,
    ProcessingStep,
    TrainingStep,
    TransformStep,
    TuningStep,
)

from tests.fixtures.constants import (
    TEST_LAMBDA_FUNC_NAME,
    TEST_ROLE_ARN,
    TEST_SQS_QUEUE_URL,
)
from tests.fixtures.image_details import IMAGE_1_URI, IMAGE_2_URI


def arn_formatter(_type: str, _id: str, account_id: str, region_name: str) -> str:
    return f"arn:aws:sagemaker:{region_name}:{account_id}:{_type}/{_id}"


DUMMY_BUCKET = "dummy-bucket"


def get_sagemaker_pipeline(
    script_path: str = "tests/fixtures/fake_processing_script.py",
) -> Pipeline:
    network_config = NetworkConfig(
        enable_network_isolation=True,
        security_group_ids=["sg-12345"],
        subnets=["subnet-12345"],
        encrypt_inter_container_traffic=True,
    )

    sm_processor_sklearn = ScriptProcessor(
        base_job_name="sm_processor",
        role=TEST_ROLE_ARN,
        image_uri=IMAGE_1_URI,
        network_config=network_config,
        tags=[
            {"Key": "some-key", "Value": "some-value"},
            {"Key": "some-key-2", "Value": "some-value-2"},
        ],
    )
    sm_processor_spark = PySparkProcessor(
        base_job_name="sm_processors",
        role=TEST_ROLE_ARN,
        image_uri=IMAGE_2_URI,
        instance_type="ml.m5.xlarge",
        instance_count=2,
        network_config=network_config,
        tags=[{"Key": "some-key", "Value": "some-value"}],
    )
    sm_trainer_sklearn = SKLearn(
        entry_point=script_path,
        role=TEST_ROLE_ARN,
        image_uri=IMAGE_1_URI,
        instance_type="ml.c4.xlarge",
        output_kms_key="some/kms-key-alias",
        enable_network_isolation=network_config.enable_network_isolation,
        security_group_ids=network_config.security_group_ids,
        subnets=network_config.subnets,
        encrypt_inter_container_traffic=network_config.encrypt_inter_container_traffic,
        tags=[
            {"Key": "some-key", "Value": "some-value"},
            {
                "Key": "some-key",
                "Value": ParameterString(name="parameter-1", default_value="some-value-1"),
            },
        ],
    )

    sm_processing_step_sklearn = ProcessingStep(
        name="sm_processing_step_sklearn",
        ste_args=sm_processor_sklearn.run(
            code=script_path,
            inputs=[
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/output-1",
                    destination="/opt/ml/processing/input",
                    input_name="input-1",
                ),
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/input-2",
                    destination="/opt/ml/processing/input",
                    input_name="input-2",
                ),
            ],
            outputs=[
                ProcessingOutput(
                    output_name="output-1",
                    source="/opt/ml/processing/output/1",
                    destination=f"s3://{DUMMY_BUCKET}/output-1",
                ),
                ProcessingOutput(
                    output_name="output-2",
                    source="/opt/ml/processing/output/2",
                    destination=f"s3://{DUMMY_BUCKET}/output-2",
                ),
                ProcessingOutput(
                    output_name="output-3",
                    source="/opt/ml/processing/output/3",
                    destination=Join(
                        on="/",
                        values=[
                            "s3:/",
                            DUMMY_BUCKET,
                            ExecutionVariables.PIPELINE_EXECUTION_ID,
                            "output-3",
                        ],
                    ),
                ),
            ],
            kms_key="some/kms-key-alias",
        ),
    )

    sm_processing_step_spark = ProcessingStep(
        name="sm_processing_step_spark",
        step_args=sm_processor_spark.run(
            code=script_path,
            kms_key="some/kms-key-alias",
            inputs=[
                ProcessingInput(
                    source=sm_processing_step_sklearn.outputs,
                    destination="/opt/ml/processing/input",
                    input_name="input-1",
                ),
                ProcessingInput(
                    source=f"s3://{DUMMY_BUCKET}/input-2",
                    destination="/opt/ml/processing/input",
                    input_name="input-2",
                ),
                ProcessingInput(
                    source=Join(
                        on="/",
                        values=[
                            "s3:/",
                            DUMMY_BUCKET,
                            ExecutionVariables.PIPELINE_EXECUTION_ID,
                            "output-3",
                        ],
                    ),
                    destination="/opt/ml/processing/input",
                    input_name="input-3",
                ),
            ],
            outputs=[
                ProcessingOutput(
                    output_name="output-1",
                    source="/opt/ml/processing/output/1",
                    destination=f"s3://{DUMMY_BUCKET}/output-3",
                ),
                ProcessingOutput(
                    output_name="output-2",
                    source="/opt/ml/processing/output/2",
                    destination=f"s3://{DUMMY_BUCKET}/output-4",
                ),
            ],
        ),
        depends_on=[sm_processing_step_sklearn.name],
    )

    sm_training_step_sklearn = TrainingStep(
        name="sm_training_step_sklearn",
        estimator=sm_trainer_sklearn,
        depends_on=[sm_processing_step_spark.name],
        inputs={
            "train": TrainingInput(
                s3_data=f"s3://{DUMMY_BUCKET}/output-4",
                content_type="text/csv",
            ),
            "some-key": "some-value",
            "validation": FileSystemInput(
                file_system_id="fs-1234",
                file_system_type="EFS",
                directory_path="/some/path",
                file_system_access_mode="ro",
            ),
        },
    )

    sm_tuning_step = TuningStep(
        name="sm_tuning_step",
        depends_on=[sm_processing_step_spark.name],
        inputs={
            "train": TrainingInput(
                s3_data=f"s3://{DUMMY_BUCKET}/output-4",
                content_type="text/csv",
            ),
            "some-key": "some-value",
            "validation": FileSystemInput(
                file_system_id="fs-1234",
                file_system_type="EFS",
                directory_path="/some/path",
                file_system_access_mode="ro",
            ),
        },
        tuner=HyperparameterTuner(
            estimator=sm_trainer_sklearn,
            objective_metric_name="some-metric",
            hyperparameter_ranges={
                "some-hp": ContinuousParameter(0, 1),
            },
            metric_definitions=[
                {"Name": "some-metric", "Regex": "some-regex"},
            ],
            max_jobs=2,
            max_parallel_jobs=2,
        ),
    )

    transformer = Transformer(
        model_name=sm_training_step_sklearn.properties.ModelArtifacts.S3ModelArtifacts,
        instance_count=1,
        instance_type="ml.m5.xlarge",
        output_kms_key="some/kms-key-alias",
        output_path=f"s3://{DUMMY_BUCKET}/transformer-output",
    )

    sm_transform_step = TransformStep(
        name="sm_transform_step",
        transformer=transformer,
        inputs=TransformInput(
            data=f"s3://{DUMMY_BUCKET}/output-4",
        ),
        depends_on=[sm_tuning_step.name],
    )

    sm_lambda_step = LambdaStep(
        name="sm_lambda_step",
        lambda_func=TEST_LAMBDA_FUNC_NAME,
        depends_on=[sm_transform_step.name],
    )

    sm_callback_step = CallbackStep(
        name="sm_callback_step",
        inputs={
            "some": "input",
        },
        outputs=[CallbackOutput(output_name="output1", output_type=CallbackOutputTypeEnum.String)],
        sqs_queue_url=TEST_SQS_QUEUE_URL,
        depends_on=[sm_lambda_step.name],
    )

    sm_pipeline = Pipeline(
        name="dummy-pipeline",
        steps=[
            sm_processing_step_sklearn,
            sm_processing_step_spark,
            sm_training_step_sklearn,
            sm_tuning_step,
            sm_transform_step,
            sm_lambda_step,
            sm_callback_step,
        ],
        parameters=[
            ParameterString(
                name="parameter-1",
                default_value="some-value-1",
            ),
            ParameterString(
                name="parameter-2",
                default_value="some-value-2",
            ),
        ],
    )
    return sm_pipeline

from sagemaker.inputs import FileSystemInput, TrainingInput
from sagemaker.processing import NetworkConfig, ScriptProcessor
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.spark.processing import PySparkProcessor
from sagemaker.workflow.lambda_step import LambdaStep
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import (
    ProcessingInput,
    ProcessingOutput,
    ProcessingStep,
    TrainingStep,
)

from tests.fixtures.constants import TEST_LAMBDA_FUNC_NAME, TEST_ROLE_ARN
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
        code=script_path,
        processor=sm_processor_sklearn,
        kms_key="some/kms-key-alias",
        inputs=[
            ProcessingInput(
                source=f"s3://{DUMMY_BUCKET}/input-1",
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
        ],
    )

    sm_processing_step_spark = ProcessingStep(
        name="sm_processing_step_spark",
        code=script_path,
        processor=sm_processor_spark,
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
        depends_on=[sm_processing_step_sklearn.name],
    )

    sm_training_step_sklearn = TrainingStep(
        name="sm_training_step_sklearn",
        estimator=sm_trainer_sklearn,
        depends_on=[sm_processing_step_spark.name],
        inputs={
            "train": TrainingInput(
                s3_data=f"s3://{DUMMY_BUCKET}/some-prefix/validation",
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

    sm_lambda_step = LambdaStep(
        name="sm_lambda_step",
        lambda_func=TEST_LAMBDA_FUNC_NAME,
        depends_on=[sm_training_step_sklearn.name],
    )

    sm_pipeline = Pipeline(
        name="dummy-pipeline",
        steps=[
            sm_processing_step_sklearn,
            sm_processing_step_spark,
            sm_training_step_sklearn,
            sm_lambda_step,
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

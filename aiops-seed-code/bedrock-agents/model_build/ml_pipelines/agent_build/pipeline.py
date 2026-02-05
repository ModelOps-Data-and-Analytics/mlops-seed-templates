"""SageMaker Pipeline for building Amazon Bedrock Agents.

This pipeline orchestrates the complete lifecycle of creating, configuring,
and evaluating a Bedrock Agent with optional Knowledge Base and Action Groups.
"""

import os
from typing import Optional

import boto3
import sagemaker
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.workflow.fail_step import FailStep
from sagemaker.workflow.functions import JsonGet
from sagemaker.workflow.parameters import ParameterFloat, ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.steps import ProcessingStep


def get_pipeline(
    region: str,
    role: Optional[str] = None,
    default_bucket: Optional[str] = None,
    pipeline_name: str = "BedrockAgentPipeline",
    base_job_prefix: str = "BedrockAgent",
    agent_name: str = "customer-service-agent",
    project_id: str = "default-project",
    model_package_group_name: Optional[str] = None,
    bucket_kms_id: Optional[str] = None,
    sagemaker_session: Optional[sagemaker.Session] = None,
    foundation_model: str = "anthropic.claude-3-7-sonnet-20250219-v1:0",
) -> Pipeline:
    """Creates a SageMaker Pipeline for building Bedrock Agents.

    Args:
        region: AWS region for pipeline execution
        role: IAM role ARN for SageMaker
        default_bucket: S3 bucket for artifacts
        pipeline_name: Name of the pipeline
        base_job_prefix: Prefix for job names
        agent_name: Name for the Bedrock agent
        project_id: SMUS project ID
        model_package_group_name: Model registry group name
        bucket_kms_id: KMS key for S3 encryption
        sagemaker_session: SageMaker session
        foundation_model: Foundation model ID

    Returns:
        SageMaker Pipeline instance
    """
    # Initialize session if not provided
    if sagemaker_session is None:
        boto_session = boto3.Session(region_name=region)
        sagemaker_session = sagemaker.Session(boto_session=boto_session)

    if role is None:
        role = sagemaker.get_execution_role(sagemaker_session=sagemaker_session)

    if default_bucket is None:
        default_bucket = sagemaker_session.default_bucket()

    if model_package_group_name is None:
        model_package_group_name = f"aiops-{project_id}-agents"

    # ==========================================================================
    # Pipeline Parameters
    # ==========================================================================
    param_agent_name = ParameterString(
        name="AgentName",
        default_value=agent_name
    )
    param_foundation_model = ParameterString(
        name="FoundationModel",
        default_value=foundation_model
    )
    param_processing_instance_type = ParameterString(
        name="ProcessingInstanceType",
        default_value="ml.m5.xlarge"
    )
    param_processing_instance_count = ParameterInteger(
        name="ProcessingInstanceCount",
        default_value=1
    )
    param_model_approval_status = ParameterString(
        name="ModelApprovalStatus",
        default_value="PendingManualApproval"
    )
    param_enable_knowledge_base = ParameterString(
        name="EnableKnowledgeBase",
        default_value="true"
    )
    param_enable_action_groups = ParameterString(
        name="EnableActionGroups",
        default_value="true"
    )
    param_evaluation_threshold = ParameterFloat(
        name="EvaluationThreshold",
        default_value=0.8
    )
    param_knowledge_base_s3_uri = ParameterString(
        name="KnowledgeBaseS3Uri",
        default_value=f"s3://{default_bucket}/{base_job_prefix}/knowledge-base-data/"
    )
    # Parámetros de ingesta de Knowledge Base
    param_kb_max_tokens = ParameterInteger(
        name="KBChunkMaxTokens",
        default_value=1024
    )
    param_kb_overlap_percentage = ParameterInteger(
        name="KBChunkOverlapPercentage",
        default_value=20
    )
    param_kb_ingestion_timeout = ParameterInteger(
        name="KBIngestionTimeoutMinutes",
        default_value=30
    )
    param_skip_kb_ingestion = ParameterString(
        name="SkipKBIngestion",
        default_value="false"
    )

    # ==========================================================================
    # Processing Image
    # ==========================================================================
    processing_image_uri = sagemaker.image_uris.retrieve(
        framework="sklearn",
        region=region,
        version="1.2-1",
        py_version="py3",
        instance_type="ml.m5.xlarge",
    )

    # ==========================================================================
    # Step 1: Setup and Validation
    # ==========================================================================
    setup_processor = ScriptProcessor(
        image_uri=processing_image_uri,
        instance_type=param_processing_instance_type,
        instance_count=param_processing_instance_count,
        base_job_name=f"{base_job_prefix}/setup",
        command=["python3"],
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )

    step_setup = ProcessingStep(
        name="SetupAndValidation",
        processor=setup_processor,
        inputs=[
            ProcessingInput(
                source=f"s3://{default_bucket}/{base_job_prefix}/config/",
                destination="/opt/ml/processing/input/config",
                input_name="config"
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="setup_output",
                source="/opt/ml/processing/output",
                destination=f"s3://{default_bucket}/{base_job_prefix}/setup-output/"
            ),
        ],
        code="source_scripts/setup/main.py",
        job_arguments=[
            "--agent-name", param_agent_name,
            "--foundation-model", param_foundation_model,
            "--region", region,
        ],
    )

    # ==========================================================================
    # Step 2: Create/Update Bedrock Agent
    # ==========================================================================
    create_agent_processor = ScriptProcessor(
        image_uri=processing_image_uri,
        instance_type=param_processing_instance_type,
        instance_count=param_processing_instance_count,
        base_job_name=f"{base_job_prefix}/create-agent",
        command=["python3"],
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )

    # Property file to capture agent outputs
    agent_output_property_file = PropertyFile(
        name="AgentOutput",
        output_name="agent_output",
        path="agent_output.json"
    )

    step_create_agent = ProcessingStep(
        name="CreateBedrockAgent",
        processor=create_agent_processor,
        inputs=[
            ProcessingInput(
                source=f"s3://{default_bucket}/{base_job_prefix}/config/",
                destination="/opt/ml/processing/input/config",
                input_name="config"
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="agent_output",
                source="/opt/ml/processing/output",
                destination=f"s3://{default_bucket}/{base_job_prefix}/agent-output/"
            ),
        ],
        code="source_scripts/create_agent/main.py",
        job_arguments=[
            "--agent-name", param_agent_name,
            "--foundation-model", param_foundation_model,
            "--region", region,
            "--role-arn", role,
        ],
        property_files=[agent_output_property_file],
    )
    step_create_agent.add_depends_on([step_setup])

    # ==========================================================================
    # Step 3: Create Knowledge Base
    # ==========================================================================
    create_kb_processor = ScriptProcessor(
        image_uri=processing_image_uri,
        instance_type=param_processing_instance_type,
        instance_count=param_processing_instance_count,
        base_job_name=f"{base_job_prefix}/create-kb",
        command=["python3"],
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )

    kb_output_property_file = PropertyFile(
        name="KBOutput",
        output_name="kb_output",
        path="kb_output.json"
    )

    step_create_kb = ProcessingStep(
        name="CreateKnowledgeBase",
        processor=create_kb_processor,
        inputs=[
            ProcessingInput(
                source=f"s3://{default_bucket}/{base_job_prefix}/config/",
                destination="/opt/ml/processing/input/config",
                input_name="config"
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="kb_output",
                source="/opt/ml/processing/output",
                destination=f"s3://{default_bucket}/{base_job_prefix}/kb-output/"
            ),
        ],
        code="source_scripts/knowledge_base/main.py",
        job_arguments=[
            "--agent-name", param_agent_name,
            "--s3-uri", param_knowledge_base_s3_uri,
            "--region", region,
            "--enable", param_enable_knowledge_base,
            "--max-tokens", param_kb_max_tokens,
            "--overlap-percentage", param_kb_overlap_percentage,
            "--ingestion-timeout", param_kb_ingestion_timeout,
        ],
        property_files=[kb_output_property_file],
    )
    step_create_kb.add_depends_on([step_create_agent])

    # ==========================================================================
    # Step 4: Deploy Action Groups
    # ==========================================================================
    deploy_actions_processor = ScriptProcessor(
        image_uri=processing_image_uri,
        instance_type=param_processing_instance_type,
        instance_count=param_processing_instance_count,
        base_job_name=f"{base_job_prefix}/deploy-actions",
        command=["python3"],
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )

    actions_output_property_file = PropertyFile(
        name="ActionsOutput",
        output_name="actions_output",
        path="actions_output.json"
    )

    step_deploy_actions = ProcessingStep(
        name="DeployActionGroups",
        processor=deploy_actions_processor,
        inputs=[
            ProcessingInput(
                source=f"s3://{default_bucket}/{base_job_prefix}/config/",
                destination="/opt/ml/processing/input/config",
                input_name="config"
            ),
            ProcessingInput(
                source=f"s3://{default_bucket}/{base_job_prefix}/lambda-packages/",
                destination="/opt/ml/processing/input/lambdas",
                input_name="lambdas"
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="actions_output",
                source="/opt/ml/processing/output",
                destination=f"s3://{default_bucket}/{base_job_prefix}/actions-output/"
            ),
        ],
        code="source_scripts/action_groups/main.py",
        job_arguments=[
            "--agent-name", param_agent_name,
            "--region", region,
            "--enable", param_enable_action_groups,
        ],
        property_files=[actions_output_property_file],
    )
    step_deploy_actions.add_depends_on([step_create_kb])

    # ==========================================================================
    # Step 5: Prepare Agent
    # ==========================================================================
    prepare_agent_processor = ScriptProcessor(
        image_uri=processing_image_uri,
        instance_type=param_processing_instance_type,
        instance_count=param_processing_instance_count,
        base_job_name=f"{base_job_prefix}/prepare-agent",
        command=["python3"],
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )

    prepare_output_property_file = PropertyFile(
        name="PrepareOutput",
        output_name="prepare_output",
        path="prepare_output.json"
    )

    step_prepare_agent = ProcessingStep(
        name="PrepareAgent",
        processor=prepare_agent_processor,
        outputs=[
            ProcessingOutput(
                output_name="prepare_output",
                source="/opt/ml/processing/output",
                destination=f"s3://{default_bucket}/{base_job_prefix}/prepare-output/"
            ),
        ],
        code="source_scripts/prepare_agent/main.py",
        job_arguments=[
            "--agent-name", param_agent_name,
            "--region", region,
        ],
        property_files=[prepare_output_property_file],
    )
    step_prepare_agent.add_depends_on([step_deploy_actions])

    # ==========================================================================
    # Step 6: Evaluate Agent
    # ==========================================================================
    evaluate_processor = ScriptProcessor(
        image_uri=processing_image_uri,
        instance_type=param_processing_instance_type,
        instance_count=param_processing_instance_count,
        base_job_name=f"{base_job_prefix}/evaluate",
        command=["python3"],
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )

    evaluation_report = PropertyFile(
        name="EvaluationReport",
        output_name="evaluation",
        path="evaluation.json"
    )

    step_evaluate = ProcessingStep(
        name="EvaluateAgent",
        processor=evaluate_processor,
        inputs=[
            ProcessingInput(
                source=f"s3://{default_bucket}/{base_job_prefix}/test-cases/",
                destination="/opt/ml/processing/input/test_cases",
                input_name="test_cases"
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="evaluation",
                source="/opt/ml/processing/output",
                destination=f"s3://{default_bucket}/{base_job_prefix}/evaluation/"
            ),
        ],
        code="source_scripts/evaluate/main.py",
        job_arguments=[
            "--agent-name", param_agent_name,
            "--region", region,
            "--threshold", param_evaluation_threshold,
        ],
        property_files=[evaluation_report],
    )
    step_evaluate.add_depends_on([step_prepare_agent])

    # ==========================================================================
    # Step 7: Condition - Check Evaluation Results
    # ==========================================================================
    condition_eval_passed = ConditionGreaterThanOrEqualTo(
        left=JsonGet(
            step_name=step_evaluate.name,
            property_file=evaluation_report,
            json_path="metrics.success_rate"
        ),
        right=param_evaluation_threshold
    )

    # ==========================================================================
    # Step 8: Register Agent in Model Registry
    # ==========================================================================
    register_processor = ScriptProcessor(
        image_uri=processing_image_uri,
        instance_type=param_processing_instance_type,
        instance_count=1,
        base_job_name=f"{base_job_prefix}/register",
        command=["python3"],
        sagemaker_session=sagemaker_session,
        role=role,
        output_kms_key=bucket_kms_id,
    )

    step_register = ProcessingStep(
        name="RegisterAgentModel",
        processor=register_processor,
        outputs=[
            ProcessingOutput(
                output_name="register_output",
                source="/opt/ml/processing/output",
                destination=f"s3://{default_bucket}/{base_job_prefix}/register-output/"
            ),
        ],
        code="source_scripts/register/main.py",
        job_arguments=[
            "--agent-name", param_agent_name,
            "--model-package-group-name", model_package_group_name,
            "--approval-status", param_model_approval_status,
            "--region", region,
        ],
    )

    # ==========================================================================
    # Fail Step
    # ==========================================================================
    step_fail = FailStep(
        name="EvaluationFailed",
        error_message="Agent evaluation did not meet the required threshold. Please review test results and improve the agent configuration."
    )

    # ==========================================================================
    # Condition Step
    # ==========================================================================
    step_condition = ConditionStep(
        name="CheckEvaluationResults",
        conditions=[condition_eval_passed],
        if_steps=[step_register],
        else_steps=[step_fail],
    )
    step_condition.add_depends_on([step_evaluate])

    # ==========================================================================
    # Create Pipeline
    # ==========================================================================
    pipeline = Pipeline(
        name=pipeline_name,
        parameters=[
            param_agent_name,
            param_foundation_model,
            param_processing_instance_type,
            param_processing_instance_count,
            param_model_approval_status,
            param_enable_knowledge_base,
            param_enable_action_groups,
            param_evaluation_threshold,
            param_knowledge_base_s3_uri,
            # Parámetros de ingesta KB
            param_kb_max_tokens,
            param_kb_overlap_percentage,
            param_kb_ingestion_timeout,
            param_skip_kb_ingestion,
        ],
        steps=[
            step_setup,
            step_create_agent,
            step_create_kb,
            step_deploy_actions,
            step_prepare_agent,
            step_evaluate,
            step_condition,
        ],
        sagemaker_session=sagemaker_session,
    )

    return pipeline

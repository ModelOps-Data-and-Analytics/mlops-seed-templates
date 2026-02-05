"""Runs the SageMaker Pipeline for Bedrock Agents."""
import argparse
import json
import logging
import os
import sys

import boto3
import sagemaker

from sagemaker.workflow.pipeline import Pipeline
from ml_pipelines.agent_build.pipeline import get_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_role_arn(region: str) -> str:
    """Get SageMaker execution role ARN from SSM or environment."""
    # First check environment variable
    role_from_env = os.environ.get('SAGEMAKER_EXECUTION_ROLE')
    if role_from_env:
        return role_from_env
    
    # Try SSM parameter
    try:
        ssm = boto3.client('ssm', region_name=region)
        response = ssm.get_parameter(Name='/sagemaker/execution-role')
        return response['Parameter']['Value']
    except Exception:
        pass
    
    # Try SageMaker default role discovery (works in SageMaker environments)
    try:
        return sagemaker.get_execution_role()
    except Exception:
        pass
    
    # For GitHub Actions, use SageMaker Domain Execution role
    try:
        account_id = boto3.client('sts', region_name=region).get_caller_identity()['Account']
        # Use standard SageMaker Domain Execution role
        return f"arn:aws:iam::{account_id}:role/service-role/AmazonSageMakerAdminIAMExecutionRole"
    except Exception as e:
        raise RuntimeError(f"Could not determine SageMaker execution role: {e}")


def main():
    parser = argparse.ArgumentParser(description="Run SageMaker Pipeline for Bedrock Agents")
    
    # Primary arguments matching workflow
    parser.add_argument("--agent-name", type=str, required=True,
                        help="Name of the Bedrock agent")
    parser.add_argument("--environment", type=str, default="dev",
                        help="Environment (dev/staging/prod)")
    parser.add_argument("--foundation-model", type=str, 
                        default="anthropic.claude-3-7-sonnet-20250219-v1:0",
                        help="Foundation model ID")
    parser.add_argument("--region", type=str, default="us-east-1",
                        help="AWS region")
    
    # Optional arguments
    parser.add_argument("--role-arn", type=str, default=None,
                        help="IAM role ARN for SageMaker (auto-detected if not provided)")
    parser.add_argument("--pipeline-name", type=str, default=None,
                        help="Override pipeline name")
    parser.add_argument("--project-id", type=str, default=None,
                        help="SMUS project ID")
    parser.add_argument("--tags", type=str, default=None,
                        help="JSON string of tags for pipeline")
    parser.add_argument("--wait", action="store_true", default=True,
                        help="Wait for pipeline execution to complete")
    parser.add_argument("--log-level", type=str, default="INFO",
                        help="Logging level")
    
    args = parser.parse_args()
    
    # Configure logging
    level = logging.getLevelName(args.log_level.upper())
    logger.setLevel(level)
    
    logger.info(f"Starting pipeline for agent: {args.agent_name}")
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Region: {args.region}")
    logger.info(f"Foundation Model: {args.foundation_model}")
    
    # Get role ARN
    role_arn = args.role_arn or get_role_arn(args.region)
    logger.info(f"Using role: {role_arn}")
    
    # Parse tags
    tags = json.loads(args.tags) if args.tags else [
        {"Key": "Environment", "Value": args.environment},
        {"Key": "AgentName", "Value": args.agent_name},
        {"Key": "ManagedBy", "Value": "SageMaker-Pipelines"}
    ]
    
    # Determine pipeline name
    pipeline_name = args.pipeline_name or f"bedrock-agent-{args.agent_name}-{args.environment}"
    
    # Get project ID from environment or argument
    project_id = args.project_id or os.environ.get('SAGEMAKER_PROJECT_ID', 'genai-agents')
    
    # Create pipeline
    logger.info("Creating pipeline definition...")
    try:
        pipeline = get_pipeline(
            region=args.region,
            role=role_arn,
            pipeline_name=pipeline_name,
            agent_name=args.agent_name,
            project_id=project_id,
            foundation_model=args.foundation_model,
        )
    except Exception as e:
        logger.error(f"Failed to create pipeline: {e}")
        raise
    
    # Upsert (create or update) the pipeline
    logger.info(f"Creating/updating pipeline: {pipeline.name}")
    try:
        pipeline.upsert(role_arn=role_arn, tags=tags)
    except Exception as e:
        logger.error(f"Failed to upsert pipeline: {e}")
        raise
    
    # Start pipeline execution
    logger.info("Starting pipeline execution...")
    try:
        execution = pipeline.start()
        logger.info(f"Pipeline execution started: {execution.arn}")
    except Exception as e:
        logger.error(f"Failed to start pipeline: {e}")
        raise
    
    if args.wait:
        logger.info("Waiting for pipeline execution to complete...")
        try:
            execution.wait()
            
            # Get execution status
            description = execution.describe()
            status = description.get('PipelineExecutionStatus', 'Unknown')
            
            logger.info(f"Pipeline execution completed with status: {status}")
            
            if status != 'Succeeded':
                logger.error(f"Pipeline execution failed: {description}")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error waiting for pipeline: {e}")
            raise
    
    logger.info(f"Pipeline {pipeline.name} successfully created/updated and started")
    
    # Output execution ARN for downstream use
    print(f"EXECUTION_ARN={execution.arn}")


if __name__ == "__main__":
    main()

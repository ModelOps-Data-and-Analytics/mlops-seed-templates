"""Runs the SageMaker Pipeline for Bedrock Agents."""
import argparse
import json
import logging
import os
import sys

import boto3
import sagemaker

from sagemaker.workflow.pipeline import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run SageMaker Pipeline for Bedrock Agents")
    parser.add_argument("--module-name", type=str, required=True,
                        help="Python module containing get_pipeline function")
    parser.add_argument("--role-arn", type=str, required=True,
                        help="IAM role ARN for SageMaker")
    parser.add_argument("--tags", type=str, default=None,
                        help="JSON string of tags for pipeline")
    parser.add_argument("--kwargs", type=str, default=None,
                        help="JSON string of kwargs for get_pipeline")
    parser.add_argument("--pipeline-name", type=str, default=None,
                        help="Override pipeline name")
    parser.add_argument("--log-level", type=str, default=None,
                        help="Logging level")
    parser.add_argument("--wait", action="store_true",
                        help="Wait for pipeline execution to complete")
    
    args = parser.parse_args()
    
    if args.log_level:
        level = logging.getLevelName(args.log_level.upper())
        logger.setLevel(level)
    
    # Parse tags
    tags = json.loads(args.tags) if args.tags else []
    
    # Import the pipeline module
    try:
        module = __import__(args.module_name, fromlist=["get_pipeline"])
        get_pipeline = getattr(module, "get_pipeline")
    except Exception as e:
        logger.error(f"Failed to import module {args.module_name}: {e}")
        sys.exit(1)
    
    # Parse kwargs
    kwargs = json.loads(args.kwargs) if args.kwargs else {}
    
    # Get the pipeline
    logger.info("Getting pipeline definition...")
    pipeline = get_pipeline(**kwargs)
    
    # Override pipeline name if provided
    if args.pipeline_name:
        pipeline.name = args.pipeline_name
    
    # Upsert (create or update) the pipeline
    logger.info(f"Creating/updating pipeline: {pipeline.name}")
    pipeline.upsert(role_arn=args.role_arn, tags=tags)
    
    # Start pipeline execution
    logger.info("Starting pipeline execution...")
    execution = pipeline.start()
    
    logger.info(f"Pipeline execution started: {execution.arn}")
    
    if args.wait:
        logger.info("Waiting for pipeline execution to complete...")
        execution.wait()
        
        # Get execution status
        description = execution.describe()
        status = description.get('PipelineExecutionStatus', 'Unknown')
        
        logger.info(f"Pipeline execution completed with status: {status}")
        
        if status != 'Succeeded':
            logger.error(f"Pipeline execution failed: {description}")
            sys.exit(1)
    
    logger.info(f"Pipeline {pipeline.name} successfully created/updated and started")
    
    # Output execution ARN for downstream use
    print(f"EXECUTION_ARN={execution.arn}")


if __name__ == "__main__":
    main()

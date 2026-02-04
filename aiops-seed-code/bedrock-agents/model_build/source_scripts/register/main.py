"""Register Bedrock Agent in SageMaker Model Registry."""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_agent_by_name(bedrock_agent_client, agent_name: str) -> dict | None:
    """Get agent by name."""
    try:
        response = bedrock_agent_client.list_agents()
        for agent in response.get('agentSummaries', []):
            if agent['agentName'] == agent_name:
                # Get full agent details
                agent_details = bedrock_agent_client.get_agent(agentId=agent['agentId'])
                return agent_details['agent']
    except ClientError as e:
        logger.error(f"Error getting agent: {e}")
    return None


def get_agent_alias(bedrock_agent_client, agent_id: str, alias_name: str = "staging") -> dict | None:
    """Get agent alias by name."""
    try:
        response = bedrock_agent_client.list_agent_aliases(agentId=agent_id)
        for alias in response.get('agentAliasSummaries', []):
            if alias['agentAliasName'] == alias_name:
                return alias
    except ClientError as e:
        logger.error(f"Error getting alias: {e}")
    return None


def ensure_model_package_group(sm_client, group_name: str) -> str:
    """Ensure model package group exists.
    
    Args:
        sm_client: SageMaker client
        group_name: Model package group name
        
    Returns:
        Group ARN
    """
    try:
        response = sm_client.describe_model_package_group(
            ModelPackageGroupName=group_name
        )
        logger.info(f"Using existing model package group: {group_name}")
        return response['ModelPackageGroupArn']
    except sm_client.exceptions.ClientError:
        pass
    
    # Create new group
    logger.info(f"Creating model package group: {group_name}")
    response = sm_client.create_model_package_group(
        ModelPackageGroupName=group_name,
        ModelPackageGroupDescription="Bedrock Agents model package group"
    )
    
    return response['ModelPackageGroupArn']


def register_agent_model(
    sm_client,
    group_name: str,
    agent_id: str,
    agent_alias_id: str,
    agent_arn: str,
    foundation_model: str,
    approval_status: str,
    evaluation_metrics: dict = None
) -> str:
    """Register agent as model in SageMaker Model Registry.
    
    Args:
        sm_client: SageMaker client
        group_name: Model package group name
        agent_id: Bedrock Agent ID
        agent_alias_id: Agent alias ID
        agent_arn: Agent ARN
        foundation_model: Foundation model ID
        approval_status: Approval status
        evaluation_metrics: Evaluation metrics
        
    Returns:
        Model package ARN
    """
    logger.info(f"Registering agent model in group: {group_name}")
    
    # Create model package
    # Note: For Bedrock Agents, we use a custom approach since there's no
    # traditional model artifact. We store agent metadata as model properties.
    
    model_metrics = None
    if evaluation_metrics:
        model_metrics = {
            "ModelQuality": {
                "Statistics": {
                    "ContentType": "application/json",
                    "S3Uri": "s3://placeholder/metrics.json"  # In production, upload actual metrics
                }
            }
        }
    
    # Custom metadata for Bedrock Agent
    customer_metadata = {
        "agent_id": agent_id,
        "agent_alias_id": agent_alias_id,
        "agent_arn": agent_arn,
        "foundation_model": foundation_model,
        "agent_type": "bedrock_agent",
        "registration_timestamp": datetime.utcnow().isoformat()
    }
    
    if evaluation_metrics:
        customer_metadata["success_rate"] = str(evaluation_metrics.get("success_rate", 0))
        customer_metadata["total_tests"] = str(evaluation_metrics.get("total_tests", 0))
    
    response = sm_client.create_model_package(
        ModelPackageGroupName=group_name,
        ModelPackageDescription=f"Bedrock Agent: {agent_id}",
        ModelApprovalStatus=approval_status,
        CustomerMetadataProperties=customer_metadata,
        # For Bedrock Agents, we use inference specification with container
        # In production, this would point to an inference container that invokes the agent
        InferenceSpecification={
            "Containers": [
                {
                    "Image": "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.0.0-cpu-py310",
                    "ModelDataUrl": f"s3://sagemaker-placeholder/bedrock-agents/{agent_id}/model.tar.gz",
                    "Environment": {
                        "BEDROCK_AGENT_ID": agent_id,
                        "BEDROCK_AGENT_ALIAS_ID": agent_alias_id
                    }
                }
            ],
            "SupportedContentTypes": ["application/json"],
            "SupportedResponseMIMETypes": ["application/json"]
        }
    )
    
    model_package_arn = response['ModelPackageArn']
    logger.info(f"Registered model package: {model_package_arn}")
    
    return model_package_arn


def main():
    parser = argparse.ArgumentParser(description="Register Bedrock Agent in Model Registry")
    parser.add_argument("--agent-name", type=str, required=True)
    parser.add_argument("--model-package-group-name", type=str, required=True)
    parser.add_argument("--approval-status", type=str, default="PendingManualApproval")
    parser.add_argument("--region", type=str, required=True)
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Registering Bedrock Agent in Model Registry")
    logger.info("=" * 60)
    
    bedrock_agent = boto3.client('bedrock-agent', region_name=args.region)
    sm_client = boto3.client('sagemaker', region_name=args.region)
    
    output = {
        "agent_name": args.agent_name,
        "model_package_group": args.model_package_group_name,
        "model_package_arn": None,
        "status": "unknown"
    }
    
    try:
        # Get agent details
        agent = get_agent_by_name(bedrock_agent, args.agent_name)
        if not agent:
            raise Exception(f"Agent not found: {args.agent_name}")
        
        agent_id = agent['agentId']
        agent_arn = agent['agentArn']
        foundation_model = agent.get('foundationModel', 'unknown')
        
        output["agent_id"] = agent_id
        output["agent_arn"] = agent_arn
        output["foundation_model"] = foundation_model
        
        # Get alias
        alias = get_agent_alias(bedrock_agent, agent_id, "staging")
        agent_alias_id = alias['agentAliasId'] if alias else "TSTALIASID"
        output["agent_alias_id"] = agent_alias_id
        
        # Load evaluation metrics if available
        eval_metrics = None
        eval_path = "/opt/ml/processing/input/evaluation/evaluation.json"
        if os.path.exists(eval_path):
            with open(eval_path, 'r') as f:
                eval_data = json.load(f)
                eval_metrics = eval_data.get("metrics", {})
        
        # Ensure model package group exists
        group_arn = ensure_model_package_group(sm_client, args.model_package_group_name)
        output["model_package_group_arn"] = group_arn
        
        # Register agent model
        model_package_arn = register_agent_model(
            sm_client,
            args.model_package_group_name,
            agent_id,
            agent_alias_id,
            agent_arn,
            foundation_model,
            args.approval_status,
            eval_metrics
        )
        
        output["model_package_arn"] = model_package_arn
        output["approval_status"] = args.approval_status
        output["status"] = "registered"
        
        logger.info(f"Agent registered successfully")
        logger.info(f"Model Package ARN: {model_package_arn}")
        logger.info(f"Approval Status: {args.approval_status}")
        
    except Exception as e:
        logger.error(f"Error registering agent: {e}")
        output["status"] = "error"
        output["error"] = str(e)
    
    # Write output
    output_dir = "/opt/ml/processing/output"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "register_output.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Register output written to {output_path}")
    logger.info("=" * 60)
    logger.info(f"Registration completed: {output['status']}")
    logger.info("=" * 60)
    
    if output["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()

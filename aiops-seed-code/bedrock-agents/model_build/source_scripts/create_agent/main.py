"""Create or update Amazon Bedrock Agent."""
import argparse
import json
import logging
import os
import subprocess
import sys
import time

# Install boto3 with Bedrock support (container may have old version)
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "boto3>=1.34.0", "botocore>=1.34.0"])

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_existing_agent(bedrock_agent_client, agent_name: str) -> dict | None:
    """Check if agent already exists.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_name: Name of the agent
        
    Returns:
        Agent details if exists, None otherwise
    """
    try:
        response = bedrock_agent_client.list_agents()
        for agent in response.get('agentSummaries', []):
            if agent['agentName'] == agent_name:
                logger.info(f"Found existing agent: {agent['agentId']}")
                return agent
    except ClientError as e:
        logger.error(f"Error listing agents: {e}")
    
    return None


def create_agent_resource_role(iam_client, agent_name: str, region: str) -> str:
    """Create IAM role for Bedrock Agent.
    
    Args:
        iam_client: IAM client
        agent_name: Agent name for role naming
        region: AWS region
        
    Returns:
        Role ARN
    """
    role_name = f"AmazonBedrockExecutionRoleForAgents_{agent_name}"[:64]
    
    # Check if role exists
    try:
        response = iam_client.get_role(RoleName=role_name)
        logger.info(f"Using existing role: {role_name}")
        return response['Role']['Arn']
    except iam_client.exceptions.NoSuchEntityException:
        pass
    
    # Create trust policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    # Create role
    response = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description=f"Execution role for Bedrock Agent {agent_name}"
    )
    role_arn = response['Role']['Arn']
    
    # Attach required policies
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    "arn:aws:bedrock:*:*:inference-profile/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:Retrieve",
                    "bedrock:RetrieveAndGenerate"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:ListBucket"
                ],
                "Resource": "*"
            }
        ]
    }
    
    policy_name = f"{role_name}-policy"
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName=policy_name,
        PolicyDocument=json.dumps(policy_document)
    )
    
    # Wait for role to propagate
    logger.info("Waiting for IAM role to propagate...")
    time.sleep(10)
    
    logger.info(f"Created role: {role_arn}")
    return role_arn


def create_agent(
    bedrock_agent_client,
    agent_name: str,
    foundation_model: str,
    instruction: str,
    role_arn: str,
    description: str = None
) -> dict:
    """Create a new Bedrock Agent.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_name: Name for the agent
        foundation_model: Foundation model ID
        instruction: Agent instructions
        role_arn: IAM role ARN
        description: Optional description
        
    Returns:
        Agent creation response
    """
    logger.info(f"Creating agent: {agent_name}")
    
    response = bedrock_agent_client.create_agent(
        agentName=agent_name,
        foundationModel=foundation_model,
        instruction=instruction,
        agentResourceRoleArn=role_arn,
        idleSessionTTLInSeconds=600,
        description=description or f"Bedrock Agent: {agent_name}"
    )
    
    agent_id = response['agent']['agentId']
    logger.info(f"Created agent with ID: {agent_id}")
    
    return response['agent']


def update_agent(
    bedrock_agent_client,
    agent_id: str,
    agent_name: str,
    foundation_model: str,
    instruction: str,
    role_arn: str
) -> dict:
    """Update an existing Bedrock Agent.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_id: Existing agent ID
        agent_name: Agent name
        foundation_model: Foundation model ID
        instruction: Agent instructions
        role_arn: IAM role ARN
        
    Returns:
        Agent update response
    """
    logger.info(f"Updating agent: {agent_id}")
    
    response = bedrock_agent_client.update_agent(
        agentId=agent_id,
        agentName=agent_name,
        foundationModel=foundation_model,
        instruction=instruction,
        agentResourceRoleArn=role_arn,
        idleSessionTTLInSeconds=600
    )
    
    logger.info(f"Updated agent: {agent_id}")
    return response['agent']


def load_instruction(config_dir: str) -> str:
    """Load agent instruction from config directory.
    
    Args:
        config_dir: Path to config directory
        
    Returns:
        Instruction text
    """
    instruction_path = os.path.join(config_dir, 'agent_instruction.txt')
    
    if os.path.exists(instruction_path):
        with open(instruction_path, 'r') as f:
            return f.read().strip()
    
    # Return default instruction
    return """You are a helpful assistant. Answer questions accurately and concisely."""


def main():
    parser = argparse.ArgumentParser(description="Create or update Bedrock Agent")
    parser.add_argument("--agent-name", type=str, required=True)
    parser.add_argument("--foundation-model", type=str, required=True)
    parser.add_argument("--region", type=str, required=True)
    parser.add_argument("--role-arn", type=str, default=None)
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Creating/Updating Bedrock Agent")
    logger.info("=" * 60)
    
    # Initialize clients
    bedrock_agent = boto3.client('bedrock-agent', region_name=args.region)
    iam = boto3.client('iam', region_name=args.region)
    
    # Load instruction
    config_dir = "/opt/ml/processing/input/config"
    instruction = load_instruction(config_dir)
    logger.info(f"Loaded instruction ({len(instruction)} chars)")
    
    # Create or get role
    if args.role_arn:
        role_arn = args.role_arn
    else:
        role_arn = create_agent_resource_role(iam, args.agent_name, args.region)
    
    # Check if agent exists
    existing_agent = get_existing_agent(bedrock_agent, args.agent_name)
    
    if existing_agent:
        # Update existing agent
        agent = update_agent(
            bedrock_agent,
            existing_agent['agentId'],
            args.agent_name,
            args.foundation_model,
            instruction,
            role_arn
        )
    else:
        # Create new agent
        agent = create_agent(
            bedrock_agent,
            args.agent_name,
            args.foundation_model,
            instruction,
            role_arn
        )
    
    # Write output
    output_dir = "/opt/ml/processing/output"
    os.makedirs(output_dir, exist_ok=True)
    
    output = {
        "agent_id": agent['agentId'],
        "agent_name": agent['agentName'],
        "agent_arn": agent['agentArn'],
        "agent_status": agent['agentStatus'],
        "foundation_model": args.foundation_model,
        "role_arn": role_arn,
        "created_or_updated": "updated" if existing_agent else "created"
    }
    
    output_path = os.path.join(output_dir, "agent_output.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Agent output written to {output_path}")
    logger.info("=" * 60)
    logger.info(f"Agent {output['created_or_updated']} successfully!")
    logger.info(f"Agent ID: {output['agent_id']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

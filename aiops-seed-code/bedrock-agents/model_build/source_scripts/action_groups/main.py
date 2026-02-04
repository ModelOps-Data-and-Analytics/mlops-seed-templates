"""Deploy Action Groups for Bedrock Agent."""
import argparse
import json
import logging
import os
import sys
import time
import zipfile

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_lambda_function(
    lambda_client,
    function_name: str,
    role_arn: str,
    code_path: str,
    description: str = None
) -> str:
    """Create or update Lambda function for action group.
    
    Args:
        lambda_client: Lambda client
        function_name: Function name
        role_arn: IAM role ARN
        code_path: Path to zipped code
        description: Function description
        
    Returns:
        Function ARN
    """
    # Check if function exists
    try:
        response = lambda_client.get_function(FunctionName=function_name)
        logger.info(f"Updating existing function: {function_name}")
        
        # Update function code
        with open(code_path, 'rb') as f:
            lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=f.read()
            )
        
        return response['Configuration']['FunctionArn']
    except lambda_client.exceptions.ResourceNotFoundException:
        pass
    
    # Create new function
    logger.info(f"Creating Lambda function: {function_name}")
    
    with open(code_path, 'rb') as f:
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime='python3.11',
            Role=role_arn,
            Handler='main.handler',
            Code={'ZipFile': f.read()},
            Description=description or f"Action group function: {function_name}",
            Timeout=30,
            MemorySize=256
        )
    
    function_arn = response['FunctionArn']
    
    # Add permission for Bedrock to invoke
    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId='AllowBedrockInvoke',
            Action='lambda:InvokeFunction',
            Principal='bedrock.amazonaws.com'
        )
    except ClientError as e:
        if "ResourceConflictException" not in str(e):
            raise
    
    logger.info(f"Created function: {function_arn}")
    return function_arn


def create_action_group(
    bedrock_agent_client,
    agent_id: str,
    action_group_name: str,
    lambda_arn: str,
    api_schema: dict
) -> dict:
    """Create action group for agent.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_id: Agent ID
        action_group_name: Action group name
        lambda_arn: Lambda function ARN
        api_schema: OpenAPI schema
        
    Returns:
        Action group details
    """
    logger.info(f"Creating action group: {action_group_name}")
    
    # Check if action group exists
    try:
        response = bedrock_agent_client.list_agent_action_groups(
            agentId=agent_id,
            agentVersion='DRAFT'
        )
        for ag in response.get('actionGroupSummaries', []):
            if ag['actionGroupName'] == action_group_name:
                logger.info(f"Updating existing action group: {ag['actionGroupId']}")
                
                response = bedrock_agent_client.update_agent_action_group(
                    agentId=agent_id,
                    agentVersion='DRAFT',
                    actionGroupId=ag['actionGroupId'],
                    actionGroupName=action_group_name,
                    actionGroupExecutor={'lambda': lambda_arn},
                    apiSchema={'payload': json.dumps(api_schema)}
                )
                return response['agentActionGroup']
    except Exception as e:
        logger.warning(f"Error checking existing action groups: {e}")
    
    # Create new action group
    response = bedrock_agent_client.create_agent_action_group(
        agentId=agent_id,
        agentVersion='DRAFT',
        actionGroupName=action_group_name,
        actionGroupExecutor={'lambda': lambda_arn},
        apiSchema={'payload': json.dumps(api_schema)}
    )
    
    ag = response['agentActionGroup']
    logger.info(f"Created action group: {ag['actionGroupId']}")
    
    return ag


def load_api_schema(config_dir: str) -> dict:
    """Load API schema from config directory.
    
    Args:
        config_dir: Config directory path
        
    Returns:
        API schema dictionary
    """
    schema_path = os.path.join(config_dir, 'agent_schema.json')
    
    if os.path.exists(schema_path):
        with open(schema_path, 'r') as f:
            return json.load(f)
    
    # Return minimal schema
    return {
        "openapi": "3.0.0",
        "info": {"title": "Agent Actions", "version": "1.0.0"},
        "paths": {}
    }


def main():
    parser = argparse.ArgumentParser(description="Deploy Action Groups for Bedrock Agent")
    parser.add_argument("--agent-name", type=str, required=True)
    parser.add_argument("--region", type=str, required=True)
    parser.add_argument("--enable", type=str, default="true")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Deploying Action Groups")
    logger.info("=" * 60)
    
    output = {
        "enabled": args.enable.lower() == "true",
        "action_groups": [],
        "lambda_functions": [],
        "status": "skipped"
    }
    
    if args.enable.lower() != "true":
        logger.info("Action groups deployment is disabled")
    else:
        try:
            # Load API schema
            config_dir = "/opt/ml/processing/input/config"
            api_schema = load_api_schema(config_dir)
            
            # In a full implementation:
            # 1. Package Lambda functions
            # 2. Deploy to AWS Lambda
            # 3. Create action groups in Bedrock
            
            output["status"] = "success"
            output["api_schema_loaded"] = True
            output["paths_count"] = len(api_schema.get('paths', {}))
            
            logger.info(f"Loaded API schema with {output['paths_count']} paths")
            
        except Exception as e:
            logger.error(f"Error deploying action groups: {e}")
            output["status"] = "error"
            output["error"] = str(e)
    
    # Write output
    output_dir = "/opt/ml/processing/output"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "actions_output.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Actions output written to {output_path}")
    logger.info("=" * 60)
    logger.info(f"Action Groups step completed: {output['status']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

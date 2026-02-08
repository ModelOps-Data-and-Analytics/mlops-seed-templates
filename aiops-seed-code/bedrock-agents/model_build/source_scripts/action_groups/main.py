"""Deploy Action Groups for Bedrock Agent."""
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


# =============================================================================
# IAM Role Management
# =============================================================================
def get_or_create_lambda_role(iam_client, role_name: str, account_id: str) -> str:
    """Get or create IAM role for Lambda function.

    Args:
        iam_client: IAM client
        role_name: Role name
        account_id: AWS account ID

    Returns:
        Role ARN
    """
    # Check if role exists
    try:
        response = iam_client.get_role(RoleName=role_name)
        logger.info(f"Using existing Lambda role: {role_name}")
        return response['Role']['Arn']
    except iam_client.exceptions.NoSuchEntityException:
        pass

    logger.info(f"Creating Lambda role: {role_name}")

    # Trust policy for Lambda
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }

    # Create role
    response = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="Execution role for Bedrock Agent Action Group Lambda"
    )
    role_arn = response['Role']['Arn']

    # Attach basic Lambda execution policy
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    )

    # Wait for role to propagate
    logger.info("Waiting for IAM role to propagate...")
    time.sleep(10)

    logger.info(f"Created Lambda role: {role_arn}")
    return role_arn


# =============================================================================
# Lambda Management
# =============================================================================
def deploy_lambda_function(
    lambda_client,
    function_name: str,
    role_arn: str,
    zip_path: str,
    description: str = None
) -> str:
    """Deploy or update Lambda function.

    Args:
        lambda_client: Lambda client
        function_name: Function name
        role_arn: IAM role ARN
        zip_path: Path to zip file
        description: Function description

    Returns:
        Function ARN
    """
    logger.info(f"Deploying Lambda function: {function_name}")

    # Read zip file
    with open(zip_path, 'rb') as f:
        zip_content = f.read()

    # Check if function exists
    try:
        response = lambda_client.get_function(FunctionName=function_name)
        logger.info(f"Updating existing function: {function_name}")

        # Update function code
        lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_content
        )

        # Wait for update to complete
        waiter = lambda_client.get_waiter('function_updated_v2')
        waiter.wait(FunctionName=function_name)

        return response['Configuration']['FunctionArn']

    except lambda_client.exceptions.ResourceNotFoundException:
        pass

    # Create new function
    logger.info(f"Creating new Lambda function: {function_name}")

    response = lambda_client.create_function(
        FunctionName=function_name,
        Runtime='python3.11',
        Role=role_arn,
        Handler='main.handler',
        Code={'ZipFile': zip_content},
        Description=description or f"Bedrock Agent Action Group: {function_name}",
        Timeout=30,
        MemorySize=256
    )

    function_arn = response['FunctionArn']

    # Wait for function to be active
    waiter = lambda_client.get_waiter('function_active_v2')
    waiter.wait(FunctionName=function_name)

    logger.info(f"Created Lambda function: {function_arn}")
    return function_arn


def add_bedrock_permission(lambda_client, function_name: str, agent_id: str, region: str, account_id: str) -> None:
    """Add permission for Bedrock to invoke Lambda.

    Args:
        lambda_client: Lambda client
        function_name: Function name
        agent_id: Bedrock Agent ID
        region: AWS region
        account_id: AWS account ID
    """
    statement_id = f"AllowBedrockAgent-{agent_id}"

    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId=statement_id,
            Action='lambda:InvokeFunction',
            Principal='bedrock.amazonaws.com',
            SourceArn=f"arn:aws:bedrock:{region}:{account_id}:agent/{agent_id}"
        )
        logger.info(f"Added Bedrock permission to Lambda: {statement_id}")
    except ClientError as e:
        if 'ResourceConflictException' in str(e):
            logger.info(f"Bedrock permission already exists: {statement_id}")
        else:
            raise


# =============================================================================
# Agent & Action Group Management
# =============================================================================
def get_agent_by_name(bedrock_agent_client, agent_name: str) -> dict | None:
    """Get agent by name.

    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_name: Agent name

    Returns:
        Agent details if found
    """
    try:
        response = bedrock_agent_client.list_agents()
        for agent in response.get('agentSummaries', []):
            if agent['agentName'] == agent_name:
                logger.info(f"Found agent: {agent['agentId']}")
                return agent
    except ClientError as e:
        logger.error(f"Error listing agents: {e}")
    return None


def create_or_update_action_group(
    bedrock_agent_client,
    agent_id: str,
    action_group_name: str,
    lambda_arn: str,
    api_schema: dict,
    description: str = None
) -> dict:
    """Create or update action group for agent.

    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_id: Agent ID
        action_group_name: Action group name
        lambda_arn: Lambda function ARN
        api_schema: OpenAPI schema
        description: Action group description

    Returns:
        Action group details
    """
    logger.info(f"Creating/updating action group: {action_group_name}")

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
                    description=description or f"Action group for {action_group_name}",
                    actionGroupExecutor={'lambda': lambda_arn},
                    apiSchema={'payload': json.dumps(api_schema)}
                )
                logger.info(f"Updated action group: {ag['actionGroupId']}")
                return response['agentActionGroup']
    except Exception as e:
        logger.warning(f"Error checking existing action groups: {e}")

    # Create new action group
    response = bedrock_agent_client.create_agent_action_group(
        agentId=agent_id,
        agentVersion='DRAFT',
        actionGroupName=action_group_name,
        description=description or f"Action group for {action_group_name}",
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
            schema = json.load(f)
            logger.info(f"Loaded API schema from: {schema_path}")
            return schema

    logger.warning(f"No schema found at {schema_path}, using minimal schema")
    return {
        "openapi": "3.0.0",
        "info": {"title": "Agent Actions", "version": "1.0.0"},
        "paths": {}
    }


def find_lambda_zip(lambdas_dir: str) -> str | None:
    """Find Lambda zip file in the lambdas directory.

    Args:
        lambdas_dir: Directory containing Lambda packages

    Returns:
        Path to zip file or None
    """
    if not os.path.exists(lambdas_dir):
        logger.warning(f"Lambdas directory not found: {lambdas_dir}")
        return None

    # Look for agent_actions.zip first, then any zip
    preferred = os.path.join(lambdas_dir, 'agent_actions.zip')
    if os.path.exists(preferred):
        return preferred

    # Find any zip file
    for file in os.listdir(lambdas_dir):
        if file.endswith('.zip'):
            return os.path.join(lambdas_dir, file)

    return None


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Deploy Action Groups for Bedrock Agent")
    parser.add_argument("--agent-name", type=str, required=True)
    parser.add_argument("--region", type=str, required=True)
    parser.add_argument("--enable", type=str, default="true")

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("DEPLOYING ACTION GROUPS")
    logger.info("=" * 60)
    logger.info(f"  Agent Name: {args.agent_name}")
    logger.info(f"  Region: {args.region}")
    logger.info(f"  Enabled: {args.enable}")
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
            # Initialize clients
            bedrock_agent = boto3.client('bedrock-agent', region_name=args.region)
            lambda_client = boto3.client('lambda', region_name=args.region)
            iam_client = boto3.client('iam')
            sts_client = boto3.client('sts')

            account_id = sts_client.get_caller_identity()['Account']

            # Paths
            config_dir = "/opt/ml/processing/input/config"
            lambdas_dir = "/opt/ml/processing/input/lambdas"

            # 1. Get agent
            logger.info("")
            logger.info("Step 1: Getting Bedrock Agent...")
            agent = get_agent_by_name(bedrock_agent, args.agent_name)
            if not agent:
                raise Exception(f"Agent not found: {args.agent_name}")
            agent_id = agent['agentId']
            output["agent_id"] = agent_id

            # 2. Load API schema
            logger.info("")
            logger.info("Step 2: Loading API Schema...")
            api_schema = load_api_schema(config_dir)
            paths_count = len(api_schema.get('paths', {}))
            logger.info(f"  Found {paths_count} API paths")
            output["paths_count"] = paths_count

            if paths_count == 0:
                logger.warning("No API paths defined, skipping action group creation")
                output["status"] = "skipped_no_paths"
            else:
                # 3. Find Lambda zip
                logger.info("")
                logger.info("Step 3: Finding Lambda package...")
                lambda_zip = find_lambda_zip(lambdas_dir)
                if not lambda_zip:
                    raise Exception(f"No Lambda zip found in {lambdas_dir}")
                logger.info(f"  Using: {lambda_zip}")

                # 4. Create/get Lambda role
                logger.info("")
                logger.info("Step 4: Setting up Lambda IAM role...")
                role_name = f"{args.agent_name}-action-lambda-role"[:64]
                lambda_role_arn = get_or_create_lambda_role(iam_client, role_name, account_id)
                output["lambda_role_arn"] = lambda_role_arn

                # 5. Deploy Lambda function
                logger.info("")
                logger.info("Step 5: Deploying Lambda function...")
                function_name = f"{args.agent_name}-actions"[:64]
                lambda_arn = deploy_lambda_function(
                    lambda_client,
                    function_name,
                    lambda_role_arn,
                    lambda_zip,
                    description=f"Action handler for Bedrock Agent: {args.agent_name}"
                )
                output["lambda_functions"].append({
                    "name": function_name,
                    "arn": lambda_arn
                })

                # 6. Add Bedrock permission to Lambda
                logger.info("")
                logger.info("Step 6: Adding Bedrock permissions to Lambda...")
                add_bedrock_permission(lambda_client, function_name, agent_id, args.region, account_id)

                # 7. Create Action Group
                logger.info("")
                logger.info("Step 7: Creating Action Group...")
                action_group_name = f"{args.agent_name}-actions"
                action_group = create_or_update_action_group(
                    bedrock_agent,
                    agent_id,
                    action_group_name,
                    lambda_arn,
                    api_schema,
                    description="Customer service actions for order and customer management"
                )
                output["action_groups"].append({
                    "name": action_group_name,
                    "id": action_group['actionGroupId']
                })

                output["status"] = "success"
                logger.info("")
                logger.info("=" * 60)
                logger.info("ACTION GROUPS DEPLOYED SUCCESSFULLY!")
                logger.info(f"  Lambda: {function_name}")
                logger.info(f"  Action Group: {action_group_name}")
                logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Error deploying action groups: {e}")
            output["status"] = "error"
            output["error"] = str(e)
            import traceback
            traceback.print_exc()

    # Write output
    output_dir = "/opt/ml/processing/output"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "actions_output.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    logger.info(f"Actions output written to {output_path}")

    if output["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()

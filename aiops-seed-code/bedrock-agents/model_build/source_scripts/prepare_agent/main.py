"""Prepare Bedrock Agent for deployment."""
import argparse
import json
import logging
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_agent_by_name(bedrock_agent_client, agent_name: str) -> dict | None:
    """Get agent details by name.
    
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
                return agent
    except ClientError as e:
        logger.error(f"Error listing agents: {e}")
    
    return None


def prepare_agent(bedrock_agent_client, agent_id: str) -> dict:
    """Prepare agent for deployment.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_id: Agent ID
        
    Returns:
        Preparation response
    """
    logger.info(f"Preparing agent: {agent_id}")
    
    response = bedrock_agent_client.prepare_agent(agentId=agent_id)
    
    # Wait for agent to be prepared
    logger.info("Waiting for agent preparation to complete...")
    
    for _ in range(60):  # Max 10 minutes
        agent_response = bedrock_agent_client.get_agent(agentId=agent_id)
        status = agent_response['agent']['agentStatus']
        
        if status == 'PREPARED':
            logger.info("Agent prepared successfully")
            return agent_response['agent']
        elif status in ['FAILED', 'DELETING']:
            raise Exception(f"Agent preparation failed with status: {status}")
        
        logger.info(f"Agent status: {status}, waiting...")
        time.sleep(10)
    
    raise TimeoutError("Agent preparation timed out")


def create_agent_alias(
    bedrock_agent_client,
    agent_id: str,
    alias_name: str = "staging",
    description: str = None
) -> dict:
    """Create or update agent alias.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_id: Agent ID
        alias_name: Alias name
        description: Alias description
        
    Returns:
        Alias details
    """
    logger.info(f"Creating alias '{alias_name}' for agent {agent_id}")
    
    # Check if alias exists
    try:
        response = bedrock_agent_client.list_agent_aliases(agentId=agent_id)
        for alias in response.get('agentAliasSummaries', []):
            if alias['agentAliasName'] == alias_name:
                logger.info(f"Updating existing alias: {alias['agentAliasId']}")
                
                response = bedrock_agent_client.update_agent_alias(
                    agentId=agent_id,
                    agentAliasId=alias['agentAliasId'],
                    agentAliasName=alias_name,
                    description=description or f"Staging alias for agent {agent_id}"
                )
                return response['agentAlias']
    except Exception as e:
        logger.warning(f"Error checking aliases: {e}")
    
    # Create new alias
    response = bedrock_agent_client.create_agent_alias(
        agentId=agent_id,
        agentAliasName=alias_name,
        description=description or f"Staging alias for agent {agent_id}"
    )
    
    alias = response['agentAlias']
    logger.info(f"Created alias: {alias['agentAliasId']}")
    
    # Wait for alias to be ready
    for _ in range(30):
        alias_response = bedrock_agent_client.get_agent_alias(
            agentId=agent_id,
            agentAliasId=alias['agentAliasId']
        )
        status = alias_response['agentAlias']['agentAliasStatus']
        
        if status == 'PREPARED':
            return alias_response['agentAlias']
        elif status == 'FAILED':
            raise Exception(f"Alias creation failed")
        
        time.sleep(5)
    
    return alias


def main():
    parser = argparse.ArgumentParser(description="Prepare Bedrock Agent for deployment")
    parser.add_argument("--agent-name", type=str, required=True)
    parser.add_argument("--region", type=str, required=True)
    parser.add_argument("--alias-name", type=str, default="staging")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Preparing Bedrock Agent")
    logger.info("=" * 60)
    
    bedrock_agent = boto3.client('bedrock-agent', region_name=args.region)
    
    output = {
        "agent_name": args.agent_name,
        "agent_id": None,
        "agent_version": None,
        "alias_id": None,
        "alias_name": args.alias_name,
        "status": "unknown"
    }
    
    try:
        # Get agent
        agent = get_agent_by_name(bedrock_agent, args.agent_name)
        
        if not agent:
            raise Exception(f"Agent not found: {args.agent_name}")
        
        output["agent_id"] = agent['agentId']
        
        # Prepare agent
        prepared_agent = prepare_agent(bedrock_agent, agent['agentId'])
        output["agent_version"] = prepared_agent.get('preparedAgentVersion', 'DRAFT')
        
        # Create staging alias
        alias = create_agent_alias(
            bedrock_agent,
            agent['agentId'],
            args.alias_name
        )
        output["alias_id"] = alias['agentAliasId']
        output["status"] = "prepared"
        
        logger.info(f"Agent prepared successfully")
        logger.info(f"Agent ID: {output['agent_id']}")
        logger.info(f"Alias ID: {output['alias_id']}")
        
    except Exception as e:
        logger.error(f"Error preparing agent: {e}")
        output["status"] = "error"
        output["error"] = str(e)
    
    # Write output
    output_dir = "/opt/ml/processing/output"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "prepare_output.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Prepare output written to {output_path}")
    logger.info("=" * 60)
    logger.info(f"Prepare Agent step completed: {output['status']}")
    logger.info("=" * 60)
    
    if output["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()

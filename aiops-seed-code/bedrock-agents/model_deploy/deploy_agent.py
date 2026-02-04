"""Deploy Bedrock Agent to target environment."""
import argparse
import json
import logging
import sys
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentDeployer:
    """Handles Bedrock Agent deployment operations."""
    
    def __init__(self, region: str):
        """Initialize deployer.
        
        Args:
            region: AWS region
        """
        self.region = region
        self.bedrock_agent = boto3.client('bedrock-agent', region_name=region)
    
    def get_agent(self, agent_id: str) -> dict:
        """Get agent details.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent details
        """
        response = self.bedrock_agent.get_agent(agentId=agent_id)
        return response['agent']
    
    def get_alias(self, agent_id: str, alias_id: str) -> Optional[dict]:
        """Get agent alias.
        
        Args:
            agent_id: Agent ID
            alias_id: Alias ID or name
            
        Returns:
            Alias details if found
        """
        try:
            response = self.bedrock_agent.get_agent_alias(
                agentId=agent_id,
                agentAliasId=alias_id
            )
            return response['agentAlias']
        except ClientError:
            return None
    
    def get_alias_by_name(self, agent_id: str, alias_name: str) -> Optional[dict]:
        """Get agent alias by name.
        
        Args:
            agent_id: Agent ID
            alias_name: Alias name
            
        Returns:
            Alias details if found
        """
        try:
            response = self.bedrock_agent.list_agent_aliases(agentId=agent_id)
            for alias in response.get('agentAliasSummaries', []):
                if alias['agentAliasName'] == alias_name:
                    return self.get_alias(agent_id, alias['agentAliasId'])
        except ClientError as e:
            logger.error(f"Error listing aliases: {e}")
        return None
    
    def create_or_update_alias(
        self,
        agent_id: str,
        alias_name: str,
        agent_version: str,
        description: str = ""
    ) -> dict:
        """Create or update agent alias.
        
        Args:
            agent_id: Agent ID
            alias_name: Alias name
            agent_version: Agent version to point to
            description: Alias description
            
        Returns:
            Alias details
        """
        existing = self.get_alias_by_name(agent_id, alias_name)
        
        if existing:
            logger.info(f"Updating alias: {alias_name}")
            response = self.bedrock_agent.update_agent_alias(
                agentId=agent_id,
                agentAliasId=existing['agentAliasId'],
                agentAliasName=alias_name,
                routingConfiguration=[
                    {
                        'agentVersion': agent_version
                    }
                ],
                description=description
            )
            return response['agentAlias']
        else:
            logger.info(f"Creating alias: {alias_name}")
            response = self.bedrock_agent.create_agent_alias(
                agentId=agent_id,
                agentAliasName=alias_name,
                routingConfiguration=[
                    {
                        'agentVersion': agent_version
                    }
                ],
                description=description
            )
            return response['agentAlias']
    
    def wait_for_alias_ready(
        self,
        agent_id: str,
        alias_id: str,
        timeout_seconds: int = 300
    ) -> bool:
        """Wait for alias to be ready.
        
        Args:
            agent_id: Agent ID
            alias_id: Alias ID
            timeout_seconds: Maximum wait time
            
        Returns:
            True if ready
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            alias = self.get_alias(agent_id, alias_id)
            if alias:
                status = alias.get('agentAliasStatus')
                if status == 'PREPARED':
                    return True
                elif status == 'FAILED':
                    logger.error("Alias creation failed")
                    return False
            
            logger.info(f"Alias status: {status}, waiting...")
            time.sleep(10)
        
        return False
    
    def get_latest_version(self, agent_id: str) -> str:
        """Get latest agent version.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Latest version number
        """
        response = self.bedrock_agent.list_agent_versions(agentId=agent_id)
        versions = response.get('agentVersionSummaries', [])
        
        # Filter out DRAFT and get latest
        numbered_versions = [
            v for v in versions
            if v['agentVersion'] != 'DRAFT'
        ]
        
        if not numbered_versions:
            return 'DRAFT'
        
        # Sort by version number
        numbered_versions.sort(
            key=lambda v: int(v['agentVersion']),
            reverse=True
        )
        
        return numbered_versions[0]['agentVersion']
    
    def deploy(
        self,
        agent_id: str,
        source_alias_id: str,
        target_alias: str
    ) -> dict:
        """Deploy agent from source alias to target alias.
        
        Args:
            agent_id: Agent ID
            source_alias_id: Source alias ID
            target_alias: Target alias name
            
        Returns:
            Deployment result
        """
        logger.info(f"Deploying agent {agent_id}")
        logger.info(f"Source alias: {source_alias_id}")
        logger.info(f"Target alias: {target_alias}")
        
        # Get source alias to find the version
        source = self.get_alias(agent_id, source_alias_id)
        if not source:
            raise Exception(f"Source alias not found: {source_alias_id}")
        
        # Get version from source routing config
        routing = source.get('routingConfiguration', [])
        if not routing:
            raise Exception("Source alias has no routing configuration")
        
        agent_version = routing[0].get('agentVersion')
        logger.info(f"Deploying version: {agent_version}")
        
        # Create or update target alias
        target = self.create_or_update_alias(
            agent_id,
            target_alias,
            agent_version,
            f"Deployed from {source_alias_id}"
        )
        
        # Wait for alias to be ready
        if not self.wait_for_alias_ready(agent_id, target['agentAliasId']):
            raise Exception("Alias failed to become ready")
        
        return {
            "agent_id": agent_id,
            "target_alias": target_alias,
            "target_alias_id": target['agentAliasId'],
            "agent_version": agent_version,
            "status": "deployed"
        }
    
    def rollback(self, agent_id: str, target_alias: str, version: str) -> dict:
        """Rollback alias to specific version.
        
        Args:
            agent_id: Agent ID
            target_alias: Alias to rollback
            version: Version to rollback to
            
        Returns:
            Rollback result
        """
        logger.info(f"Rolling back {target_alias} to version {version}")
        
        target = self.create_or_update_alias(
            agent_id,
            target_alias,
            version,
            f"Rolled back to version {version}"
        )
        
        if not self.wait_for_alias_ready(agent_id, target['agentAliasId']):
            raise Exception("Rollback failed")
        
        return {
            "agent_id": agent_id,
            "target_alias": target_alias,
            "agent_version": version,
            "status": "rolled_back"
        }


def main():
    parser = argparse.ArgumentParser(description="Deploy Bedrock Agent")
    parser.add_argument("--agent-id", type=str, required=True)
    parser.add_argument("--source-alias-id", type=str, default="staging")
    parser.add_argument("--target-alias", type=str, required=True)
    parser.add_argument("--region", type=str, default="us-east-1")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--target-version", type=str)
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Bedrock Agent Deployment")
    logger.info("=" * 60)
    
    deployer = AgentDeployer(args.region)
    
    try:
        if args.rollback:
            if not args.target_version:
                raise Exception("--target-version required for rollback")
            
            result = deployer.rollback(
                args.agent_id,
                args.target_alias,
                args.target_version
            )
        else:
            result = deployer.deploy(
                args.agent_id,
                args.source_alias_id,
                args.target_alias
            )
        
        logger.info(f"Result: {json.dumps(result, indent=2)}")
        logger.info("Deployment completed successfully")
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

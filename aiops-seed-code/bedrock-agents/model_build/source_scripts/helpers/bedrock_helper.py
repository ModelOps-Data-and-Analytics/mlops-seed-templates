"""Bedrock helper utilities."""
import json
import logging
import time
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BedrockAgentHelper:
    """Helper class for Bedrock Agent operations."""
    
    def __init__(self, region: str):
        """Initialize helper.
        
        Args:
            region: AWS region
        """
        self.region = region
        self.bedrock_agent = boto3.client('bedrock-agent', region_name=region)
        self.bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name=region)
    
    def get_agent_by_name(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get agent by name.
        
        Args:
            agent_name: Agent name
            
        Returns:
            Agent details if found
        """
        try:
            response = self.bedrock_agent.list_agents()
            for agent in response.get('agentSummaries', []):
                if agent['agentName'] == agent_name:
                    return self.bedrock_agent.get_agent(agentId=agent['agentId'])['agent']
        except ClientError as e:
            logger.error(f"Error getting agent: {e}")
        return None
    
    def wait_for_agent_status(
        self,
        agent_id: str,
        target_status: str,
        timeout_seconds: int = 600
    ) -> bool:
        """Wait for agent to reach target status.
        
        Args:
            agent_id: Agent ID
            target_status: Expected status
            timeout_seconds: Maximum wait time
            
        Returns:
            True if status reached
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                response = self.bedrock_agent.get_agent(agentId=agent_id)
                status = response['agent']['agentStatus']
                
                if status == target_status:
                    return True
                elif status in ['FAILED', 'DELETING']:
                    logger.error(f"Agent reached terminal status: {status}")
                    return False
                
                logger.info(f"Agent status: {status}, waiting for {target_status}...")
                time.sleep(10)
                
            except ClientError as e:
                logger.error(f"Error checking agent status: {e}")
                return False
        
        logger.error(f"Timeout waiting for agent status: {target_status}")
        return False
    
    def invoke_agent(
        self,
        agent_id: str,
        agent_alias_id: str,
        prompt: str,
        session_id: str
    ) -> str:
        """Invoke agent and get response.
        
        Args:
            agent_id: Agent ID
            agent_alias_id: Agent alias ID
            prompt: Input prompt
            session_id: Session ID
            
        Returns:
            Agent response
        """
        try:
            response = self.bedrock_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_id,
                inputText=prompt
            )
            
            full_response = ""
            for event in response.get('completion', []):
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        full_response += chunk['bytes'].decode('utf-8')
            
            return full_response
            
        except Exception as e:
            logger.error(f"Error invoking agent: {e}")
            return ""
    
    def list_agent_action_groups(self, agent_id: str) -> List[Dict[str, Any]]:
        """List action groups for agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of action groups
        """
        try:
            response = self.bedrock_agent.list_agent_action_groups(
                agentId=agent_id,
                agentVersion='DRAFT'
            )
            return response.get('actionGroupSummaries', [])
        except ClientError as e:
            logger.error(f"Error listing action groups: {e}")
            return []
    
    def list_agent_knowledge_bases(self, agent_id: str) -> List[Dict[str, Any]]:
        """List knowledge bases associated with agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of knowledge bases
        """
        try:
            response = self.bedrock_agent.list_agent_knowledge_bases(
                agentId=agent_id,
                agentVersion='DRAFT'
            )
            return response.get('agentKnowledgeBaseSummaries', [])
        except ClientError as e:
            logger.error(f"Error listing knowledge bases: {e}")
            return []

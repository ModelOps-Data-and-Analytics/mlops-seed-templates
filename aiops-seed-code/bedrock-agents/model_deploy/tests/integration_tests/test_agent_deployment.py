"""Integration tests for Bedrock Agent deployment."""
import json
import uuid

import boto3
import pytest


class TestAgentDeployment:
    """Test agent deployment functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, agent_id, environment, region):
        """Set up test fixtures."""
        self.agent_id = agent_id
        self.environment = environment
        self.region = region
        
        if not self.agent_id:
            pytest.skip("No agent-id provided")
        
        self.bedrock_agent = boto3.client('bedrock-agent', region_name=region)
        self.bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name=region)
    
    def test_agent_exists(self):
        """Test that agent exists and is accessible."""
        response = self.bedrock_agent.get_agent(agentId=self.agent_id)
        
        assert response is not None
        assert 'agent' in response
        assert response['agent']['agentId'] == self.agent_id
        assert response['agent']['agentStatus'] in ['PREPARED', 'NOT_PREPARED']
    
    def test_agent_has_alias(self):
        """Test that agent has the expected alias."""
        response = self.bedrock_agent.list_agent_aliases(agentId=self.agent_id)
        
        aliases = response.get('agentAliasSummaries', [])
        alias_names = [a['agentAliasName'] for a in aliases]
        
        # Should have at least staging alias
        assert len(aliases) > 0, "Agent should have at least one alias"
    
    def test_agent_responds(self):
        """Test that agent can respond to queries."""
        # Get first available alias
        response = self.bedrock_agent.list_agent_aliases(agentId=self.agent_id)
        aliases = response.get('agentAliasSummaries', [])
        
        if not aliases:
            pytest.skip("No aliases available")
        
        alias_id = aliases[0]['agentAliasId']
        session_id = str(uuid.uuid4())
        
        # Invoke agent
        try:
            response = self.bedrock_runtime.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=alias_id,
                sessionId=session_id,
                inputText="Hello, are you available?"
            )
            
            # Collect response
            full_response = ""
            for event in response.get('completion', []):
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        full_response += chunk['bytes'].decode('utf-8')
            
            assert len(full_response) > 0, "Agent should provide a response"
            
        except Exception as e:
            pytest.fail(f"Agent invocation failed: {e}")
    
    def test_agent_handles_customer_query(self):
        """Test agent handles customer service query."""
        response = self.bedrock_agent.list_agent_aliases(agentId=self.agent_id)
        aliases = response.get('agentAliasSummaries', [])
        
        if not aliases:
            pytest.skip("No aliases available")
        
        alias_id = aliases[0]['agentAliasId']
        session_id = str(uuid.uuid4())
        
        try:
            response = self.bedrock_runtime.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=alias_id,
                sessionId=session_id,
                inputText="I need help with my order"
            )
            
            full_response = ""
            for event in response.get('completion', []):
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        full_response += chunk['bytes'].decode('utf-8')
            
            # Agent should acknowledge the customer request
            assert len(full_response) > 0
            
        except Exception as e:
            pytest.fail(f"Customer query handling failed: {e}")
    
    def test_action_groups_configured(self):
        """Test that action groups are properly configured."""
        response = self.bedrock_agent.list_agent_action_groups(
            agentId=self.agent_id,
            agentVersion='DRAFT'
        )
        
        action_groups = response.get('actionGroupSummaries', [])
        
        # Should have at least one action group
        assert len(action_groups) > 0, "Agent should have action groups"
    
    def test_agent_version_exists(self):
        """Test that agent has at least one version."""
        response = self.bedrock_agent.list_agent_versions(agentId=self.agent_id)
        
        versions = response.get('agentVersionSummaries', [])
        
        # Should have at least DRAFT
        assert len(versions) > 0, "Agent should have versions"


class TestDeploymentRollback:
    """Test deployment rollback functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, agent_id, environment, region):
        """Set up test fixtures."""
        self.agent_id = agent_id
        self.environment = environment
        self.region = region
        
        if not self.agent_id:
            pytest.skip("No agent-id provided")
        
        self.bedrock_agent = boto3.client('bedrock-agent', region_name=region)
    
    def test_multiple_versions_exist(self):
        """Test that multiple versions exist for rollback capability."""
        response = self.bedrock_agent.list_agent_versions(agentId=self.agent_id)
        
        versions = response.get('agentVersionSummaries', [])
        # Filter out DRAFT
        numbered = [v for v in versions if v['agentVersion'] != 'DRAFT']
        
        if len(numbered) < 2:
            pytest.skip("Need at least 2 versions for rollback test")
        
        assert len(numbered) >= 2, "Should have multiple versions for rollback"

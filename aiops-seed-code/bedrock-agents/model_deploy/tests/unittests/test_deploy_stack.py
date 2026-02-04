"""Unit tests for CDK deployment stack."""
import pytest
from aws_cdk import App
from aws_cdk.assertions import Template, Match

from deploy_agent.deploy_agent_stack import DeployAgentStack


class TestDeployAgentStack:
    """Test CDK stack creation."""
    
    @pytest.fixture
    def template(self):
        """Create CDK template for testing."""
        app = App()
        config = {
            "environment": "test",
            "region": "us-east-1",
            "log_level": "DEBUG"
        }
        stack = DeployAgentStack(app, "TestStack", config=config)
        return Template.from_stack(stack)
    
    def test_lambda_function_created(self, template):
        """Test that Lambda function is created."""
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "Runtime": "python3.11",
                "Timeout": 300,  # 5 minutes
                "MemorySize": 256
            }
        )
    
    def test_lambda_has_environment_variables(self, template):
        """Test Lambda has required environment variables."""
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "Environment": {
                    "Variables": {
                        "ENVIRONMENT": "test",
                        "LOG_LEVEL": "DEBUG"
                    }
                }
            }
        )
    
    def test_eventbridge_rule_created(self, template):
        """Test EventBridge rule is created."""
        template.has_resource_properties(
            "AWS::Events::Rule",
            {
                "EventPattern": {
                    "source": ["aws.sagemaker"],
                    "detail-type": ["SageMaker Model Package State Change"]
                }
            }
        )
    
    def test_iam_role_has_bedrock_permissions(self, template):
        """Test IAM role has Bedrock permissions."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with([
                        Match.object_like({
                            "Action": Match.array_with([
                                "bedrock:GetAgent"
                            ]),
                            "Effect": "Allow"
                        })
                    ])
                }
            }
        )
    
    def test_log_group_created(self, template):
        """Test CloudWatch Log Group is created."""
        template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {
                "RetentionInDays": 7
            }
        )
    
    def test_stack_has_expected_resources(self, template):
        """Test stack has expected number of resources."""
        template.resource_count_is("AWS::Lambda::Function", 1)
        template.resource_count_is("AWS::Events::Rule", 1)
        template.resource_count_is("AWS::IAM::Role", 1)

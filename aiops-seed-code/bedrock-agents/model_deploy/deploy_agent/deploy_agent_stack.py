"""CDK Stack for Bedrock Agent Deployment automation."""
from typing import Any, Dict

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
)
from constructs import Construct


class DeployAgentStack(Stack):
    """CDK Stack for automated Bedrock Agent deployment."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: Dict[str, Any],
        **kwargs
    ) -> None:
        """Initialize the stack.
        
        Args:
            scope: CDK scope
            construct_id: Stack ID
            config: Configuration dictionary
            **kwargs: Additional stack arguments
        """
        super().__init__(scope, construct_id, **kwargs)
        
        self.config = config
        self.environment = config.get("environment", "dev")
        
        # Create IAM role for Lambda
        self.lambda_role = self._create_lambda_role()
        
        # Create deployment Lambda
        self.deploy_lambda = self._create_deploy_lambda()
        
        # Create EventBridge rule for model approval
        self.approval_rule = self._create_approval_event_rule()
    
    def _create_lambda_role(self) -> iam.Role:
        """Create IAM role for deployment Lambda.
        
        Returns:
            IAM Role
        """
        role = iam.Role(
            self,
            "DeployLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Bedrock Agent deployment Lambda"
        )
        
        # CloudWatch Logs permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )
        
        # Bedrock Agent permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:GetAgent",
                    "bedrock:ListAgents",
                    "bedrock:GetAgentAlias",
                    "bedrock:ListAgentAliases",
                    "bedrock:CreateAgentAlias",
                    "bedrock:UpdateAgentAlias",
                    "bedrock:ListAgentVersions"
                ],
                resources=["*"]
            )
        )
        
        # SageMaker Model Registry permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sagemaker:DescribeModelPackage",
                    "sagemaker:ListModelPackages"
                ],
                resources=["*"]
            )
        )
        
        return role
    
    def _create_deploy_lambda(self) -> lambda_.Function:
        """Create deployment Lambda function.
        
        Returns:
            Lambda function
        """
        log_group = logs.LogGroup(
            self,
            "DeployLambdaLogGroup",
            log_group_name=f"/aws/lambda/bedrock-agent-deploy-{self.environment}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        deploy_lambda = lambda_.Function(
            self,
            "DeployLambda",
            function_name=f"bedrock-agent-deploy-{self.environment}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline(self._get_lambda_code()),
            role=self.lambda_role,
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "ENVIRONMENT": self.environment,
                "LOG_LEVEL": self.config.get("log_level", "INFO")
            }
        )
        
        return deploy_lambda
    
    def _get_lambda_code(self) -> str:
        """Get inline Lambda code.
        
        Returns:
            Lambda code as string
        """
        return '''
import json
import logging
import os
import time

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

bedrock_agent = boto3.client("bedrock-agent")
sagemaker = boto3.client("sagemaker")


def handler(event, context):
    """Handle model approval event."""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract model package ARN from event
        detail = event.get("detail", {})
        model_package_arn = detail.get("ModelPackageArn")
        
        if not model_package_arn:
            logger.error("No ModelPackageArn in event")
            return {"statusCode": 400, "body": "Missing ModelPackageArn"}
        
        # Get model package details
        response = sagemaker.describe_model_package(
            ModelPackageName=model_package_arn
        )
        
        metadata = response.get("CustomerMetadataProperties", {})
        agent_id = metadata.get("agent_id")
        agent_alias_id = metadata.get("agent_alias_id")
        
        if not agent_id:
            logger.error("No agent_id in model package metadata")
            return {"statusCode": 400, "body": "Missing agent_id"}
        
        logger.info(f"Deploying agent: {agent_id}")
        
        # Get agent version from staging alias
        staging = bedrock_agent.get_agent_alias(
            agentId=agent_id,
            agentAliasId=agent_alias_id
        )
        
        routing = staging["agentAlias"].get("routingConfiguration", [])
        agent_version = routing[0]["agentVersion"] if routing else "1"
        
        # Create or update production alias
        environment = os.environ.get("ENVIRONMENT", "prod")
        alias_name = f"prod" if environment == "prod" else environment
        
        try:
            # Try to update existing alias
            aliases = bedrock_agent.list_agent_aliases(agentId=agent_id)
            existing = None
            for alias in aliases.get("agentAliasSummaries", []):
                if alias["agentAliasName"] == alias_name:
                    existing = alias
                    break
            
            if existing:
                bedrock_agent.update_agent_alias(
                    agentId=agent_id,
                    agentAliasId=existing["agentAliasId"],
                    agentAliasName=alias_name,
                    routingConfiguration=[{"agentVersion": agent_version}]
                )
                logger.info(f"Updated alias: {alias_name}")
            else:
                bedrock_agent.create_agent_alias(
                    agentId=agent_id,
                    agentAliasName=alias_name,
                    routingConfiguration=[{"agentVersion": agent_version}]
                )
                logger.info(f"Created alias: {alias_name}")
        
        except Exception as e:
            logger.error(f"Error managing alias: {e}")
            raise
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "agent_id": agent_id,
                "agent_version": agent_version,
                "alias": alias_name,
                "status": "deployed"
            })
        }
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return {"statusCode": 500, "body": str(e)}
'''
    
    def _create_approval_event_rule(self) -> events.Rule:
        """Create EventBridge rule for model approval events.
        
        Returns:
            EventBridge Rule
        """
        rule = events.Rule(
            self,
            "ModelApprovalRule",
            rule_name=f"bedrock-agent-approval-{self.environment}",
            description="Trigger deployment when model package is approved",
            event_pattern=events.EventPattern(
                source=["aws.sagemaker"],
                detail_type=["SageMaker Model Package State Change"],
                detail={
                    "ModelApprovalStatus": ["Approved"]
                }
            )
        )
        
        rule.add_target(targets.LambdaFunction(self.deploy_lambda))
        
        return rule

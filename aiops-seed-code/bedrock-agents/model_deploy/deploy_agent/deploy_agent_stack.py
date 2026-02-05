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
        
        # Bedrock Knowledge Base permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:CreateKnowledgeBase",
                    "bedrock:GetKnowledgeBase",
                    "bedrock:ListKnowledgeBases",
                    "bedrock:CreateDataSource",
                    "bedrock:StartIngestionJob"
                ],
                resources=["*"]
            )
        )
        
        # S3 and STS permissions for KB creation
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                    "sts:GetCallerIdentity"
                ],
                resources=["*"]
            )
        )
        
        # IAM PassRole for KB
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "iam:PassedToService": "bedrock.amazonaws.com"
                    }
                }
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
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

bedrock_agent = boto3.client("bedrock-agent")
sagemaker = boto3.client("sagemaker")


def create_knowledge_base(metadata, environment):
    """Create Knowledge Base in target environment using metadata from pipeline.
    
    Args:
        metadata: Model package metadata containing KB configuration
        environment: Target environment name
        
    Returns:
        Knowledge Base ID if created, None otherwise
    """
    kb_name = metadata.get("kb_name")
    if not kb_name:
        logger.info("No Knowledge Base to create (kb_name not in metadata)")
        return None
    
    # Check if KB already exists for this environment
    target_kb_name = f"{kb_name}-{environment}"
    
    try:
        existing_kbs = bedrock_agent.list_knowledge_bases()
        for kb in existing_kbs.get("knowledgeBaseSummaries", []):
            if kb["name"] == target_kb_name:
                logger.info(f"Knowledge Base already exists: {kb['knowledgeBaseId']}")
                return kb["knowledgeBaseId"]
    except ClientError as e:
        logger.warning(f"Error checking existing KBs: {e}")
    
    # Get configuration from metadata
    kb_role_arn = metadata.get("kb_role_arn")
    kb_embedding_model = metadata.get("kb_embedding_model")
    kb_description = metadata.get("kb_description", f"Knowledge Base for {environment}")
    kb_storage_type = metadata.get("kb_storage_type", "S3")
    
    if not kb_role_arn or not kb_embedding_model:
        logger.error("Missing kb_role_arn or kb_embedding_model in metadata")
        return None
    
    # Target bucket for this environment
    region = os.environ.get("AWS_REGION", "us-east-1")
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    target_bucket = f"sagemaker-{region}-{account_id}"
    target_prefix = f"knowledge-base-data/{environment}"
    
    logger.info(f"Creating Knowledge Base: {target_kb_name}")
    logger.info(f"  - Embedding model: {kb_embedding_model}")
    logger.info(f"  - Storage type: {kb_storage_type}")
    logger.info(f"  - Target data location: s3://{target_bucket}/{target_prefix}")
    
    try:
        # Create KB with same configuration as pipeline
        create_response = bedrock_agent.create_knowledge_base(
            name=target_kb_name,
            description=kb_description,
            roleArn=kb_role_arn,
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {
                    "embeddingModelArn": kb_embedding_model
                }
            },
            storageConfiguration={
                "type": kb_storage_type,
                "s3Configuration": {
                    "bucketArn": f"arn:aws:s3:::{target_bucket}"
                }
            }
        )
        
        kb_id = create_response["knowledgeBase"]["knowledgeBaseId"]
        logger.info(f"Created Knowledge Base: {kb_id}")
        
        # Wait for KB to be active
        for _ in range(30):
            status = bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]["status"]
            if status == "ACTIVE":
                break
            time.sleep(10)
        
        # Create data source pointing to environment-specific bucket location
        create_data_source(kb_id, target_bucket, target_prefix)
        
        return kb_id
        
    except ClientError as e:
        logger.error(f"Error creating Knowledge Base: {e}")
        return None


def create_data_source(kb_id, bucket, prefix):
    """Create data source and start ingestion.
    
    Args:
        kb_id: Knowledge Base ID
        bucket: S3 bucket name for this environment
        prefix: S3 prefix for KB data
    
    Note: The data must be uploaded to s3://{bucket}/{prefix}/ before ingestion.
          This is typically done by a separate data pipeline or CI/CD process.
    """
    try:
        response = bedrock_agent.create_data_source(
            knowledgeBaseId=kb_id,
            name=f"ds-{prefix.replace('/', '-')[:20]}",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": f"arn:aws:s3:::{bucket}",
                    "inclusionPrefixes": [prefix] if prefix else []
                }
            }
        )
        
        ds_id = response["dataSource"]["dataSourceId"]
        logger.info(f"Created data source: {ds_id} -> s3://{bucket}/{prefix}")
        
        # Start ingestion
        bedrock_agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
        logger.info(f"Started ingestion for: {ds_id}")
        
    except ClientError as e:
        logger.error(f"Error creating data source s3://{bucket}/{prefix}: {e}")


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
        
        # Get environment
        environment = os.environ.get("ENVIRONMENT", "prod")
        
        # Create Knowledge Base if metadata contains KB info
        kb_id = None
        if metadata.get("kb_name"):
            kb_id = create_knowledge_base(metadata, environment)
        
        # Get agent version from staging alias
        staging = bedrock_agent.get_agent_alias(
            agentId=agent_id,
            agentAliasId=agent_alias_id
        )
        
        routing = staging["agentAlias"].get("routingConfiguration", [])
        agent_version = routing[0]["agentVersion"] if routing else "1"
        
        # Create or update production alias
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
                "knowledge_base_id": kb_id,
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

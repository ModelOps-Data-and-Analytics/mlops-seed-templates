from aws_cdk import (
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    custom_resources as cr,
    aws_secretsmanager as secretsmanager,
    RemovalPolicy,
    Aws,
    CfnOutput
)
from constructs import Construct
import boto3
from .constructs.lambda_construct import LambdaConstruct
from .constructs.model_approval_lambda_construct import ModelApprovalLambdaConstruct
from .constructs.git_layer import GitLayerConstruct
from .constructs.dependency_layer import DependencyLayerConstruct
from .config import config

class RepoSyncStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        role_name = config.oidc_role_github_workflow
        account_id = Aws.ACCOUNT_ID
        github_org = config.private_github_organization

        # Custom resource to check if role exists
        check_role_exists = cr.AwsCustomResource(
            self, "CheckRoleExists",
            on_create=cr.AwsSdkCall(
                service="IAM",
                action="getRole",
                parameters={"RoleName": role_name},
                physical_resource_id=cr.PhysicalResourceId.of(f"{role_name}-exists"),
                ignore_error_codes_matching="NoSuchEntity"
            ),
            on_update=cr.AwsSdkCall(
                service="IAM",
                action="getRole",
                parameters={"RoleName": role_name},
                physical_resource_id=cr.PhysicalResourceId.of(f"{role_name}-exists"),
                ignore_error_codes_matching="NoSuchEntity"
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE)
        )

        try:
            check_role_exists.get_response_field("Role.Arn")
            print(f"Found existing role: {role_name}")
            github_workflow_role = iam.Role.from_role_name(
                self, "GitHubWorkflowRole",
                role_name=role_name
            )

        except:

            
            print(f"Creating new IDP")
            # Create the OIDC Provider 
            github_provider = iam.OpenIdConnectProvider(
                self, "GitHubProvider",
                url="https://token.actions.githubusercontent.com",
                client_ids=["sts.amazonaws.com"]
            )
            github_provider.node.default_child.apply_removal_policy(RemovalPolicy.RETAIN)

            print(f"Creating new role: {role_name}")
            github_workflow_role = iam.Role(
                self, "GitHubWorkflowRole",
                role_name=role_name,
                assumed_by=iam.CompositePrincipal(
                    iam.FederatedPrincipal(
                        federated=f"arn:aws:iam::{account_id}:oidc-provider/token.actions.githubusercontent.com",
                        conditions={
                            "StringEquals": {
                                "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                            },
                            "StringLike": {
                                "token.actions.githubusercontent.com:sub": [
                                    f"repo:{github_org}/*" 
                                ]
                            }
                        },
                        assume_role_action="sts:AssumeRoleWithWebIdentity"
                    ),
                    iam.AccountRootPrincipal()
                )
            )
            github_workflow_role.node.default_child.apply_removal_policy(RemovalPolicy.RETAIN)
            # Add policies for new role
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sagemaker:CreatePipeline",
                    "sagemaker:UpdatePipeline",
                    "sagemaker:StartPipelineExecution",
                    "sagemaker:DescribePipeline",
                    "sagemaker:DescribePipelineExecution",
                    "sagemaker:ListPipelineExecutions",
                    "sagemaker:AddTags",
                    "sagemaker:ListTags",
                    "sagemaker:ListProcessingJobs",
                    "sagemaker:DescribeProcessingJob",
                    "sagemaker:DescribeImageVersion",
                    "sagemaker:CreateProcessingJob",
                    "sagemaker:ListPipelineExecutionSteps",
                    "sagemaker:ListModelPackages",
                    "sagemaker:StopProcessingJob"
                ],
                resources=["*"]
            ))
            # Add cloudformation stack permissions
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudformation:ListStacks",
                    "cloudformation:DescribeStacks",
                    "cloudformation:CreateStack",
                    "cloudformation:UpdateStack",
                    "cloudformation:DeleteStack",
                    "cloudformation:ListStackResources",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:GetTemplateSummary",
                    "cloudformation:ValidateTemplate",
                    "cloudformation:GetTemplate",
                    "cloudformation:CreateChangeSet",
                    "cloudformation:DeleteChangeSet",
                    "cloudformation:ListChangeSets",
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:ExecuteChangeSet",
                    "cloudformation:SetStackPolicy",
                    "cloudformation:DescribeStackResource"
                ],
                resources=["*"]
            ))
            # Add ECR permissions
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:CreateRepository",
                    "ecr:DeleteRepository",
                    "ecr:DescribeRepositories",
                    "ecr:PutLifecyclePolicy",
                    "ecr:SetRepositoryPolicy"
                ],
                resources=["*"]
            ))
            # Add SSM permissions
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:*"
                ],
                resources=["arn:aws:ssm:*:*:parameter/cdk-bootstrap/*"]
            ))
            # Add IAM permissions
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:CreateRole",
                    "iam:Get*",
                    "iam:Delete*",
                    "iam:List*",
                    "iam:Put*",
                    "iam:Tag*",
                    "iam:Attach*",
                    "iam:Detach*",
                    "iam:Update*"
                ],
                resources=["*"]
            ))
            # Add S3 permissions
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:Put*",
                    "s3:Get*",
                    "s3:List*",
                    "s3:Create*",
                    "s3:Delete*"
                ],
                resources=["*"]
            ))
            # Assume role permissions
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sts:AssumeRole"
                ],
                resources=[
                    "arn:aws:iam::*:role/cdk-*",
                    "arn:aws:iam::*:role/cdk-gitactions-*"
                ]
            ))
            # Add Glue permissions
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "glue:GetTable",
                    "glue:GetDatabase",
                    "glue:GetPartitions"
                ],
                resources=["*"]
            ))
            
            # Add IAM PassRole permission
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "iam:PassedToService": "sagemaker.amazonaws.com"
                    }
                }
            ))
            
            # Add CloudWatch Logs permissions
            github_workflow_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            ))
            
        
        # Create base EventBridge role first
        events_role = iam.Role(
            self, "EventBridgeRole",
            role_name="ml-ops-smus-eventbridge-role-v2",
            assumed_by=iam.ServicePrincipal("events.amazonaws.com")
        )
        
        # Use existing secret instead of creating a new one
        github_token_secret = secretsmanager.Secret.from_secret_name_v2(
            self, 'GitHubTokenSecret',
            secret_name=config.github_token_secret_name
        )

        git_layer = GitLayerConstruct(self, "GitLayer")
        dependency_layer = DependencyLayerConstruct(self, "DependencyLayer")

        #  Create Lambda construct (includes Step Function)
        repo_sync = LambdaConstruct(
            self, 
            "RepoSyncLambda",
            github_workflow_role_arn=github_workflow_role.role_arn,
            github_token_secret=github_token_secret, 
            git_layer=git_layer, 
            dependency_layer=dependency_layer
            )

        # Create Model Approval Lambda construct
        model_approval = ModelApprovalLambdaConstruct(
            self, 
            "ModelApprovalConstruct",
            github_token_secret=github_token_secret,
            git_layer=git_layer, 
            dependency_layer=dependency_layer 
        )
        
        #  Add Step Functions execution permissions after state machine is created
        events_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["states:StartExecution"],
                resources=[repo_sync.state_machine.state_machine_arn]
            )
        )

        #  Create EventBridge rule
        rule = events.Rule(
            self, "DataZoneProjectRule",
            rule_name="ml-ops-smus-datazone-project-rule-v2",
            description="Triggers Step Functions on DataZone Project Creation",
            enabled=True,
            event_pattern=events.EventPattern(
                source=["aws.datazone"],
                detail_type=["AWS API Call via CloudTrail"],
                detail={
                    "eventSource": ["datazone.amazonaws.com"],
                    "eventName": ["CreateProject"]
                }
            ),
            targets=[
                targets.SfnStateMachine(
                    repo_sync.state_machine,
                    role=events_role
                )
            ]
        )

        #  Add removal policies
        rule.apply_removal_policy(RemovalPolicy.DESTROY)
        events_role.apply_removal_policy(RemovalPolicy.DESTROY)

        #  Outputs
        CfnOutput(self, "StateMachineArn",
                 value=repo_sync.state_machine.state_machine_arn,
                 description="ARN of the Step Functions state machine")
        
        CfnOutput(self, "EventBridgeRuleName", 
                 value=rule.rule_name,
                 description="Name of the created EventBridge rule")
        
        CfnOutput(self, "EventBridgeRoleArn", 
                 value=events_role.role_arn,
                 description="ARN of the created EventBridge role")
        
        CfnOutput(self, "GitHubWorkflowRoleArn", 
                 value=github_workflow_role.role_arn,
                 description="ARN of the SageMaker pipeline role")

        CfnOutput(
            self, "ModelApprovalLambdaArn",
            value=model_approval.lambda_function.function_arn,
            description="ARN of the Model Approval Lambda function"
        )

        CfnOutput(
            self, "ModelApprovalRuleName",
            value=model_approval.event_rule.ref,
            description="Name of the Model Approval EventBridge rule"
        )

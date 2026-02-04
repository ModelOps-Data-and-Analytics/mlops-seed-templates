#!/usr/bin/env python3
"""CDK app for Bedrock Agent deployment."""
import os

import aws_cdk as cdk

from deploy_agent.deploy_agent_stack import DeployAgentStack
from config.config_mux import get_config

app = cdk.App()

# Get environment from context or default to dev
environment = app.node.try_get_context("environment") or os.getenv("ENVIRONMENT", "dev")
config = get_config(environment)

DeployAgentStack(
    app,
    f"BedrockAgentDeploy-{environment}",
    config=config,
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)

app.synth()

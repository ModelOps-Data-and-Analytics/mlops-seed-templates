"""Shared constants for deployment."""

# AWS Configuration
AWS_REGION = "us-east-1"

# Model Registry
MODEL_PACKAGE_GROUP_NAME = "BedrockAgentPackageGroup"

# Agent defaults
DEFAULT_IDLE_SESSION_TTL = 1800  # 30 minutes
DEFAULT_FOUNDATION_MODEL = "anthropic.claude-3-7-sonnet-20250219-v1:0"

# Alias names
ALIAS_STAGING = "staging"
ALIAS_PRODUCTION = "prod"

# Tags
DEFAULT_TAGS = {
    "Project": "bedrock-agents-aiops",
    "ManagedBy": "CDK"
}

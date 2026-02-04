"""Development environment constants."""

ENVIRONMENT = "dev"
AWS_ACCOUNT = ""  # Set via environment variable

# Model Registry
MODEL_PACKAGE_GROUP_NAME = "BedrockAgentPackageGroup-dev"

# Agent Configuration
AGENT_NAME = "customer-service-agent-dev"

# Monitoring
ENABLE_DETAILED_MONITORING = True
LOG_LEVEL = "DEBUG"

# Tags
TAGS = {
    "Environment": "dev",
    "Project": "bedrock-agents-aiops"
}

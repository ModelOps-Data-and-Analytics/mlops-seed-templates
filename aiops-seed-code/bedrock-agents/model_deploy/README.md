# Bedrock Agent Deployment (model_deploy)

This directory contains the CDK stack and deployment scripts for deploying approved Bedrock Agents to production environments.

## Directory Structure

```
model_deploy/
├── app.py                      # CDK app entry point
├── cdk.json                    # CDK configuration
├── deploy_agent.py             # Agent deployment script
├── Makefile                    # Build and deploy commands
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Development dependencies
├── config/
│   ├── config_mux.py          # Configuration multiplexer
│   ├── constants.py           # Shared constants
│   └── dev/
│       ├── constants.py       # Dev environment constants
│       └── agent-config.yml   # Agent deployment config
├── deploy_agent/
│   ├── __init__.py
│   ├── deploy_agent_stack.py  # CDK stack for deployment
│   └── get_approved_package.py # Fetch approved model package
└── tests/
    ├── integration_tests/
    │   ├── __init__.py
    │   ├── conftest.py
    │   └── test_agent_deployment.py
    └── unittests/
        ├── __init__.py
        └── test_deploy_stack.py
```

## Deployment Flow

1. **Model Approval**: When an agent is approved in SageMaker Model Registry
2. **EventBridge Trigger**: Triggers the deployment workflow
3. **Get Approved Package**: Fetch agent details from model package
4. **Create Production Alias**: Create or update production alias
5. **Run Integration Tests**: Validate agent responses
6. **Update Routing**: Route traffic to new version

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `AWS_REGION` | AWS region for deployment |
| `AGENT_ID` | Bedrock Agent ID |
| `ENVIRONMENT` | Target environment (dev/staging/prod) |
| `MODEL_PACKAGE_GROUP` | SageMaker Model Package Group name |

### Agent Configuration (agent-config.yml)

```yaml
agent:
  idle_session_ttl: 1800
  guardrails:
    enabled: true
    content_filter_level: MEDIUM
  alias:
    production:
      routing_config:
        version: LATEST
```

## Usage

### Deploy Agent

```bash
# Deploy to dev environment
make deploy-dev

# Deploy to production
make deploy-prod

# Deploy specific agent
python deploy_agent.py \
  --agent-id XXXXXXXXXX \
  --source-alias-id staging \
  --target-alias prod \
  --region us-east-1
```

### Run Tests

```bash
# Unit tests
make test-unit

# Integration tests
make test-integration AGENT_ID=XXXXXXXXXX
```

## CDK Stack

The CDK stack creates:
- EventBridge rule for model approval events
- Lambda function for deployment automation
- IAM roles with least privilege permissions
- CloudWatch alarms for agent monitoring

## Rollback

To rollback to a previous version:

```bash
python deploy_agent.py \
  --agent-id XXXXXXXXXX \
  --rollback \
  --target-version <previous-version>
```

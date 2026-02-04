# Bedrock Agents - Model Build

This directory contains the code for building and configuring Amazon Bedrock Agents using SageMaker Pipelines.

## Directory Structure

```
model_build/
├── README.md                          # This file
├── Makefile                           # Build automation commands
├── getting_started.ipynb              # Interactive notebook for exploration
├── ml_pipelines/                      # SageMaker Pipeline definitions
│   ├── __init__.py
│   ├── __version__.py
│   ├── _utils.py
│   ├── get_pipeline_definition.py
│   ├── run_pipeline.py
│   ├── requirements.txt
│   ├── agent_config/                  # Agent configuration files
│   │   ├── agent_instruction.txt      # Agent instructions/prompts
│   │   ├── agent_schema.json          # OpenAPI schema for action groups
│   │   └── knowledge_base_config.yaml # Knowledge base configuration
│   └── agent_build/                   # Pipeline definition for agents
│       ├── __init__.py
│       ├── _utils.py
│       ├── pipeline.py                # Main pipeline definition
│       └── README.md
├── source_scripts/                    # Processing scripts for pipeline steps
│   ├── setup/                         # Setup and validation step
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── create_agent/                  # Create/update Bedrock agent
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── knowledge_base/                # Create/update knowledge base
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── action_groups/                 # Deploy action group lambdas
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── lambda_functions/          # Lambda function code
│   │       ├── get_customer_info/
│   │       │   ├── main.py
│   │       │   └── requirements.txt
│   │       └── process_order/
│   │           ├── main.py
│   │           └── requirements.txt
│   ├── prepare_agent/                 # Prepare agent for deployment
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── evaluate/                      # Evaluate agent responses
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── test_cases.json
│   └── helpers/                       # Shared utilities
│       ├── __init__.py
│       ├── logger.py
│       ├── bedrock_helper.py
│       └── requirements.txt
└── .github/
    └── workflows/
        └── build-agent-pipeline.yml   # GitHub Actions workflow
```

## Pipeline Steps

The SageMaker Pipeline for Bedrock Agents consists of the following steps:

| Step | Name | Description |
|------|------|-------------|
| 1 | SetupAndValidation | Validates configuration and prerequisites |
| 2 | CreateBedrockAgent | Creates or updates the Bedrock agent |
| 3 | CreateKnowledgeBase | Creates knowledge base with S3 data source |
| 4 | DeployActionGroups | Deploys Lambda functions for action groups |
| 5 | AssociateComponents | Associates KB and action groups to agent |
| 6 | PrepareAgent | Prepares agent DRAFT version |
| 7 | EvaluateAgent | Runs test cases against the agent |
| 8 | ConditionCheck | Checks if success rate >= 80% |
| 9 | RegisterAgent | Registers agent in Model Registry |

## Configuration

### Agent Instructions (`agent_config/agent_instruction.txt`)
Contains the system prompt and instructions for the agent's behavior.

### Action Group Schema (`agent_config/agent_schema.json`)
OpenAPI 3.0 schema defining the available actions the agent can perform.

### Knowledge Base Config (`agent_config/knowledge_base_config.yaml`)
Configuration for the knowledge base including:
- S3 data source location
- Embedding model selection
- Chunking strategy

## Usage

### Local Development
```bash
# Install dependencies
make install

# Run pipeline locally (dry run)
make test-pipeline

# Validate configuration
make validate
```

### GitHub Actions
The pipeline is triggered automatically when:
- Code is pushed to main branch
- Workflow is manually dispatched

Set `TRIGGER_PIPELINE_EXECUTION=true` in GitHub repository variables to enable execution.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AWS_REGION` | AWS region for deployment | Yes |
| `SAGEMAKER_ROLE_ARN` | IAM role for SageMaker | Yes |
| `PROJECT_ID` | SMUS project ID | Yes |
| `AGENT_NAME` | Name for the Bedrock agent | Yes |
| `FOUNDATION_MODEL` | Foundation model ID (default: Claude 3 Sonnet) | No |
| `KNOWLEDGE_BASE_S3_URI` | S3 URI for knowledge base data | No |

## Model Registry

Successful agent builds are registered in SageMaker Model Registry with:
- Agent ID
- Agent Alias ID (staging)
- Foundation Model used
- Evaluation metrics
- Configuration metadata

The model package status is set to `PendingManualApproval` for review before deployment.

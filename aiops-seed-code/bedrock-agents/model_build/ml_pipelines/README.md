# ML Pipelines for Bedrock Agents

This directory contains the SageMaker Pipeline definitions for building and configuring Amazon Bedrock Agents.

## Structure

```
ml_pipelines/
├── __init__.py
├── __version__.py
├── _utils.py                    # Shared utilities
├── get_pipeline_definition.py   # Pipeline definition generator
├── run_pipeline.py              # Pipeline execution script
├── requirements.txt             # Python dependencies
├── agent_config/                # Agent configuration files
│   ├── agent_instruction.txt    # Agent system prompt
│   ├── agent_schema.json        # OpenAPI schema for actions
│   └── knowledge_base_config.yaml
└── agent_build/                 # Pipeline definition
    ├── __init__.py
    ├── pipeline.py              # Main pipeline
    └── README.md
```

## Pipeline Overview

The pipeline orchestrates the following steps:

1. **Setup & Validation** - Validates configuration and prerequisites
2. **Create Agent** - Creates/updates the Bedrock agent
3. **Create Knowledge Base** - Sets up knowledge base with embeddings
4. **Deploy Action Groups** - Deploys Lambda functions
5. **Associate Components** - Links KB and actions to agent
6. **Prepare Agent** - Prepares the DRAFT version
7. **Evaluate Agent** - Runs test cases
8. **Register** - Registers in Model Registry (if eval passes)

## Usage

```python
from ml_pipelines.agent_build.pipeline import get_pipeline

pipeline = get_pipeline(
    region="us-east-1",
    role="arn:aws:iam::123456789012:role/SageMakerRole",
    agent_name="my-customer-service-agent",
    foundation_model="anthropic.claude-3-7-sonnet-20250219-v1:0"
)

pipeline.upsert(role_arn=role)
pipeline.start()
```

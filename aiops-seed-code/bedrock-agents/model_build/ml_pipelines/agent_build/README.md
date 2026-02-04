# Agent Build Pipeline

This directory contains the SageMaker Pipeline definition for building Amazon Bedrock Agents.

## Pipeline Steps

```
┌─────────────────────────────────────────────────────────────────┐
│                    SageMaker ML Pipeline                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐                                              │
│  │ 1. Setup &   │──┐                                           │
│  │   Validation │  │                                           │
│  └──────────────┘  │                                           │
│                    ▼                                           │
│  ┌──────────────┐                                              │
│  │ 2. Create    │──┐                                           │
│  │   Agent      │  │                                           │
│  └──────────────┘  │                                           │
│                    ▼                                           │
│  ┌──────────────┐                                              │
│  │ 3. Create    │──┐                                           │
│  │   KB (RAG)   │  │                                           │
│  └──────────────┘  │                                           │
│                    ▼                                           │
│  ┌──────────────┐                                              │
│  │ 4. Deploy    │──┐                                           │
│  │   Actions    │  │                                           │
│  └──────────────┘  │                                           │
│                    ▼                                           │
│  ┌──────────────┐                                              │
│  │ 5. Prepare   │──┐                                           │
│  │   Agent      │  │                                           │
│  └──────────────┘  │                                           │
│                    ▼                                           │
│  ┌──────────────┐                                              │
│  │ 6. Evaluate  │──┐                                           │
│  │   Agent      │  │                                           │
│  └──────────────┘  │                                           │
│                    ▼                                           │
│  ┌──────────────┐     ┌──────────────┐                        │
│  │ 7. Condition │────▶│ 8. Register  │                        │
│  │   ≥80%?      │ Yes │   Model      │                        │
│  └──────────────┘     └──────────────┘                        │
│         │ No                                                   │
│         ▼                                                      │
│  ┌──────────────┐                                              │
│  │   FailStep   │                                              │
│  └──────────────┘                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `AgentName` | Name for the Bedrock agent | Required |
| `FoundationModel` | Foundation model ID | Claude 3 Sonnet |
| `ProcessingInstanceType` | Instance for processing jobs | ml.m5.xlarge |
| `ModelApprovalStatus` | Initial approval status | PendingManualApproval |
| `EnableKnowledgeBase` | Whether to create KB | true |
| `EnableActionGroups` | Whether to deploy actions | true |
| `EvaluationThreshold` | Minimum success rate | 0.8 |

## Usage

```python
from ml_pipelines.agent_build.pipeline import get_pipeline

pipeline = get_pipeline(
    region="us-east-1",
    role="arn:aws:iam::123456789012:role/SageMakerRole",
    agent_name="customer-service-agent",
    project_id="my-project-123"
)
```

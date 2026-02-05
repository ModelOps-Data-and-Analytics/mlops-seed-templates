# Bedrock Agents Project Profile

Este project profile implementa un flujo completo de MLOps para **Amazon Bedrock Agents**, siguiendo el mismo patrón arquitectónico del profile `regression` pero adaptado para agentes de IA generativa.

## 📋 Descripción

El profile `bedrock-agents` permite:
- Crear y configurar agentes de Amazon Bedrock con Knowledge Bases y Action Groups
- Ejecutar pipelines de construcción automatizados via SageMaker Pipelines
- Evaluar agentes con casos de prueba automatizados
- Registrar versiones de agentes en SageMaker Model Registry
- Desplegar agentes aprobados automáticamente a producción

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         BEDROCK AGENTS MLOps                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐    ┌──────────────────┐    ┌─────────────────────────┐    │
│  │ GitHub  │───▶│ SageMaker        │───▶│ Model Registry          │    │
│  │ Actions │    │ Pipeline         │    │ (PendingManualApproval) │    │
│  └─────────┘    └──────────────────┘    └───────────┬─────────────┘    │
│                          │                          │                    │
│                          ▼                          ▼                    │
│              ┌──────────────────────┐    ┌─────────────────────┐        │
│              │ Bedrock Agent        │    │ EventBridge         │        │
│              │ ├─ Knowledge Base    │    │ (on Approval)       │        │
│              │ └─ Action Groups     │    └──────────┬──────────┘        │
│              └──────────────────────┘               │                    │
│                                                     ▼                    │
│                                         ┌─────────────────────┐          │
│                                         │ Production Alias    │          │
│                                         └─────────────────────┘          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 📁 Estructura del Directorio

```
bedrock-agents/
├── README.md                    # Este archivo
├── model_build/                 # Pipeline de construcción
│   ├── README.md
│   ├── Makefile
│   ├── .gitignore
│   ├── .github/
│   │   └── workflows/
│   │       ├── build-agent-pipeline.yml
│   │       └── deploy-agent.yml
│   ├── ml_pipelines/
│   │   ├── run_pipeline.py
│   │   ├── requirements.txt
│   │   ├── agent_build/
│   │   │   └── pipeline.py      # SageMaker Pipeline definition
│   │   └── agent_config/
│   │       ├── agent_instruction.txt
│   │       ├── agent_schema.json
│   │       └── knowledge_base_config.yaml
│   └── source_scripts/
│       ├── setup/               # Validación de configuración
│       ├── create_agent/        # Creación del agente
│       ├── knowledge_base/      # Knowledge Base con S3 Vectors
│       ├── action_groups/       # Lambda functions para acciones
│       ├── prepare_agent/       # Preparar y crear alias
│       ├── evaluate/            # Evaluación con test cases
│       ├── register/            # Registro en Model Registry
│       └── helpers/             # Utilidades compartidas
│
└── model_deploy/                # Infraestructura de deployment
    ├── README.md
    ├── Makefile
    ├── app.py                   # CDK entry point
    ├── cdk.json
    ├── deploy_agent.py          # Script de deployment
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── config/
    │   ├── config_mux.py
    │   ├── constants.py
    │   └── dev/
    ├── deploy_agent/
    │   ├── deploy_agent_stack.py
    │   └── get_approved_package.py
    └── tests/
        ├── integration_tests/
        └── unittests/
```

## 🚀 Quick Start

### Prerrequisitos

- Python 3.11+
- AWS CLI configurado
- CDK CLI instalado
- Permisos para Bedrock, SageMaker, Lambda, S3

### 1. Clonar y configurar

```bash
cd aiops-seed-code/bedrock-agents/model_build

# Instalar dependencias
pip install -r ml_pipelines/requirements.txt
```

### 2. Configurar el agente

Editar los archivos de configuración:
- `ml_pipelines/agent_config/agent_instruction.txt` - Instrucciones del agente
- `ml_pipelines/agent_config/agent_schema.json` - OpenAPI schema para acciones
- `ml_pipelines/agent_config/knowledge_base_config.yaml` - Configuración de KB

### 3. Ejecutar el pipeline

```bash
# Ejecutar localmente
make run-pipeline AGENT_NAME=my-agent ENVIRONMENT=dev

# O via GitHub Actions
git push origin main
```

### 4. Aprobar el modelo

Una vez evaluado, aprobar el modelo en SageMaker Model Registry:

```bash
aws sagemaker update-model-package \
    --model-package-arn <ARN> \
    --model-approval-status Approved
```

### 5. Deployment automático

El deployment se ejecuta automáticamente cuando se aprueba el modelo via EventBridge.

## 🔄 Pasos del Pipeline

| Step | Descripción | Outputs |
|------|-------------|---------|
| 1. SetupAndValidation | Valida configuración y disponibilidad de modelo | Config validada |
| 2. CreateBedrockAgent | Crea/actualiza el agente en Bedrock | Agent ID |
| 3. CreateKnowledgeBase | Configura Knowledge Base con S3 Vectors | KB ID |
| 4. DeployActionGroups | Despliega Lambdas y Action Groups | Action Group IDs |
| 5. PrepareAgent | Prepara el agente y crea alias staging | Staging Alias |
| 6. EvaluateAgent | Ejecuta test cases automatizados | Success Rate |
| 7. CheckResults | Verifica si pasa el umbral (80%) | Pass/Fail |
| 8. RegisterModel | Registra en Model Registry | Model Package ARN |

## 🧪 Testing

```bash
# Unit tests
cd model_deploy
make test-unit

# Integration tests (requiere agent-id)
make test-integration AGENT_ID=XXXXXXXXXX
```

## 📊 Métricas y Evaluación

El pipeline evalúa el agente con casos de prueba definidos en `source_scripts/evaluate/test_cases.json`:

```json
{
  "prompt": "¿Cuál es el estado de mi orden ORD-12345?",
  "expected_keywords": ["order", "status", "tracking"],
  "expected_action_group": "process_order"
}
```

El umbral de éxito por defecto es **80%**.

## 🌐 Cross-Region Inference

Este profile utiliza **Claude 3.7 Sonnet** con soporte para **Cross-Region Inference**, lo que permite:

- ✅ Invocar el modelo desde regiones donde puede no estar disponible directamente
- ✅ Failover automático a otras regiones si la región primaria no está disponible
- ✅ Mayor disponibilidad y resiliencia para cargas de trabajo de producción

### Regiones Soportadas

| Región Primaria | Regiones de Fallback |
|-----------------|---------------------|
| `us-east-1` | `us-west-2`, `eu-west-1` |
| `us-west-2` | `us-east-1`, `eu-west-1` |
| `eu-west-1` | `us-east-1`, `us-west-2` |

### Permisos Requeridos para Cross-Region

```json
{
  "Sid": "BedrockCrossRegionInference",
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:GetInferenceProfile",
    "bedrock:ListInferenceProfiles"
  ],
  "Resource": [
    "arn:aws:bedrock:us-east-1::foundation-model/*",
    "arn:aws:bedrock:us-west-2::foundation-model/*",
    "arn:aws:bedrock:*:*:inference-profile/*"
  ]
}
```

## 🔐 Permisos IAM Requeridos

El rol de ejecución de SageMaker Pipeline necesita la siguiente política:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockAgentFullAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:CreateAgent",
                "bedrock:UpdateAgent",
                "bedrock:DeleteAgent",
                "bedrock:GetAgent",
                "bedrock:ListAgents",
                "bedrock:PrepareAgent",
                "bedrock:CreateAgentAlias",
                "bedrock:UpdateAgentAlias",
                "bedrock:DeleteAgentAlias",
                "bedrock:GetAgentAlias",
                "bedrock:ListAgentAliases",
                "bedrock:CreateAgentActionGroup",
                "bedrock:UpdateAgentActionGroup",
                "bedrock:DeleteAgentActionGroup",
                "bedrock:GetAgentActionGroup",
                "bedrock:ListAgentActionGroups",
                "bedrock:AssociateAgentKnowledgeBase",
                "bedrock:DisassociateAgentKnowledgeBase",
                "bedrock:ListAgentKnowledgeBases",
                "bedrock:GetAgentVersion",
                "bedrock:ListAgentVersions",
                "bedrock:TagResource",
                "bedrock:UntagResource",
                "bedrock:ListTagsForResource"
            ],
            "Resource": "*"
        },
        {
            "Sid": "BedrockKnowledgeBaseAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:CreateKnowledgeBase",
                "bedrock:UpdateKnowledgeBase",
                "bedrock:DeleteKnowledgeBase",
                "bedrock:GetKnowledgeBase",
                "bedrock:ListKnowledgeBases",
                "bedrock:CreateDataSource",
                "bedrock:UpdateDataSource",
                "bedrock:DeleteDataSource",
                "bedrock:GetDataSource",
                "bedrock:ListDataSources",
                "bedrock:StartIngestionJob",
                "bedrock:GetIngestionJob",
                "bedrock:ListIngestionJobs",
                "bedrock:Retrieve",
                "bedrock:RetrieveAndGenerate"
            ],
            "Resource": "*"
        },
        {
            "Sid": "BedrockModelAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:InvokeAgent",
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel",
                "bedrock:GetInferenceProfile",
                "bedrock:ListInferenceProfiles"
            ],
            "Resource": "*"
        },
        {
            "Sid": "LambdaForActionGroups",
            "Effect": "Allow",
            "Action": [
                "lambda:CreateFunction",
                "lambda:UpdateFunctionCode",
                "lambda:UpdateFunctionConfiguration",
                "lambda:DeleteFunction",
                "lambda:GetFunction",
                "lambda:GetFunctionConfiguration",
                "lambda:ListFunctions",
                "lambda:InvokeFunction",
                "lambda:AddPermission",
                "lambda:RemovePermission",
                "lambda:GetPolicy",
                "lambda:TagResource",
                "lambda:UntagResource"
            ],
            "Resource": "*"
        },
        {
            "Sid": "IAMPassRole",
            "Effect": "Allow",
            "Action": [
                "iam:PassRole",
                "iam:GetRole",
                "iam:CreateRole",
                "iam:AttachRolePolicy",
                "iam:PutRolePolicy"
            ],
            "Resource": "*"
        },
        {
            "Sid": "S3FullAccessForKnowledgeBase",
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:DeleteBucket",
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:PutBucketPolicy",
                "s3:GetBucketPolicy",
                "s3:PutBucketVersioning",
                "s3:GetBucketVersioning"
            ],
            "Resource": "*"
        },
        {
            "Sid": "OpenSearchServerlessForVectorStore",
            "Effect": "Allow",
            "Action": [
                "aoss:CreateCollection",
                "aoss:DeleteCollection",
                "aoss:UpdateCollection",
                "aoss:BatchGetCollection",
                "aoss:ListCollections",
                "aoss:CreateAccessPolicy",
                "aoss:DeleteAccessPolicy",
                "aoss:UpdateAccessPolicy",
                "aoss:GetAccessPolicy",
                "aoss:ListAccessPolicies",
                "aoss:CreateSecurityPolicy",
                "aoss:DeleteSecurityPolicy",
                "aoss:UpdateSecurityPolicy",
                "aoss:GetSecurityPolicy",
                "aoss:ListSecurityPolicies",
                "aoss:APIAccessAll"
            ],
            "Resource": "*"
        },
        {
            "Sid": "SageMakerModelRegistry",
            "Effect": "Allow",
            "Action": [
                "sagemaker:CreateModelPackage",
                "sagemaker:CreateModelPackageGroup",
                "sagemaker:DescribeModelPackage",
                "sagemaker:DescribeModelPackageGroup",
                "sagemaker:ListModelPackages",
                "sagemaker:ListModelPackageGroups",
                "sagemaker:UpdateModelPackage",
                "sagemaker:AddTags"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CloudWatchLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams"
            ],
            "Resource": "*"
        }
    ]
}
```

### Permisos por Stage del Pipeline

| Stage | Permisos Requeridos |
|-------|---------------------|
| SetupAndValidation | `bedrock:ListFoundationModels`, `GetFoundationModel` |
| CreateBedrockAgent | `bedrock:CreateAgent`, `UpdateAgent`, `ListAgents`, `GetAgent` |
| CreateKnowledgeBase | `bedrock:CreateKnowledgeBase`, `CreateDataSource`, `StartIngestionJob`, `aoss:*` |
| DeployActionGroups | `lambda:CreateFunction`, `UpdateFunctionCode`, `AddPermission`, `iam:PassRole` |
| PrepareAgent | `bedrock:PrepareAgent`, `CreateAgentAlias` |
| EvaluateAgent | `bedrock:InvokeAgent`, `InvokeModel` |
| RegisterAgentModel | `sagemaker:CreateModelPackage`, `CreateModelPackageGroup` |

## 📚 Referencias

- [Amazon Bedrock Agents Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Cross-Region Inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)
- [SageMaker Pipelines](https://docs.aws.amazon.com/sagemaker/latest/dg/pipelines.html)
- [CDK Python Reference](https://docs.aws.amazon.com/cdk/api/v2/python/)

## 🤝 Contribuir

Ver [CONTRIBUTING.md](../../CONTRIBUTING.md) en el directorio raíz del proyecto.

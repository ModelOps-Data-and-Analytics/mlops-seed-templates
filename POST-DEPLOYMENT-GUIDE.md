# Guía de Configuración Post-Creación de Proyecto

## 1. Esperar a que el Proyecto se Cree (5-10 minutos)

Después de crear el proyecto en SMUS, espera a que:
- ✅ Los 2 repositorios aparezcan en GitHub:
  - `mlops-test-build`
  - `{project-id}-dzd_4jzjk46dkwid0n-deploy-repo`
- ✅ El proyecto esté en estado ACTIVE en SMUS

## 2. Configurar Glue Database y Tabla

Ejecutar desde el directorio raíz del proyecto:

```bash
cd /Users/julian.mazo/Documents/modelops/sample-smus-aiops
./setup-glue-database.sh
```

Este script:
- Busca la base de datos Glue creada por el proyecto
- Sube el dataset abalone a S3
- Crea la tabla `abalone` con el schema correcto
- Muestra los valores para actualizar en GitHub Secrets

## 3. Actualizar GitHub Secrets

### En el repositorio BUILD (`mlops-test-build`):

1. Ir a: `https://github.com/ModelOps-Data-and-Analytics/mlops-test-build`
2. Settings → Secrets and variables → Actions
3. Actualizar estos secrets:
   - `GLUE_DATABASE`: El valor mostrado por el script
   - `GLUE_TABLE`: `abalone`

### En el repositorio DEPLOY (`{project-id}-dzd_4jzjk46dkwid0n-deploy-repo`):

1. Ir al repositorio de deploy
2. Settings → Secrets and variables → Actions
3. Actualizar los mismos secrets:
   - `GLUE_DATABASE`: El valor mostrado por el script
   - `GLUE_TABLE`: `abalone`

## 4. Habilitar Ejecución del Pipeline

En el repositorio BUILD:

1. Settings → Secrets and variables → Actions → **Variables** tab
2. Crear nueva variable:
   - **Name**: `TRIGGER_PIPELINE_EXECUTION`
   - **Value**: `true`
3. Click "Add variable"

## 5. Ejecutar el Primer Pipeline

### Opción A - Manual (Recomendado para primera vez):
1. Ir a: Actions → "SageMaker Pipeline build SMUS project"
2. Click "Run workflow"
3. Esperar 10-15 minutos a que complete

### Opción B - Automático:
1. Hacer cualquier cambio en el repo (agregar línea vacía)
2. Commit y push
3. El workflow se ejecutará automáticamente

## 6. Verificar Modelo en Model Registry

Después de que el pipeline complete:

1. Ir a SMUS → Build → AI OPS → Model Registry
2. Buscar: `aiops-{project-id}-models`
3. Verificar que aparezca el modelo con estado "PendingManualApproval"

## 7. Aprobar Modelo para Despliegue

1. Seleccionar el modelo
2. Click "Update model approval status"
3. Cambiar a "Approved"
4. El despliegue se activará automáticamente

## Comandos Útiles

### Ver logs de Lambda:
```bash
# Check project setup
aws logs tail /aws/lambda/ai-ops-check-project-status --follow --region us-east-1

# Sync repositories
aws logs tail /aws/lambda/ai-ops-sync-repositories --follow --region us-east-1

# Model approval
aws logs tail /aws/lambda/MlOpsSmusStack-model-approval-trigger --follow --region us-east-1
```

### Ver ejecución de Step Functions:
```bash
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:767397690934:stateMachine:ml-ops-project-setup \
  --region us-east-1
```

### Verificar EventBridge rules:
```bash
aws events list-rules --region us-east-1 | grep -i "ml-ops\|model-approval"
```

## Troubleshooting

### Si los repositorios no se crean:
```bash
# Ver logs del Step Functions
aws stepfunctions describe-execution \
  --execution-arn <execution-arn> \
  --region us-east-1
```

### Si el pipeline falla:
- Verificar que GLUE_DATABASE y GLUE_TABLE estén configurados
- Verificar que TRIGGER_PIPELINE_EXECUTION=true
- Ver logs en Actions del repositorio

### Si el deploy no se activa:
- Verificar que el modelo esté "Approved"
- Ver logs del Lambda de model approval
- Verificar EventBridge rule está ENABLED

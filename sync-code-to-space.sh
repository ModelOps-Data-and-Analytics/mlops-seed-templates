#!/bin/bash

# Script para sincronizar código al Space via S3 (workaround para falta de conectividad GitHub)

REPO_NAME="mlops-test-build"
S3_BUCKET="s3://amazon-sagemaker-767397690934-us-east-1-ea48f8126d08/dzd_4jzjk46dkwid0n/d9o7lduveyqhev/code-sync/"
LOCAL_REPO_PATH="/Users/julian.mazo/Documents/modelops/${REPO_NAME}"

echo "=== Sincronizando código del repositorio al Space vía S3 ==="

# Paso 1: Clonar o actualizar repositorio localmente
if [ ! -d "$LOCAL_REPO_PATH" ]; then
    echo "Clonando repositorio..."
    git clone https://github.com/ModelOps-Data-and-Analytics/${REPO_NAME}.git "$LOCAL_REPO_PATH"
else
    echo "Actualizando repositorio existente..."
    cd "$LOCAL_REPO_PATH" && git pull
fi

# Paso 2: Comprimir el código
echo "Comprimiendo código..."
cd "$(dirname "$LOCAL_REPO_PATH")"
tar -czf ${REPO_NAME}.tar.gz ${REPO_NAME}/

# Paso 3: Subir a S3
echo "Subiendo a S3..."
aws s3 cp ${REPO_NAME}.tar.gz ${S3_BUCKET}

echo "✓ Código subido a S3"
echo ""
echo "Ahora desde el terminal del Space, ejecuta:"
echo "  aws s3 cp ${S3_BUCKET}${REPO_NAME}.tar.gz /home/sagemaker-user/"
echo "  cd /home/sagemaker-user"
echo "  tar -xzf ${REPO_NAME}.tar.gz"
echo "  cd ${REPO_NAME}"

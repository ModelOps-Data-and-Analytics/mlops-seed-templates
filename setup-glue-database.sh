#!/bin/bash

# Script para configurar Glue Database y Tabla para el proyecto MLOps
# Ejecutar después de crear el proyecto en SMUS

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Configuración de Glue Database para MLOps ===${NC}\n"

# Variables - ACTUALIZAR CON TUS VALORES DESPUÉS DE CREAR EL PROYECTO
PROJECT_NAME="mlops-test"  # El nombre del proyecto que creaste en SMUS
REGION="us-east-1"
ACCOUNT_ID="767397690934"

# El nombre de la base de datos Glue será creado automáticamente por SMUS
# Buscar la base de datos que contiene el project name
echo -e "${YELLOW}Buscando base de datos Glue del proyecto...${NC}"
GLUE_DB=$(aws glue get-databases --region $REGION --query "DatabaseList[?contains(Name, 'glue_db')].Name" --output text | head -1)

if [ -z "$GLUE_DB" ]; then
    echo -e "${RED}No se encontró base de datos Glue. Asegúrate de que el proyecto SMUS se haya creado completamente.${NC}"
    echo -e "${YELLOW}El proyecto puede tardar 5-10 minutos en crearse.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Base de datos encontrada: $GLUE_DB${NC}\n"

# Bucket S3 del proyecto
S3_BUCKET="s3://amazon-sagemaker-$ACCOUNT_ID-$REGION-ea48f8126d08"
S3_DATA_PATH="$S3_BUCKET/dzd_4jzjk46dkwid0n/abalone-data"

echo -e "${YELLOW}Subiendo dataset abalone a S3...${NC}"
# Copiar dataset a S3
aws s3 cp aiops-seed-code/regression/model_build/ml_pipelines/data/abalone-dataset.csv \
    $S3_DATA_PATH/abalone-dataset.csv \
    --region $REGION

echo -e "${GREEN}✓ Dataset subido a: $S3_DATA_PATH${NC}\n"

# Crear tabla Glue
echo -e "${YELLOW}Creando tabla 'abalone' en Glue...${NC}"

aws glue create-table \
    --database-name $GLUE_DB \
    --region $REGION \
    --table-input '{
        "Name": "abalone",
        "StorageDescriptor": {
            "Columns": [
                {"Name": "sex", "Type": "string"},
                {"Name": "length", "Type": "double"},
                {"Name": "diameter", "Type": "double"},
                {"Name": "height", "Type": "double"},
                {"Name": "whole_weight", "Type": "double"},
                {"Name": "shucked_weight", "Type": "double"},
                {"Name": "viscera_weight", "Type": "double"},
                {"Name": "shell_weight", "Type": "double"},
                {"Name": "rings", "Type": "int"}
            ],
            "Location": "'$S3_DATA_PATH'/",
            "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe",
                "Parameters": {
                    "field.delim": ",",
                    "skip.header.line.count": "1"
                }
            }
        },
        "TableType": "EXTERNAL_TABLE"
    }' 2>/dev/null || echo -e "${YELLOW}Tabla ya existe, continuando...${NC}"

echo -e "${GREEN}✓ Tabla 'abalone' creada${NC}\n"

# Verificar tabla
echo -e "${YELLOW}Verificando tabla...${NC}"
aws glue get-table \
    --database-name $GLUE_DB \
    --name abalone \
    --region $REGION \
    --query 'Table.{Name:Name,Columns:StorageDescriptor.Columns[*].Name,Location:StorageDescriptor.Location}' \
    --output table

echo -e "\n${GREEN}=== Configuración completada ===${NC}\n"
echo -e "${YELLOW}Información para actualizar GitHub Secrets:${NC}"
echo -e "GLUE_DATABASE: ${GREEN}$GLUE_DB${NC}"
echo -e "GLUE_TABLE: ${GREEN}abalone${NC}"
echo -e "S3_DATA_PATH: ${GREEN}$S3_DATA_PATH${NC}\n"

echo -e "${YELLOW}Próximos pasos:${NC}"
echo "1. Ir a los repositorios creados en GitHub"
echo "2. Actualizar los secrets con los valores mostrados arriba"
echo "3. Habilitar la variable TRIGGER_PIPELINE_EXECUTION=true"

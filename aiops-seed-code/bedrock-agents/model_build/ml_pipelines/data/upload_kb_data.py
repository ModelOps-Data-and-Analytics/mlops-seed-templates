#!/usr/bin/env python3
"""
Script para subir datos sintéticos de Knowledge Base a S3.

Uso:
    python upload_kb_data.py --bucket mi-bucket --prefix knowledge-base-data/
    
O con perfil AWS específico:
    AWS_PROFILE=mi-perfil python upload_kb_data.py --bucket mi-bucket
"""

import argparse
import json
import logging
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directorio donde están los datos
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "knowledge_base"


def get_content_type(filename: str) -> str:
    """Determinar el Content-Type basado en la extensión del archivo."""
    extension = filename.lower().split('.')[-1]
    content_types = {
        'json': 'application/json',
        'csv': 'text/csv',
        'txt': 'text/plain',
        'md': 'text/markdown',
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'html': 'text/html',
    }
    return content_types.get(extension, 'application/octet-stream')


def upload_file(s3_client, file_path: Path, bucket: str, prefix: str) -> bool:
    """Subir un archivo a S3."""
    key = f"{prefix}{file_path.name}"
    content_type = get_content_type(file_path.name)
    
    try:
        s3_client.upload_file(
            str(file_path),
            bucket,
            key,
            ExtraArgs={
                'ContentType': content_type,
                'Metadata': {
                    'source': 'synthetic-data',
                    'purpose': 'knowledge-base-ingestion'
                }
            }
        )
        logger.info(f"✅ Subido: s3://{bucket}/{key}")
        return True
    except ClientError as e:
        logger.error(f"❌ Error subiendo {file_path.name}: {e}")
        return False


def ensure_bucket_exists(s3_client, bucket: str, region: str) -> bool:
    """Verificar que el bucket existe, o crearlo si no."""
    try:
        s3_client.head_bucket(Bucket=bucket)
        logger.info(f"Bucket existe: {bucket}")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            logger.info(f"Creando bucket: {bucket}")
            try:
                if region == 'us-east-1':
                    s3_client.create_bucket(Bucket=bucket)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket,
                        CreateBucketConfiguration={'LocationConstraint': region}
                    )
                logger.info(f"✅ Bucket creado: {bucket}")
                return True
            except ClientError as create_error:
                logger.error(f"❌ Error creando bucket: {create_error}")
                return False
        else:
            logger.error(f"❌ Error accediendo al bucket: {e}")
            return False


def list_data_files() -> list:
    """Listar todos los archivos de datos en el directorio."""
    if not DATA_DIR.exists():
        logger.error(f"Directorio de datos no existe: {DATA_DIR}")
        return []
    
    files = []
    for ext in ['*.json', '*.csv', '*.txt', '*.md']:
        files.extend(DATA_DIR.glob(ext))
    
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description="Subir datos de Knowledge Base a S3")
    parser.add_argument("--bucket", type=str, required=True,
                        help="Nombre del bucket S3")
    parser.add_argument("--prefix", type=str, default="knowledge-base-data/",
                        help="Prefijo (carpeta) en S3")
    parser.add_argument("--region", type=str, default="us-east-1",
                        help="Región AWS")
    parser.add_argument("--create-bucket", action="store_true",
                        help="Crear bucket si no existe")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostrar archivos sin subir")
    
    args = parser.parse_args()
    
    # Asegurar que el prefix termine con /
    prefix = args.prefix
    if not prefix.endswith('/'):
        prefix += '/'
    
    logger.info("=" * 60)
    logger.info("SUBIDA DE DATOS SINTÉTICOS A S3")
    logger.info("=" * 60)
    logger.info(f"  Bucket: {args.bucket}")
    logger.info(f"  Prefix: {prefix}")
    logger.info(f"  Region: {args.region}")
    logger.info("=" * 60)
    
    # Listar archivos
    files = list_data_files()
    if not files:
        logger.error("No se encontraron archivos de datos")
        return 1
    
    logger.info(f"\nArchivos encontrados ({len(files)}):")
    total_size = 0
    for f in files:
        size = f.stat().st_size
        total_size += size
        logger.info(f"  - {f.name} ({size:,} bytes)")
    
    logger.info(f"\nTamaño total: {total_size:,} bytes ({total_size/1024:.1f} KB)")
    
    if args.dry_run:
        logger.info("\n[DRY RUN] No se subieron archivos")
        return 0
    
    # Crear cliente S3
    s3_client = boto3.client('s3', region_name=args.region)
    
    # Verificar/crear bucket
    if args.create_bucket:
        if not ensure_bucket_exists(s3_client, args.bucket, args.region):
            return 1
    
    # Subir archivos
    logger.info("\nSubiendo archivos...")
    success_count = 0
    for file_path in files:
        if upload_file(s3_client, file_path, args.bucket, prefix):
            success_count += 1
    
    # Resumen
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN")
    logger.info("=" * 60)
    logger.info(f"  Archivos procesados: {len(files)}")
    logger.info(f"  Subidos exitosamente: {success_count}")
    logger.info(f"  Errores: {len(files) - success_count}")
    logger.info(f"\n  URI S3: s3://{args.bucket}/{prefix}")
    logger.info("=" * 60)
    
    if success_count < len(files):
        logger.warning("⚠️ Algunos archivos no se subieron correctamente")
        return 1
    
    logger.info("✅ Todos los archivos subidos correctamente")
    logger.info(f"\nPara ingestar estos datos en el pipeline, usa:")
    logger.info(f"  KnowledgeBaseS3Uri=s3://{args.bucket}/{prefix}")
    
    return 0


if __name__ == "__main__":
    exit(main())

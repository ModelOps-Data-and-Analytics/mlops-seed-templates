"""Create or update Knowledge Base for Bedrock Agent using S3 Vectors."""
import argparse
import json
import logging
import os
import subprocess
import sys
import time

# Install boto3 with Bedrock support (container may have old version)
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "boto3>=1.34.0", "botocore>=1.34.0"])

import boto3
import yaml
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_existing_knowledge_base(bedrock_agent_client, kb_name: str) -> dict | None:
    """Check if knowledge base already exists.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        kb_name: Knowledge base name
        
    Returns:
        Knowledge base details if exists, None otherwise
    """
    try:
        response = bedrock_agent_client.list_knowledge_bases()
        for kb in response.get('knowledgeBaseSummaries', []):
            if kb['name'] == kb_name:
                logger.info(f"Found existing knowledge base: {kb['knowledgeBaseId']}")
                return kb
    except ClientError as e:
        logger.error(f"Error listing knowledge bases: {e}")
    
    return None


def ensure_s3_vectors_bucket(s3_client, bucket_name: str, region: str) -> str:
    """Ensure S3 bucket exists for S3 Vectors storage.
    
    Args:
        s3_client: S3 client
        bucket_name: Name for the bucket
        region: AWS region
        
    Returns:
        Bucket ARN
    """
    logger.info(f"Ensuring S3 Vectors bucket exists: {bucket_name}")
    
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        logger.info(f"Using existing bucket: {bucket_name}")
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.info(f"Creating S3 bucket: {bucket_name}")
            if region == 'us-east-1':
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            
            # Enable versioning for S3 Vectors
            s3_client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            logger.info(f"Created bucket with versioning: {bucket_name}")
        else:
            raise
    
    return f"arn:aws:s3:::{bucket_name}"


def create_knowledge_base(
    bedrock_agent_client,
    kb_name: str,
    description: str,
    role_arn: str,
    embedding_model_arn: str,
    bucket_arn: str,
    region: str
) -> dict:
    """Create a new knowledge base with S3 Vectors storage.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        kb_name: Knowledge base name
        description: Description
        role_arn: IAM role ARN
        embedding_model_arn: Embedding model ARN
        bucket_arn: S3 Vectors bucket ARN
        region: AWS region
        
    Returns:
        Knowledge base details
    """
    logger.info(f"Creating knowledge base with S3 Vectors: {kb_name}")
    
    response = bedrock_agent_client.create_knowledge_base(
        name=kb_name,
        description=description,
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            'type': 'VECTOR',
            'vectorKnowledgeBaseConfiguration': {
                'embeddingModelArn': embedding_model_arn
            }
        },
        storageConfiguration={
            'type': 'S3',
            's3Configuration': {
                'bucketArn': bucket_arn
            }
        }
    )
    
    kb = response['knowledgeBase']
    logger.info(f"Created knowledge base: {kb['knowledgeBaseId']}")
    
    # Wait for KB to be ready
    logger.info("Waiting for knowledge base to be ready...")
    for _ in range(30):
        kb_response = bedrock_agent_client.get_knowledge_base(
            knowledgeBaseId=kb['knowledgeBaseId']
        )
        status = kb_response['knowledgeBase']['status']
        if status == 'ACTIVE':
            logger.info("Knowledge base is active")
            break
        elif status == 'FAILED':
            raise Exception(f"Knowledge base creation failed: {kb_response}")
        time.sleep(10)
    else:
        logger.warning("Knowledge base still creating, continuing...")
    
    return kb


def create_data_source(
    bedrock_agent_client,
    kb_id: str,
    s3_uri: str,
    data_source_name: str,
    max_tokens: int = 1024,
    overlap_percentage: int = 20
) -> dict:
    """Create S3 data source for knowledge base.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        kb_id: Knowledge base ID
        s3_uri: S3 URI for data (ej: s3://mi-bucket/documentos/)
        data_source_name: Data source name
        max_tokens: Tamaño máximo de chunks (default: 1024)
        overlap_percentage: Porcentaje de overlap entre chunks (default: 20)
        
    Returns:
        Data source details
    """
    logger.info(f"Creating data source for KB {kb_id}: {s3_uri}")
    
    # Parse S3 URI
    s3_parts = s3_uri.replace("s3://", "").split("/", 1)
    bucket = s3_parts[0]
    prefix = s3_parts[1] if len(s3_parts) > 1 else ""
    
    response = bedrock_agent_client.create_data_source(
        knowledgeBaseId=kb_id,
        name=data_source_name,
        dataSourceConfiguration={
            'type': 'S3',
            's3Configuration': {
                'bucketArn': f"arn:aws:s3:::{bucket}",
                'inclusionPrefixes': [prefix] if prefix else []
            }
        },
        vectorIngestionConfiguration={
            'chunkingConfiguration': {
                'chunkingStrategy': 'FIXED_SIZE',
                'fixedSizeChunkingConfiguration': {
                    'maxTokens': max_tokens,
                    'overlapPercentage': overlap_percentage
                }
            }
        }
    )
    
    ds = response['dataSource']
    logger.info(f"Created data source: {ds['dataSourceId']}")
    
    return ds


def start_ingestion_job(
    bedrock_agent_client,
    kb_id: str,
    data_source_id: str,
    description: str = "Ingesta de documentación"
) -> dict:
    """Iniciar job de ingesta para sincronizar documentos de S3 a Knowledge Base.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        kb_id: Knowledge Base ID
        data_source_id: Data Source ID
        description: Descripción del job
        
    Returns:
        Ingestion job details
    """
    logger.info(f"Iniciando ingesta para KB {kb_id}, DataSource {data_source_id}")
    
    response = bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=data_source_id,
        description=description
    )
    
    job = response['ingestionJob']
    logger.info(f"Ingestion job iniciado: {job['ingestionJobId']}")
    
    return job


def wait_for_ingestion_job(
    bedrock_agent_client,
    kb_id: str,
    data_source_id: str,
    job_id: str,
    timeout_minutes: int = 30
) -> dict:
    """Esperar a que termine el job de ingesta.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        kb_id: Knowledge Base ID
        data_source_id: Data Source ID
        job_id: Ingestion Job ID
        timeout_minutes: Tiempo máximo de espera en minutos
        
    Returns:
        Ingestion job final status
    """
    logger.info(f"Esperando ingesta {job_id}...")
    
    max_attempts = timeout_minutes * 6  # Check every 10 seconds
    
    for attempt in range(max_attempts):
        response = bedrock_agent_client.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id,
            ingestionJobId=job_id
        )
        
        job = response['ingestionJob']
        status = job['status']
        
        if status == 'COMPLETE':
            stats = job.get('statistics', {})
            logger.info("=" * 50)
            logger.info("✅ INGESTA COMPLETADA")
            logger.info(f"   Documentos escaneados: {stats.get('numberOfDocumentsScanned', 0)}")
            logger.info(f"   Documentos indexados: {stats.get('numberOfDocumentsIndexed', 0)}")
            logger.info(f"   Documentos fallidos: {stats.get('numberOfDocumentsFailed', 0)}")
            logger.info(f"   Nuevos chunks: {stats.get('numberOfNewChunksIndexed', 0)}")
            logger.info(f"   Chunks modificados: {stats.get('numberOfModifiedChunksIndexed', 0)}")
            logger.info(f"   Chunks eliminados: {stats.get('numberOfChunksDeleted', 0)}")
            logger.info("=" * 50)
            return job
            
        elif status == 'FAILED':
            failure_reasons = job.get('failureReasons', [])
            logger.error(f"❌ Ingesta fallida: {failure_reasons}")
            raise Exception(f"Ingestion job failed: {failure_reasons}")
            
        elif status in ['STARTING', 'IN_PROGRESS']:
            if attempt % 6 == 0:  # Log every minute
                logger.info(f"   Ingesta en progreso... ({attempt // 6 + 1} min)")
            time.sleep(10)
            
        else:
            logger.warning(f"Estado desconocido: {status}")
            time.sleep(10)
    
    raise TimeoutError(f"Ingestion job timeout after {timeout_minutes} minutes")


def sync_documents_to_kb(
    bedrock_agent_client,
    kb_id: str,
    data_source_id: str,
    timeout_minutes: int = 30
) -> dict:
    """Sincronizar documentos de S3 a la Knowledge Base.
    
    Esta es la función principal que:
    1. Inicia el job de ingesta
    2. Espera a que termine
    3. Retorna estadísticas
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        kb_id: Knowledge Base ID
        data_source_id: Data Source ID
        timeout_minutes: Timeout en minutos
        
    Returns:
        Resultado de la ingesta con estadísticas
    """
    logger.info("=" * 60)
    logger.info("SINCRONIZANDO DOCUMENTOS A KNOWLEDGE BASE")
    logger.info("=" * 60)
    
    # 1. Iniciar job de ingesta
    job = start_ingestion_job(
        bedrock_agent_client,
        kb_id,
        data_source_id,
        description=f"Ingesta automática desde SageMaker Pipeline"
    )
    
    # 2. Esperar a que termine
    result = wait_for_ingestion_job(
        bedrock_agent_client,
        kb_id,
        data_source_id,
        job['ingestionJobId'],
        timeout_minutes=timeout_minutes
    )
    
    return result


def associate_kb_to_agent(bedrock_agent_client, agent_id: str, kb_id: str) -> None:
    """Associate knowledge base to agent.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_id: Agent ID
        kb_id: Knowledge base ID
    """
    logger.info(f"Associating KB {kb_id} to agent {agent_id}")
    
    bedrock_agent_client.associate_agent_knowledge_base(
        agentId=agent_id,
        agentVersion='DRAFT',
        knowledgeBaseId=kb_id,
        description="Product and policy knowledge base"
    )
    
    logger.info("Knowledge base associated successfully")


def main():
    parser = argparse.ArgumentParser(description="Create Knowledge Base for Bedrock Agent")
    parser.add_argument("--agent-name", type=str, required=True)
    parser.add_argument("--s3-uri", type=str, required=True, 
                        help="S3 URI donde están los documentos (ej: s3://mi-bucket/docs/)")
    parser.add_argument("--region", type=str, required=True)
    parser.add_argument("--enable", type=str, default="true")
    parser.add_argument("--max-tokens", type=int, default=1024,
                        help="Tamaño máximo de chunks en tokens")
    parser.add_argument("--overlap-percentage", type=int, default=20,
                        help="Porcentaje de overlap entre chunks")
    parser.add_argument("--ingestion-timeout", type=int, default=30,
                        help="Timeout de ingesta en minutos")
    parser.add_argument("--skip-ingestion", action="store_true",
                        help="Omitir la ingesta de documentos")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("CREANDO KNOWLEDGE BASE CON INGESTA DE DOCUMENTOS")
    logger.info("=" * 60)
    logger.info(f"  Agent Name: {args.agent_name}")
    logger.info(f"  S3 URI: {args.s3_uri}")
    logger.info(f"  Max Tokens: {args.max_tokens}")
    logger.info(f"  Overlap: {args.overlap_percentage}%")
    logger.info("=" * 60)
    
    output = {
        "enabled": args.enable.lower() == "true",
        "knowledge_base_id": None,
        "data_source_id": None,
        "status": "skipped",
        "ingestion": {
            "status": "skipped",
            "documents_indexed": 0,
            "chunks_created": 0
        }
    }
    
    if args.enable.lower() != "true":
        logger.info("Knowledge base creation is disabled")
    else:
        try:
            bedrock_agent = boto3.client('bedrock-agent', region_name=args.region)
            s3 = boto3.client('s3', region_name=args.region)
            sts = boto3.client('sts')
            
            account_id = sts.get_caller_identity()['Account']
            
            kb_name = f"{args.agent_name}-kb"
            vectors_bucket = f"{args.agent_name}-vectors-{account_id}-{args.region}"
            
            # 1. Check if KB exists
            existing_kb = get_existing_knowledge_base(bedrock_agent, kb_name)
            
            if existing_kb:
                kb_id = existing_kb['knowledgeBaseId']
                output["knowledge_base_id"] = kb_id
                output["status"] = "existing"
                logger.info(f"Usando KB existente: {kb_id}")
                
                # Get existing data source
                ds_response = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
                data_sources = ds_response.get('dataSourceSummaries', [])
                
                if data_sources:
                    data_source_id = data_sources[0]['dataSourceId']
                    output["data_source_id"] = data_source_id
                    logger.info(f"Usando Data Source existente: {data_source_id}")
                else:
                    # Create new data source
                    ds = create_data_source(
                        bedrock_agent, kb_id, args.s3_uri,
                        f"{args.agent_name}-datasource",
                        max_tokens=args.max_tokens,
                        overlap_percentage=args.overlap_percentage
                    )
                    data_source_id = ds['dataSourceId']
                    output["data_source_id"] = data_source_id
            else:
                # 2. Ensure S3 Vectors bucket exists
                bucket_arn = ensure_s3_vectors_bucket(s3, vectors_bucket, args.region)
                output["vectors_bucket"] = vectors_bucket
                
                # 3. Get/Create IAM role for KB
                kb_role_arn = os.environ.get('KB_ROLE_ARN')
                if not kb_role_arn:
                    kb_role_arn = f"arn:aws:iam::{account_id}:role/{args.agent_name}-kb-role"
                    logger.info(f"Usando rol: {kb_role_arn}")
                
                # 4. Get embedding model ARN
                embedding_model_arn = f"arn:aws:bedrock:{args.region}::foundation-model/amazon.titan-embed-text-v2:0"
                
                # 5. Create Knowledge Base
                kb = create_knowledge_base(
                    bedrock_agent,
                    kb_name,
                    f"Knowledge Base para {args.agent_name}",
                    kb_role_arn,
                    embedding_model_arn,
                    bucket_arn,
                    args.region
                )
                kb_id = kb['knowledgeBaseId']
                output["knowledge_base_id"] = kb_id
                output["status"] = "created"
                
                # 6. Create Data Source pointing to S3 docs
                ds = create_data_source(
                    bedrock_agent, kb_id, args.s3_uri,
                    f"{args.agent_name}-datasource",
                    max_tokens=args.max_tokens,
                    overlap_percentage=args.overlap_percentage
                )
                data_source_id = ds['dataSourceId']
                output["data_source_id"] = data_source_id
            
            # 7. INGESTA DE DOCUMENTOS
            if not args.skip_ingestion:
                logger.info("")
                logger.info("🔄 Iniciando ingesta de documentos...")
                
                ingestion_result = sync_documents_to_kb(
                    bedrock_agent,
                    output["knowledge_base_id"],
                    output["data_source_id"],
                    timeout_minutes=args.ingestion_timeout
                )
                
                stats = ingestion_result.get('statistics', {})
                output["ingestion"] = {
                    "status": "completed",
                    "job_id": ingestion_result.get('ingestionJobId'),
                    "documents_scanned": stats.get('numberOfDocumentsScanned', 0),
                    "documents_indexed": stats.get('numberOfDocumentsIndexed', 0),
                    "documents_failed": stats.get('numberOfDocumentsFailed', 0),
                    "chunks_created": stats.get('numberOfNewChunksIndexed', 0),
                    "chunks_modified": stats.get('numberOfModifiedChunksIndexed', 0),
                    "chunks_deleted": stats.get('numberOfChunksDeleted', 0)
                }
                
                logger.info(f"✅ Ingesta completada: {output['ingestion']['documents_indexed']} documentos indexados")
            else:
                logger.info("⏭️ Ingesta omitida (--skip-ingestion)")
                output["ingestion"]["status"] = "skipped"
            
            # 8. Associate KB to Agent (if agent exists)
            try:
                agent = None
                agents_response = bedrock_agent.list_agents()
                for a in agents_response.get('agentSummaries', []):
                    if a['agentName'] == args.agent_name:
                        agent = a
                        break
                
                if agent:
                    associate_kb_to_agent(bedrock_agent, agent['agentId'], output["knowledge_base_id"])
                    output["agent_associated"] = True
                else:
                    logger.info("Agente no encontrado, KB se asociará después")
                    output["agent_associated"] = False
            except Exception as e:
                logger.warning(f"No se pudo asociar KB al agente: {e}")
                output["agent_associated"] = False
                
        except Exception as e:
            logger.error(f"Error en Knowledge Base: {e}")
            output["status"] = "error"
            output["error"] = str(e)
            raise
    
    # Write output
    output_dir = "/opt/ml/processing/output"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "kb_output.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("RESUMEN DE KNOWLEDGE BASE")
    logger.info("=" * 60)
    logger.info(f"  KB ID: {output.get('knowledge_base_id')}")
    logger.info(f"  Data Source ID: {output.get('data_source_id')}")
    logger.info(f"  Status: {output.get('status')}")
    logger.info(f"  Ingesta: {output['ingestion'].get('status')}")
    if output['ingestion'].get('documents_indexed'):
        logger.info(f"  Docs indexados: {output['ingestion']['documents_indexed']}")
        logger.info(f"  Chunks creados: {output['ingestion']['chunks_created']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

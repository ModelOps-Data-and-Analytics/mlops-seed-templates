"""Register Bedrock Agent in SageMaker Model Registry."""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime

import tarfile
import tempfile

def create_and_upload_dummy_tar(agent_id, metadata_dict, s3_bucket, s3_prefix, region):
    """Crea un tar.gz dummy con un txt de metadata y lo sube a S3."""
    import boto3
    import json
    import os
    with tempfile.TemporaryDirectory() as tmpdir:
        txt_path = os.path.join(tmpdir, "agent_metadata.txt")
        with open(txt_path, "w") as f:
            json.dump(metadata_dict, f, indent=2)
        tar_path = os.path.join(tmpdir, "model.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(txt_path, arcname="agent_metadata.txt")
        s3 = boto3.client("s3", region_name=region)
        s3_key = f"{s3_prefix}/{agent_id}/model.tar.gz"
        s3.upload_file(tar_path, s3_bucket, s3_key)
        return f"s3://{s3_bucket}/{s3_key}"

# Install boto3 with Bedrock support (container may have old version)
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "boto3>=1.34.0", "botocore>=1.34.0"])

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_agent_by_name(bedrock_agent_client, agent_name: str) -> dict | None:
    """Get agent by name."""
    try:
        response = bedrock_agent_client.list_agents()
        for agent in response.get('agentSummaries', []):
            if agent['agentName'] == agent_name:
                # Get full agent details
                agent_details = bedrock_agent_client.get_agent(agentId=agent['agentId'])
                return agent_details['agent']
    except ClientError as e:
        logger.error(f"Error getting agent: {e}")
    return None


def get_agent_alias(bedrock_agent_client, agent_id: str, alias_name: str = "staging") -> dict | None:
    """Get agent alias by name."""
    try:
        response = bedrock_agent_client.list_agent_aliases(agentId=agent_id)
        for alias in response.get('agentAliasSummaries', []):
            if alias['agentAliasName'] == alias_name:
                return alias
    except ClientError as e:
        logger.error(f"Error getting alias: {e}")
    return None


def get_agent_knowledge_bases(bedrock_agent_client, agent_id: str, agent_version: str = "DRAFT") -> list:
    """Get knowledge bases associated with an agent.

    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_id: Agent ID
        agent_version: Agent version

    Returns:
        List of knowledge base associations
    """
    try:
        response = bedrock_agent_client.list_agent_knowledge_bases(
            agentId=agent_id,
            agentVersion=agent_version
        )
        return response.get('agentKnowledgeBaseSummaries', [])
    except ClientError as e:
        logger.error(f"Error getting agent knowledge bases: {e}")
        return []


def get_knowledge_base_details(bedrock_agent_client, kb_id: str) -> dict | None:
    """Get knowledge base details including configuration.

    Args:
        bedrock_agent_client: Bedrock Agent client
        kb_id: Knowledge Base ID

    Returns:
        Knowledge base details
    """
    try:
        response = bedrock_agent_client.get_knowledge_base(knowledgeBaseId=kb_id)
        kb = response.get('knowledgeBase', {})

        # Get data sources
        data_sources = []
        try:
            ds_response = bedrock_agent_client.list_data_sources(knowledgeBaseId=kb_id)
            for ds in ds_response.get('dataSourceSummaries', []):
                ds_detail = bedrock_agent_client.get_data_source(
                    knowledgeBaseId=kb_id,
                    dataSourceId=ds['dataSourceId']
                )
                data_sources.append(ds_detail.get('dataSource', {}))
        except ClientError as e:
            logger.warning(f"Could not get data sources: {e}")

        return {
            "knowledge_base_id": kb_id,
            "knowledge_base_arn": kb.get('knowledgeBaseArn'),
            "name": kb.get('name'),
            "description": kb.get('description', ''),
            "role_arn": kb.get('roleArn'),
            "storage_configuration": kb.get('storageConfiguration', {}),
            "knowledge_base_configuration": kb.get('knowledgeBaseConfiguration', {}),
            "data_sources": data_sources,
            "status": kb.get('status')
        }
    except ClientError as e:
        logger.error(f"Error getting knowledge base details: {e}")
        return None


def ensure_model_package_group(sm_client, group_name: str) -> str:
    """Ensure model package group exists.

    Args:
        sm_client: SageMaker client
        group_name: Model package group name

    Returns:
        Group ARN
    """
    try:
        response = sm_client.describe_model_package_group(
            ModelPackageGroupName=group_name
        )
        logger.info(f"Using existing model package group: {group_name}")
        return response['ModelPackageGroupArn']
    except sm_client.exceptions.ClientError:
        pass

    # Create new group
    logger.info(f"Creating model package group: {group_name}")
    response = sm_client.create_model_package_group(
        ModelPackageGroupName=group_name,
        ModelPackageGroupDescription="Bedrock Agents model package group"
    )

    return response['ModelPackageGroupArn']


def register_agent_model(
    sm_client,
    group_name: str,
    agent_id: str,
    agent_alias_id: str,
    agent_arn: str,
    foundation_model: str,
    approval_status: str,
    evaluation_metrics: dict = None,
    knowledge_base_info: dict = None
) -> str:
    """Register agent as model in SageMaker Model Registry.

    Args:
        sm_client: SageMaker client
        group_name: Model package group name
        agent_id: Bedrock Agent ID
        agent_alias_id: Agent alias ID
        agent_arn: Agent ARN
        foundation_model: Foundation model ID
        approval_status: Approval status
        evaluation_metrics: Evaluation metrics
        knowledge_base_info: Knowledge base configuration for replication

    Returns:
        Model package ARN
    """
    logger.info(f"Registering agent model in group: {group_name}")

    # Create model package
    # Note: For Bedrock Agents, we use a custom approach since there's no
    # traditional model artifact. We store agent metadata as model properties.

    model_metrics = None
    if evaluation_metrics:
        model_metrics = {
            "ModelQuality": {
                "Statistics": {
                    "ContentType": "application/json",
                    "S3Uri": "s3://placeholder/metrics.json"  # In production, upload actual metrics
                }
            }
        }

    # Custom metadata for Bedrock Agent
    customer_metadata = {
        "agent_id": agent_id,
        "agent_alias_id": agent_alias_id,
        "agent_arn": agent_arn,
        "foundation_model": foundation_model,
        "agent_type": "bedrock_agent",
        "registration_timestamp": datetime.utcnow().isoformat()
    }

    if evaluation_metrics:
        customer_metadata["success_rate"] = str(evaluation_metrics.get("success_rate", 0))
        customer_metadata["total_tests"] = str(evaluation_metrics.get("total_tests", 0))

    # Add Knowledge Base information for replication in other environments
    if knowledge_base_info:
        customer_metadata["kb_id"] = knowledge_base_info.get("knowledge_base_id", "")
        customer_metadata["kb_arn"] = knowledge_base_info.get("knowledge_base_arn", "")
        customer_metadata["kb_name"] = knowledge_base_info.get("name", "")
        customer_metadata["kb_description"] = knowledge_base_info.get("description", "")[:256]  # Max 256 chars
        customer_metadata["kb_role_arn"] = knowledge_base_info.get("role_arn", "")

        # Store data source S3 URIs for replication
        data_sources = knowledge_base_info.get("data_sources", [])
        if data_sources:
            s3_uris = []
            for ds in data_sources:
                s3_config = ds.get("dataSourceConfiguration", {}).get("s3Configuration", {})
                if s3_config.get("bucketArn"):
                    bucket_name = s3_config["bucketArn"].split(":")[-1]
                    prefix = s3_config.get("inclusionPrefixes", [""])[0] if s3_config.get("inclusionPrefixes") else ""
                    s3_uris.append(f"s3://{bucket_name}/{prefix}")
            customer_metadata["kb_data_source_s3_uris"] = ",".join(s3_uris)
            customer_metadata["kb_data_source_count"] = str(len(data_sources))

        # Store storage configuration type
        storage_config = knowledge_base_info.get("storage_configuration", {})
        customer_metadata["kb_storage_type"] = storage_config.get("type", "S3")

        # Store embedding model from KB configuration
        kb_config = knowledge_base_info.get("knowledge_base_configuration", {})
        vector_config = kb_config.get("vectorKnowledgeBaseConfiguration", {})
        customer_metadata["kb_embedding_model"] = vector_config.get("embeddingModelArn", "")

    # Usar los argumentos de S3 para construir el ModelDataUrl
    import inspect
    frame = inspect.currentframe().f_back
    args = frame.f_locals.get('args', None)
    if args:
        s3_bucket = args.s3_bucket
        s3_prefix = args.s3_prefix
    else:
        s3_bucket = 'placeholder-bucket'
        s3_prefix = 'bedrock-agents'
    model_data_url = f"s3://{s3_bucket}/{s3_prefix}/{agent_id}/model.tar.gz"
    response = sm_client.create_model_package(
        ModelPackageGroupName=group_name,
        ModelPackageDescription=f"Bedrock Agent: {agent_id}",
        ModelApprovalStatus=approval_status,
        CustomerMetadataProperties=customer_metadata,
        InferenceSpecification={
            "Containers": [
                {
                    "Image": "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.0.0-cpu-py310",
                    "ModelDataUrl": model_data_url,
                    "Environment": {
                        "BEDROCK_AGENT_ID": agent_id,
                        "BEDROCK_AGENT_ALIAS_ID": agent_alias_id
                    }
                }
            ],
            "SupportedContentTypes": ["application/json"],
            "SupportedResponseMIMETypes": ["application/json"]
        }
    )
    model_package_arn = response['ModelPackageArn']
    logger.info(f"Registered model package: {model_package_arn}")
    return model_package_arn


def main():
    parser = argparse.ArgumentParser(description="Register Bedrock Agent in Model Registry")
    parser.add_argument("--agent-name", type=str, required=True)
    parser.add_argument("--model-package-group-name", type=str, required=True)
    parser.add_argument("--approval-status", type=str, default="PendingManualApproval")
    parser.add_argument("--region", type=str, required=True)
    parser.add_argument("--s3-bucket", type=str, required=True)
    parser.add_argument("--s3-prefix", type=str, default="bedrock-agents")

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Registering Bedrock Agent in Model Registry")
    logger.info("=" * 60)

    bedrock_agent = boto3.client('bedrock-agent', region_name=args.region)
    sm_client = boto3.client('sagemaker', region_name=args.region)

    output = {
        "agent_name": args.agent_name,
        "model_package_group": args.model_package_group_name,
        "model_package_arn": None,
        "status": "unknown"
    }

    try:
        # Get agent details
        agent = get_agent_by_name(bedrock_agent, args.agent_name)
        if not agent:
            raise Exception(f"Agent not found: {args.agent_name}")

        agent_id = agent['agentId']
        agent_arn = agent['agentArn']
        foundation_model = agent.get('foundationModel', 'unknown')

        output["agent_id"] = agent_id
        output["agent_arn"] = agent_arn
        output["foundation_model"] = foundation_model

        # Get alias
        alias = get_agent_alias(bedrock_agent, agent_id, "staging")
        agent_alias_id = alias['agentAliasId'] if alias else "TSTALIASID"
        output["agent_alias_id"] = agent_alias_id

        # Get Knowledge Base information for replication
        kb_info = None
        kb_associations = get_agent_knowledge_bases(bedrock_agent, agent_id)
        if kb_associations:
            logger.info(f"Found {len(kb_associations)} knowledge base(s) associated with agent")
            # Get details of the first KB (primary KB)
            primary_kb_id = kb_associations[0].get('knowledgeBaseId')
            if primary_kb_id:
                kb_info = get_knowledge_base_details(bedrock_agent, primary_kb_id)
                if kb_info:
                    output["knowledge_base_id"] = kb_info.get("knowledge_base_id")
                    output["knowledge_base_arn"] = kb_info.get("knowledge_base_arn")
                    output["knowledge_base_name"] = kb_info.get("name")
                    logger.info(f"Knowledge Base: {kb_info.get('name')} ({primary_kb_id})")

        # Load evaluation metrics if available
        eval_metrics = None
        eval_path = "/opt/ml/processing/input/evaluation/evaluation.json"
        if os.path.exists(eval_path):
            with open(eval_path, 'r') as f:
                eval_data = json.load(f)
                eval_metrics = eval_data.get("metrics", {})

        # Ensure model package group exists
        group_arn = ensure_model_package_group(sm_client, args.model_package_group_name)
        output["model_package_group_arn"] = group_arn


        # Crear y subir el tar.gz dummy con la metadata
        metadata_dict = {
            "agent_id": agent_id,
            "agent_alias_id": agent_alias_id,
            "agent_arn": agent_arn,
            "foundation_model": foundation_model,
            "knowledge_base": kb_info,
            "evaluation_metrics": eval_metrics
        }
        s3_uri = create_and_upload_dummy_tar(
            agent_id,
            metadata_dict,
            args.s3_bucket,
            args.s3_prefix,
            args.region
        )
        logger.info(f"Dummy model.tar.gz uploaded to: {s3_uri}")

        # Registrar el modelo usando la ruta S3 del dummy
        # Extraer bucket y prefix para ModelDataUrl
        s3_bucket = args.s3_bucket
        s3_prefix = args.s3_prefix
        model_data_url = f"s3://{s3_bucket}/{s3_prefix}/{agent_id}/model.tar.gz"
        # El registro real del modelo
        model_package_arn = register_agent_model(
            sm_client,
            args.model_package_group_name,
            agent_id,
            agent_alias_id,
            agent_arn,
            foundation_model,
            args.approval_status,
            eval_metrics,
            kb_info
        )
        output["model_package_arn"] = model_package_arn
        output["approval_status"] = args.approval_status
        output["status"] = "registered"
        logger.info(f"Agent registered successfully")
        logger.info(f"Model Package ARN: {model_package_arn}")
        logger.info(f"Approval Status: {args.approval_status}")

    except Exception as e:
        logger.error(f"Error registering agent: {e}")
        output["status"] = "error"
        output["error"] = str(e)

    # Write output
    output_dir = "/opt/ml/processing/output"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "register_output.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    logger.info(f"Register output written to {output_path}")
    logger.info("=" * 60)
    logger.info(f"Registration completed: {output['status']}")
    logger.info("=" * 60)

    if output["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()

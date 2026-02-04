"""Utility functions for ml_pipelines."""
import json
import logging
import os
from typing import Any, Dict, Optional

import boto3

logger = logging.getLogger(__name__)


def get_sagemaker_session(region: str, default_bucket: Optional[str] = None):
    """Get a SageMaker session.
    
    Args:
        region: AWS region
        default_bucket: Default S3 bucket for SageMaker
        
    Returns:
        SageMaker session object
    """
    import sagemaker
    
    boto_session = boto3.Session(region_name=region)
    
    if default_bucket:
        return sagemaker.session.Session(
            boto_session=boto_session,
            default_bucket=default_bucket
        )
    return sagemaker.session.Session(boto_session=boto_session)


def get_pipeline_config(config_path: str) -> Dict[str, Any]:
    """Load pipeline configuration from file.
    
    Args:
        config_path: Path to configuration file (JSON or YAML)
        
    Returns:
        Configuration dictionary
    """
    if config_path.endswith('.yaml') or config_path.endswith('.yml'):
        import yaml
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    elif config_path.endswith('.json'):
        with open(config_path, 'r') as f:
            return json.load(f)
    else:
        raise ValueError(f"Unsupported config file format: {config_path}")


def resolve_s3_uri(bucket: str, prefix: str) -> str:
    """Construct S3 URI from bucket and prefix.
    
    Args:
        bucket: S3 bucket name
        prefix: S3 key prefix
        
    Returns:
        Full S3 URI
    """
    return f"s3://{bucket}/{prefix}"


def get_account_id() -> str:
    """Get the current AWS account ID."""
    sts = boto3.client('sts')
    return sts.get_caller_identity()['Account']


def get_region() -> str:
    """Get the current AWS region."""
    session = boto3.Session()
    return session.region_name or os.environ.get('AWS_REGION', 'us-east-1')

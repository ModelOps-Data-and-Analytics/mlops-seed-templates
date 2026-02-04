"""Utility functions for agent build pipeline."""
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def load_agent_instruction(file_path: str) -> str:
    """Load agent instruction from file.
    
    Args:
        file_path: Path to instruction file
        
    Returns:
        Agent instruction text
    """
    with open(file_path, 'r') as f:
        return f.read().strip()


def load_api_schema(file_path: str) -> Dict[str, Any]:
    """Load OpenAPI schema from file.
    
    Args:
        file_path: Path to schema JSON file
        
    Returns:
        OpenAPI schema dictionary
    """
    with open(file_path, 'r') as f:
        return json.load(f)


def get_foundation_model_arn(model_id: str, region: str, cross_region: bool = True) -> str:
    """Construct foundation model ARN with optional cross-region inference support.
    
    Claude 3.7 Sonnet supports cross-region inference, allowing the model to be
    invoked from regions where it may not be directly available.
    
    Args:
        model_id: Foundation model ID (e.g., anthropic.claude-3-7-sonnet-20250219-v1:0)
        region: AWS region
        cross_region: Enable cross-region inference (default: True for Claude 3.7)
        
    Returns:
        Full model ARN (cross-region or standard)
    """
    # Cross-region inference profile for Claude 3.7 Sonnet
    # Uses inference profiles for multi-region availability
    if cross_region and "claude-3-7-sonnet" in model_id:
        # Cross-region inference uses inference profiles
        # Format: arn:aws:bedrock:{region}:{account}:inference-profile/{profile-id}
        # For on-demand cross-region, use the standard ARN with cross-region enabled
        return f"arn:aws:bedrock:{region}::foundation-model/{model_id}"
    
    return f"arn:aws:bedrock:{region}::foundation-model/{model_id}"


def get_cross_region_inference_config() -> Dict[str, Any]:
    """Get cross-region inference configuration for Bedrock.
    
    Claude 3.7 Sonnet supports cross-region inference, which allows:
    - Automatic failover to other regions if primary region is unavailable
    - Better availability and resilience for production workloads
    
    Returns:
        Cross-region inference configuration
    """
    return {
        "enabled": True,
        "supported_models": [
            "anthropic.claude-3-7-sonnet-20250219-v1:0"
        ],
        "primary_regions": ["us-east-1", "us-west-2", "eu-west-1"],
        "notes": "Cross-region inference requires appropriate IAM permissions across regions"
    }


def sanitize_agent_name(name: str) -> str:
    """Sanitize agent name to meet Bedrock requirements.
    
    Args:
        name: Original agent name
        
    Returns:
        Sanitized name (alphanumeric, hyphens, underscores only)
    """
    import re
    # Replace invalid characters with hyphens
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '-', name)
    # Remove consecutive hyphens
    sanitized = re.sub(r'-+', '-', sanitized)
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    # Truncate to 100 characters (Bedrock limit)
    return sanitized[:100]


def create_agent_resource_role_policy(enable_cross_region: bool = True) -> Dict[str, Any]:
    """Create IAM policy for Bedrock agent resource role.
    
    Args:
        enable_cross_region: Enable cross-region inference permissions (default: True)
    
    Returns:
        IAM policy document
    """
    statements = [
        {
            "Sid": "BedrockInvokeModel",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            # Cross-region inference requires permissions in all potential regions
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-7-sonnet-20250219-v1:0",
                "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0"
            ]
        },
        {
            "Sid": "BedrockKnowledgeBase",
            "Effect": "Allow",
            "Action": [
                "bedrock:Retrieve",
                "bedrock:RetrieveAndGenerate"
            ],
            "Resource": "arn:aws:bedrock:*:*:knowledge-base/*"
        },
        {
            "Sid": "LambdaInvoke",
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": "arn:aws:lambda:*:*:function:*"
        },
        {
            "Sid": "S3Access",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket",
                "s3:PutObject"
            ],
            "Resource": [
                "arn:aws:s3:::*",
                "arn:aws:s3:::*/*"
            ]
        }
    ]
    
    # Add cross-region inference permissions
    if enable_cross_region:
        statements.append({
            "Sid": "BedrockCrossRegionInference",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:GetInferenceProfile",
                "bedrock:ListInferenceProfiles"
            ],
            "Resource": [
                "arn:aws:bedrock:us-east-1::foundation-model/*",
                "arn:aws:bedrock:us-west-2::foundation-model/*",
                "arn:aws:bedrock:eu-west-1::foundation-model/*",
                "arn:aws:bedrock:*:*:inference-profile/*"
            ]
        })
    
    return {
        "Version": "2012-10-17",
        "Statement": statements
    }

"""Fetch approved model package from SageMaker Model Registry."""
import logging
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_latest_approved_package(
    model_package_group_name: str,
    region: str = "us-east-1"
) -> Optional[Dict]:
    """Get the latest approved model package.
    
    Args:
        model_package_group_name: Model package group name
        region: AWS region
        
    Returns:
        Model package details if found
    """
    sm_client = boto3.client("sagemaker", region_name=region)
    
    try:
        response = sm_client.list_model_packages(
            ModelPackageGroupName=model_package_group_name,
            ModelApprovalStatus="Approved",
            SortBy="CreationTime",
            SortOrder="Descending",
            MaxResults=1
        )
        
        packages = response.get("ModelPackageSummaryList", [])
        if not packages:
            logger.info("No approved packages found")
            return None
        
        package_arn = packages[0]["ModelPackageArn"]
        
        # Get full details
        details = sm_client.describe_model_package(
            ModelPackageName=package_arn
        )
        
        return {
            "model_package_arn": package_arn,
            "model_package_group_name": model_package_group_name,
            "approval_status": details.get("ModelApprovalStatus"),
            "creation_time": str(details.get("CreationTime")),
            "metadata": details.get("CustomerMetadataProperties", {})
        }
        
    except ClientError as e:
        logger.error(f"Error fetching approved package: {e}")
        return None


def get_agent_info_from_package(
    model_package_arn: str,
    region: str = "us-east-1"
) -> Optional[Dict]:
    """Extract agent information from model package.
    
    Args:
        model_package_arn: Model package ARN
        region: AWS region
        
    Returns:
        Agent information
    """
    sm_client = boto3.client("sagemaker", region_name=region)
    
    try:
        response = sm_client.describe_model_package(
            ModelPackageName=model_package_arn
        )
        
        metadata = response.get("CustomerMetadataProperties", {})
        
        return {
            "agent_id": metadata.get("agent_id"),
            "agent_alias_id": metadata.get("agent_alias_id"),
            "agent_arn": metadata.get("agent_arn"),
            "foundation_model": metadata.get("foundation_model"),
            "success_rate": metadata.get("success_rate"),
            "total_tests": metadata.get("total_tests")
        }
        
    except ClientError as e:
        logger.error(f"Error getting package details: {e}")
        return None

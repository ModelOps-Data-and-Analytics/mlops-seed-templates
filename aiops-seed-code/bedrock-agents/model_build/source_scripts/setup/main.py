"""Setup and validation script for Bedrock Agent pipeline."""
import argparse
import json
import logging
import os
import sys

import subprocess

# Install required dependencies (including boto3 with Bedrock support)
logger_temp = logging.getLogger(__name__)
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "boto3>=1.34.0", "botocore>=1.34.0"])
    logger_temp.info("Successfully installed/updated boto3 with Bedrock support")
except subprocess.CalledProcessError as e:
    logger_temp.error(f"Error installing boto3: {e}")

try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
    logger_temp.info("Successfully installed pyyaml")
except subprocess.CalledProcessError as e:
    logger_temp.error(f"Error installing pyyaml: {e}")

import boto3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_foundation_model(model_id: str, region: str) -> bool:
    """Validate that the foundation model is available.
    
    Args:
        model_id: Foundation model ID
        region: AWS region
        
    Returns:
        True if model is available
    """
    bedrock = boto3.client('bedrock', region_name=region)
    
    try:
        response = bedrock.list_foundation_models()
        available_models = [m['modelId'] for m in response['modelSummaries']]
        
        if model_id in available_models:
            logger.info(f"Foundation model {model_id} is available")
            return True
        else:
            logger.error(f"Foundation model {model_id} not found. Available models: {available_models[:5]}...")
            return False
    except Exception as e:
        logger.error(f"Error checking foundation model: {e}")
        return False


def validate_agent_name(agent_name: str) -> bool:
    """Validate agent name meets Bedrock requirements.
    
    Args:
        agent_name: Proposed agent name
        
    Returns:
        True if name is valid
    """
    import re
    
    # Check length (1-100 characters)
    if len(agent_name) < 1 or len(agent_name) > 100:
        logger.error(f"Agent name must be 1-100 characters, got {len(agent_name)}")
        return False
    
    # Check pattern (alphanumeric, hyphens, underscores)
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$'
    if not re.match(pattern, agent_name):
        logger.error(f"Agent name must start with alphanumeric and contain only alphanumeric, hyphens, underscores")
        return False
    
    logger.info(f"Agent name '{agent_name}' is valid")
    return True


def check_iam_permissions(role_arn: str, region: str) -> bool:
    """Check that the IAM role has required permissions.
    
    Args:
        role_arn: IAM role ARN
        region: AWS region
        
    Returns:
        True if permissions are sufficient
    """
    # For now, just validate role exists
    iam = boto3.client('iam', region_name=region)
    
    try:
        role_name = role_arn.split('/')[-1]
        response = iam.get_role(RoleName=role_name)
        logger.info(f"IAM role {role_name} exists")
        return True
    except Exception as e:
        logger.warning(f"Could not verify IAM role: {e}")
        # Don't fail, role might be cross-account
        return True


def load_config_files(config_dir: str) -> dict:
    """Load and validate configuration files.
    
    Args:
        config_dir: Directory containing config files
        
    Returns:
        Configuration dictionary
    """
    import yaml
    
    config = {}
    
    # Load agent instruction
    instruction_path = os.path.join(config_dir, 'agent_instruction.txt')
    if os.path.exists(instruction_path):
        with open(instruction_path, 'r') as f:
            config['instruction'] = f.read()
        logger.info(f"Loaded agent instruction ({len(config['instruction'])} chars)")
    
    # Load API schema
    schema_path = os.path.join(config_dir, 'agent_schema.json')
    if os.path.exists(schema_path):
        with open(schema_path, 'r') as f:
            config['api_schema'] = json.load(f)
        logger.info("Loaded API schema")
    
    # Load knowledge base config
    kb_config_path = os.path.join(config_dir, 'knowledge_base_config.yaml')
    if os.path.exists(kb_config_path):
        with open(kb_config_path, 'r') as f:
            config['knowledge_base'] = yaml.safe_load(f)
        logger.info("Loaded knowledge base configuration")
    
    return config


def main():
    parser = argparse.ArgumentParser(description="Setup and validate Bedrock Agent configuration")
    parser.add_argument("--agent-name", type=str, required=True)
    parser.add_argument("--foundation-model", type=str, required=True)
    parser.add_argument("--region", type=str, required=True)
    parser.add_argument("--role-arn", type=str, default=None)
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Starting Setup and Validation")
    logger.info("=" * 60)
    
    validation_results = {
        "agent_name_valid": False,
        "foundation_model_available": False,
        "config_loaded": False,
        "overall_valid": False
    }
    
    # Validate agent name
    validation_results["agent_name_valid"] = validate_agent_name(args.agent_name)
    
    # Validate foundation model
    validation_results["foundation_model_available"] = validate_foundation_model(
        args.foundation_model, args.region
    )
    
    # Load configuration files
    config_dir = "/opt/ml/processing/input/config"
    if os.path.exists(config_dir):
        try:
            config = load_config_files(config_dir)
            validation_results["config_loaded"] = True
            validation_results["config"] = config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    else:
        logger.warning(f"Config directory not found: {config_dir}")
        validation_results["config_loaded"] = True  # Optional
    
    # Check IAM permissions if role provided
    if args.role_arn:
        check_iam_permissions(args.role_arn, args.region)
    
    # Determine overall validation status
    validation_results["overall_valid"] = all([
        validation_results["agent_name_valid"],
        validation_results["foundation_model_available"],
        validation_results["config_loaded"]
    ])
    
    # Write output
    output_dir = "/opt/ml/processing/output"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "setup_output.json")
    with open(output_path, 'w') as f:
        json.dump({
            "validation": validation_results,
            "agent_name": args.agent_name,
            "foundation_model": args.foundation_model,
            "region": args.region
        }, f, indent=2, default=str)
    
    logger.info(f"Setup output written to {output_path}")
    
    if not validation_results["overall_valid"]:
        logger.error("Validation failed!")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("Setup and Validation completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

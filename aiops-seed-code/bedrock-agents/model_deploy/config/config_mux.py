"""Configuration multiplexer for multi-environment support."""
import os
from pathlib import Path
from typing import Any, Dict

import yaml


def get_config(environment: str = "dev") -> Dict[str, Any]:
    """Get configuration for specified environment.
    
    Args:
        environment: Target environment (dev, staging, prod)
        
    Returns:
        Configuration dictionary
    """
    config_dir = Path(__file__).parent
    
    # Load base config
    config = {
        "environment": environment,
        "region": os.getenv("AWS_REGION", "us-east-1"),
    }
    
    # Load environment-specific constants
    try:
        env_constants_path = config_dir / environment / "constants.py"
        if env_constants_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"constants_{environment}",
                env_constants_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Add all uppercase attributes as config
            for attr in dir(module):
                if attr.isupper():
                    config[attr.lower()] = getattr(module, attr)
    except Exception as e:
        print(f"Warning: Could not load environment constants: {e}")
    
    # Load agent config YAML
    try:
        agent_config_path = config_dir / environment / "agent-config.yml"
        if agent_config_path.exists():
            with open(agent_config_path, 'r') as f:
                agent_config = yaml.safe_load(f)
                config["agent_config"] = agent_config
    except Exception as e:
        print(f"Warning: Could not load agent config: {e}")
    
    return config


def get_model_package_group_name(environment: str) -> str:
    """Get model package group name for environment.
    
    Args:
        environment: Target environment
        
    Returns:
        Model package group name
    """
    base_name = os.getenv("MODEL_PACKAGE_GROUP", "BedrockAgentPackageGroup")
    return f"{base_name}-{environment}"

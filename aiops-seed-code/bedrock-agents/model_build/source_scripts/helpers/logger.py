"""Logging utilities for pipeline scripts."""
import logging
import sys
from typing import Optional


def setup_logger(
    name: str,
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> logging.Logger:
    """Set up a logger with console handler.
    
    Args:
        name: Logger name
        level: Logging level
        format_string: Custom format string
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Set format
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


def log_step_start(logger: logging.Logger, step_name: str) -> None:
    """Log step start with visual separator.
    
    Args:
        logger: Logger instance
        step_name: Name of the step
    """
    logger.info("=" * 60)
    logger.info(f"Starting: {step_name}")
    logger.info("=" * 60)


def log_step_end(logger: logging.Logger, step_name: str, status: str) -> None:
    """Log step end with status.
    
    Args:
        logger: Logger instance
        step_name: Name of the step
        status: Step completion status
    """
    logger.info("=" * 60)
    logger.info(f"Completed: {step_name} - Status: {status}")
    logger.info("=" * 60)

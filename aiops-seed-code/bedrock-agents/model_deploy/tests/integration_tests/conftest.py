"""Pytest configuration for integration tests."""
import pytest


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--agent-id",
        action="store",
        default=None,
        help="Bedrock Agent ID to test"
    )
    parser.addoption(
        "--environment",
        action="store",
        default="dev",
        help="Target environment"
    )
    parser.addoption(
        "--region",
        action="store",
        default="us-east-1",
        help="AWS region"
    )


@pytest.fixture
def agent_id(request):
    """Get agent ID from command line."""
    return request.config.getoption("--agent-id")


@pytest.fixture
def environment(request):
    """Get environment from command line."""
    return request.config.getoption("--environment")


@pytest.fixture
def region(request):
    """Get region from command line."""
    return request.config.getoption("--region")

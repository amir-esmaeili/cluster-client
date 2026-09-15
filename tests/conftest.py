"""Pytest fixtures and configuration."""

import pytest
import respx

from cluster_client.config import Config
from cluster_client.http_client import HTTPClient


@pytest.fixture
def config() -> Config:
    """Basic configuration for testing."""
    return Config(
        hosts=["node1.example.com", "node2.example.com", "node3.example.com"],
        connect_timeout=5.0,
        read_timeout=30.0,
        max_retry_attempts=3,
        base_backoff_delay=0.1,  # Shorter for tests
        treat_create_conflict_as_success=False,
    )


@pytest.fixture
def config_with_conflict_success() -> Config:
    """Configuration that treats create conflicts as success."""
    return Config(
        hosts=["node1.example.com", "node2.example.com", "node3.example.com"],
        connect_timeout=5.0,
        read_timeout=30.0,
        max_retry_attempts=3,
        base_backoff_delay=0.1,
        treat_create_conflict_as_success=True,
    )


@pytest.fixture
def single_node_config() -> Config:
    """Configuration with a single node."""
    return Config(
        hosts=["node1.example.com"],
        connect_timeout=5.0,
        read_timeout=30.0,
        max_retry_attempts=3,
        base_backoff_delay=0.1,
        treat_create_conflict_as_success=False,
    )


@pytest.fixture
async def http_client(config: Config) -> HTTPClient:
    """HTTP client fixture."""
    client = HTTPClient(config)
    yield client
    await client.close()


@pytest.fixture
def respx_mock() -> respx.MockRouter:
    """Respx mock router fixture."""
    with respx.mock(assert_all_called=False) as router:
        yield router

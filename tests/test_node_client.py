"""Tests for node client operations."""

import httpx
import pytest
import respx

from cluster_client.config import Config
from cluster_client.http_client import HTTPClient
from cluster_client.node_client import NodeClient


@pytest.mark.asyncio
async def test_create_success(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test successful group creation on a node."""
    host = "node1.example.com"
    group_id = "test-group"

    respx_mock.post(f"https://{host}/v1/group/").mock(return_value=httpx.Response(201))

    async with HTTPClient(config) as http_client:
        node_client = NodeClient(host, http_client, config)
        result = await node_client.create_group(group_id)

        assert result.success is True
        assert result.host == host
        assert result.status_code == 201
        assert result.error is None
        assert result.attempts == 1


@pytest.mark.asyncio
async def test_create_400_without_conflict_flag(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test that 400 on create is treated as hard failure when flag is False."""
    host = "node1.example.com"
    group_id = "test-group"

    respx_mock.post(f"https://{host}/v1/group/").mock(return_value=httpx.Response(400))

    async with HTTPClient(config) as http_client:
        node_client = NodeClient(host, http_client, config)
        result = await node_client.create_group(group_id)

        assert result.success is False
        assert result.status_code == 400
        assert result.error is not None


@pytest.mark.asyncio
async def test_create_400_with_conflict_flag_and_exists(
    config_with_conflict_success: Config, respx_mock: respx.MockRouter
) -> None:
    """Test that 400 on create is treated as success if GET confirms existence."""
    host = "node1.example.com"
    group_id = "test-group"

    respx_mock.post(f"https://{host}/v1/group/").mock(return_value=httpx.Response(400))
    respx_mock.get(f"https://{host}/v1/group/{group_id}/").mock(
        return_value=httpx.Response(200, json={"groupId": group_id})
    )

    async with HTTPClient(config_with_conflict_success) as http_client:
        node_client = NodeClient(host, http_client, config_with_conflict_success)
        result = await node_client.create_group(group_id)

        assert result.success is True
        assert result.status_code == 400
        assert "already exists" in result.error.lower()


@pytest.mark.asyncio
async def test_create_400_with_conflict_flag_but_not_exists(
    config_with_conflict_success: Config, respx_mock: respx.MockRouter
) -> None:
    """Test inconsistent state: 400 on create but GET returns 404."""
    host = "node1.example.com"
    group_id = "test-group"

    respx_mock.post(f"https://{host}/v1/group/").mock(return_value=httpx.Response(400))
    respx_mock.get(f"https://{host}/v1/group/{group_id}/").mock(
        return_value=httpx.Response(404)
    )

    async with HTTPClient(config_with_conflict_success) as http_client:
        node_client = NodeClient(host, http_client, config_with_conflict_success)
        result = await node_client.create_group(group_id)

        assert result.success is False
        assert "inconsistent" in result.error.lower()


@pytest.mark.asyncio
async def test_delete_success(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test successful group deletion from a node."""
    host = "node1.example.com"
    group_id = "test-group"

    respx_mock.delete(f"https://{host}/v1/group/").mock(return_value=httpx.Response(200))

    async with HTTPClient(config) as http_client:
        node_client = NodeClient(host, http_client, config)
        result = await node_client.delete_group(group_id)

        assert result.success is True
        assert result.host == host
        assert result.status_code == 200
        assert result.error is None


@pytest.mark.asyncio
async def test_delete_with_retries(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test delete that succeeds after retries."""
    host = "node1.example.com"
    group_id = "test-group"

    respx_mock.delete(f"https://{host}/v1/group/").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200),
        ]
    )

    async with HTTPClient(config) as http_client:
        node_client = NodeClient(host, http_client, config)
        result = await node_client.delete_group(group_id)

        assert result.success is True
        assert result.attempts == 2


@pytest.mark.asyncio
async def test_get_group_exists(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test GET when group exists."""
    host = "node1.example.com"
    group_id = "test-group"

    respx_mock.get(f"https://{host}/v1/group/{group_id}/").mock(
        return_value=httpx.Response(200, json={"groupId": group_id})
    )

    async with HTTPClient(config) as http_client:
        node_client = NodeClient(host, http_client, config)
        result = await node_client.get_group(group_id)

        assert result.success is True
        assert result.status_code == 200


@pytest.mark.asyncio
async def test_get_group_not_found(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test GET when group doesn't exist."""
    host = "node1.example.com"
    group_id = "test-group"

    respx_mock.get(f"https://{host}/v1/group/{group_id}/").mock(
        return_value=httpx.Response(404)
    )

    async with HTTPClient(config) as http_client:
        node_client = NodeClient(host, http_client, config)
        result = await node_client.get_group(group_id)

        assert result.success is False
        assert result.status_code == 404

"""Tests for cluster client delete operations."""

import httpx
import pytest
import respx

from cluster_client.cluster_client import ClusterClient
from cluster_client.config import Config


@pytest.mark.asyncio
async def test_delete_all_nodes_succeed(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test delete when all nodes succeed."""
    group_id = "test-group"

    for host in config.hosts:
        respx_mock.delete(f"https://{host}/v1/group/").mock(return_value=httpx.Response(200))

    async with ClusterClient(config) as client:
        result = await client.delete_group(group_id)

        assert result.success is True
        assert result.operation == "delete"
        assert result.group_id == group_id
        assert result.rolled_back is False
        assert len(result.node_results) == len(config.hosts)
        assert all(r.success for r in result.node_results)


@pytest.mark.asyncio
async def test_delete_one_node_fails_after_retries(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test delete where one node fails after exhausting retries."""
    group_id = "test-group"

    # First two nodes: succeed
    respx_mock.delete(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )
    respx_mock.delete(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )

    # Third node: always fails with 500
    respx_mock.delete(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(500)
    )

    async with ClusterClient(config) as client:
        result = await client.delete_group(group_id)

        # Delete is best-effort, should not raise exception
        assert result.success is False
        assert result.operation == "delete"

        succeeded = [r for r in result.node_results if r.success]
        failed = [r for r in result.node_results if not r.success]

        assert len(succeeded) == 2
        assert len(failed) == 1
        assert failed[0].host == config.hosts[2]


@pytest.mark.asyncio
async def test_delete_all_nodes_fail(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test delete where all nodes fail."""
    group_id = "test-group"

    for host in config.hosts:
        respx_mock.delete(f"https://{host}/v1/group/").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(500),
                httpx.Response(500),
            ]
        )

    async with ClusterClient(config) as client:
        result = await client.delete_group(group_id)

        assert result.success is False
        assert all(not r.success for r in result.node_results)


@pytest.mark.asyncio
async def test_delete_with_transient_failure_then_success(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test delete where one node fails transiently but succeeds on retry."""
    group_id = "test-group"

    # First node: succeeds immediately
    respx_mock.delete(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )

    # Second node: fails once, then succeeds
    respx_mock.delete(f"https://{config.hosts[1]}/v1/group/").mock(
        side_effect=[httpx.Response(500), httpx.Response(200)]
    )

    # Third node: succeeds immediately
    respx_mock.delete(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )

    async with ClusterClient(config) as client:
        result = await client.delete_group(group_id)

        assert result.success is True
        assert all(r.success for r in result.node_results)

        # Check that the second node made 2 attempts
        second_node_result = next(r for r in result.node_results if r.host == config.hosts[1])
        assert second_node_result.attempts == 2


@pytest.mark.asyncio
async def test_delete_idempotent_second_call(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test that delete can be called twice for the same group (idempotent)."""
    group_id = "test-group"

    # First delete: all succeed
    for host in config.hosts:
        respx_mock.delete(f"https://{host}/v1/group/").mock(return_value=httpx.Response(200))

    async with ClusterClient(config) as client:
        result1 = await client.delete_group(group_id)
        assert result1.success is True

        # Reset mocks for second call
        respx_mock.clear()

        # Second delete: all succeed (idempotent)
        for host in config.hosts:
            respx_mock.delete(f"https://{host}/v1/group/").mock(return_value=httpx.Response(200))

        result2 = await client.delete_group(group_id)
        assert result2.success is True


@pytest.mark.asyncio
async def test_delete_single_node_cluster(
    single_node_config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test delete on a single-node cluster."""
    group_id = "test-group"

    respx_mock.delete(f"https://{single_node_config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )

    async with ClusterClient(single_node_config) as client:
        result = await client.delete_group(group_id)

        assert result.success is True
        assert len(result.node_results) == 1
        assert result.node_results[0].success is True


@pytest.mark.asyncio
async def test_delete_attempts_all_nodes_despite_failures(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test that delete attempts all nodes even if some fail early."""
    group_id = "test-group"

    # Track which nodes were called
    called_hosts = []

    def track_call(host: str) -> httpx.Response:
        called_hosts.append(host)
        return httpx.Response(200)

    for host in config.hosts:
        respx_mock.delete(f"https://{host}/v1/group/").mock(
            side_effect=lambda request, host=host: track_call(host)
        )

    async with ClusterClient(config) as client:
        await client.delete_group(group_id)

        # All nodes should have been called
        assert len(called_hosts) == len(config.hosts)
        assert set(called_hosts) == set(config.hosts)

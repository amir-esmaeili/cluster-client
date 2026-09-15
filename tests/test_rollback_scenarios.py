"""Tests for rollback scenarios and edge cases."""

import httpx
import pytest
import respx

from cluster_client.cluster_client import ClusterClient
from cluster_client.config import Config
from cluster_client.errors import RollbackIncompleteError


@pytest.mark.asyncio
async def test_rollback_incomplete_one_node_fails(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test RollbackIncompleteError when rollback fails on one node."""
    group_id = "test-group"

    # Create: first two nodes succeed, third fails
    respx_mock.post(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )
    respx_mock.post(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )
    respx_mock.post(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(400)
    )

    # Rollback: first node succeeds, second node fails
    respx_mock.delete(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )
    respx_mock.delete(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(500)
    )

    async with ClusterClient(config) as client:
        with pytest.raises(RollbackIncompleteError) as exc_info:
            await client.create_group(group_id)

        error = exc_info.value
        assert error.group_id == group_id
        assert len(error.orphaned_nodes) == 1
        assert config.hosts[1] in error.orphaned_nodes
        assert len(error.node_results) == 3
        assert len(error.rollback_results) == 2

        # Verify message contains group_id and orphaned node
        assert group_id in str(error)
        assert config.hosts[1] in str(error)


@pytest.mark.asyncio
async def test_rollback_incomplete_multiple_nodes_fail(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test RollbackIncompleteError when rollback fails on multiple nodes."""
    group_id = "test-group"

    # Create: all succeed
    for host in config.hosts:
        respx_mock.post(f"https://{host}/v1/group/").mock(return_value=httpx.Response(201))

    # Now simulate a failure that triggers rollback by posting again
    # (in practice we'd need to trigger failure differently, but for testing
    # let's create a scenario where create succeeds but we force a failure)

    # Actually, let's use a more realistic scenario:
    # Create: first two succeed, third fails
    respx_mock.reset()
    respx_mock.post(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )
    respx_mock.post(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )
    respx_mock.post(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(400)
    )

    # Rollback: both fail
    respx_mock.delete(f"https://{config.hosts[0]}/v1/group/").mock(
        side_effect=[httpx.Response(500)] * 3
    )
    respx_mock.delete(f"https://{config.hosts[1]}/v1/group/").mock(
        side_effect=[httpx.Response(500)] * 3
    )

    async with ClusterClient(config) as client:
        with pytest.raises(RollbackIncompleteError) as exc_info:
            await client.create_group(group_id)

        error = exc_info.value
        assert len(error.orphaned_nodes) == 2
        assert config.hosts[0] in error.orphaned_nodes
        assert config.hosts[1] in error.orphaned_nodes


@pytest.mark.asyncio
async def test_rollback_incomplete_exact_structure(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test the exact structure and content of RollbackIncompleteError."""
    group_id = "test-group-123"

    # Create: first node succeeds, others fail
    respx_mock.post(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )
    respx_mock.post(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(400)
    )
    respx_mock.post(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(400)
    )

    # Rollback: first node delete fails
    respx_mock.delete(f"https://{config.hosts[0]}/v1/group/").mock(
        side_effect=[httpx.Response(500)] * 3
    )

    async with ClusterClient(config) as client:
        with pytest.raises(RollbackIncompleteError) as exc_info:
            await client.create_group(group_id)

        error = exc_info.value

        # Verify all attributes exist and have correct types
        assert isinstance(error.group_id, str)
        assert error.group_id == group_id

        assert isinstance(error.orphaned_nodes, list)
        assert all(isinstance(node, str) for node in error.orphaned_nodes)
        assert error.orphaned_nodes == [config.hosts[0]]

        assert isinstance(error.node_results, list)
        assert len(error.node_results) == 3

        assert isinstance(error.rollback_results, list)
        assert len(error.rollback_results) == 1

        # Verify the rollback result indicates failure
        assert error.rollback_results[0].success is False
        assert error.rollback_results[0].host == config.hosts[0]


@pytest.mark.asyncio
async def test_successful_rollback_after_partial_create_failure(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test that successful rollback returns ClusterOperationResult, not exception."""
    group_id = "test-group"

    # Create: two succeed, one fails
    respx_mock.post(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )
    respx_mock.post(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(400)
    )
    respx_mock.post(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    # Rollback: both succeed
    respx_mock.delete(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )
    respx_mock.delete(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )

    async with ClusterClient(config) as client:
        # Should NOT raise RollbackIncompleteError
        result = await client.create_group(group_id)

        assert result.success is False
        assert result.rolled_back is True
        assert result.rollback_results is not None
        assert len(result.rollback_results) == 2
        assert all(r.success for r in result.rollback_results)


@pytest.mark.asyncio
async def test_rollback_with_retry_success(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test that rollback itself uses retry logic and can succeed after transient failures."""
    group_id = "test-group"

    # Create: two succeed, one fails
    respx_mock.post(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )
    respx_mock.post(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(400)
    )
    respx_mock.post(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    # Rollback: first node fails once then succeeds, second succeeds immediately
    respx_mock.delete(f"https://{config.hosts[0]}/v1/group/").mock(
        side_effect=[httpx.Response(500), httpx.Response(200)]
    )
    respx_mock.delete(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )

    async with ClusterClient(config) as client:
        result = await client.create_group(group_id)

        assert result.success is False
        assert result.rolled_back is True
        assert all(r.success for r in result.rollback_results)

        # First node should show 2 attempts
        first_rollback = next(r for r in result.rollback_results if r.host == config.hosts[0])
        assert first_rollback.attempts == 2


@pytest.mark.asyncio
async def test_no_rollback_when_all_creates_fail(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test that no rollback is attempted when all creates fail."""
    group_id = "test-group"

    # All create operations fail
    for host in config.hosts:
        respx_mock.post(f"https://{host}/v1/group/").mock(return_value=httpx.Response(400))

    async with ClusterClient(config) as client:
        result = await client.create_group(group_id)

        assert result.success is False
        assert result.rolled_back is False
        assert result.rollback_results is None
        assert all(not r.success for r in result.node_results)


@pytest.mark.asyncio
async def test_empty_cluster_handled_gracefully(respx_mock: respx.MockRouter) -> None:
    """Test behavior with an empty host list."""
    empty_config = Config(
        hosts=[],
        max_retry_attempts=3,
        base_backoff_delay=0.1,
    )

    async with ClusterClient(empty_config) as client:
        result = await client.create_group("test-group")

        # Should handle gracefully with no node results
        assert result.success is True  # Vacuous truth: no failures
        assert len(result.node_results) == 0

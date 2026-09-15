"""Tests for cluster client create operations."""

import httpx
import pytest
import respx

from cluster_client.cluster_client import ClusterClient
from cluster_client.config import Config


@pytest.mark.asyncio
async def test_create_all_nodes_succeed(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test create when all nodes succeed."""
    group_id = "test-group"

    for host in config.hosts:
        respx_mock.post(f"https://{host}/v1/group/").mock(return_value=httpx.Response(201))

    async with ClusterClient(config) as client:
        result = await client.create_group(group_id)

        assert result.success is True
        assert result.operation == "create"
        assert result.group_id == group_id
        assert result.rolled_back is False
        assert len(result.node_results) == len(config.hosts)
        assert all(r.success for r in result.node_results)


@pytest.mark.asyncio
async def test_create_one_node_fails_transiently_then_succeeds(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test create where one node fails transiently but succeeds on retry."""
    group_id = "test-group"

    # First node: succeeds immediately
    respx_mock.post(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    # Second node: fails once with 500, then succeeds
    respx_mock.post(f"https://{config.hosts[1]}/v1/group/").mock(
        side_effect=[httpx.Response(500), httpx.Response(201)]
    )

    # Third node: succeeds immediately
    respx_mock.post(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    async with ClusterClient(config) as client:
        result = await client.create_group(group_id)

        assert result.success is True
        assert result.rolled_back is False
        assert all(r.success for r in result.node_results)

        # Check that the second node made 2 attempts
        second_node_result = next(r for r in result.node_results if r.host == config.hosts[1])
        assert second_node_result.attempts == 2


@pytest.mark.asyncio
async def test_create_one_node_fails_permanently_triggers_rollback(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test create where one node fails permanently, triggering successful rollback."""
    group_id = "test-group"

    # First two nodes: create succeeds
    respx_mock.post(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )
    respx_mock.post(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    # Third node: create fails with 400
    respx_mock.post(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(400)
    )

    # Rollback: delete from first two nodes
    respx_mock.delete(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )
    respx_mock.delete(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )

    async with ClusterClient(config) as client:
        result = await client.create_group(group_id)

        assert result.success is False
        assert result.rolled_back is True
        assert result.rollback_results is not None
        assert len(result.rollback_results) == 2
        assert all(r.success for r in result.rollback_results)

        # Check node results
        succeeded = [r for r in result.node_results if r.success]
        failed = [r for r in result.node_results if not r.success]
        assert len(succeeded) == 2
        assert len(failed) == 1


@pytest.mark.asyncio
async def test_create_all_nodes_fail_no_rollback_needed(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test create where all nodes fail, so no rollback is needed."""
    group_id = "test-group"

    for host in config.hosts:
        respx_mock.post(f"https://{host}/v1/group/").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(500),
                httpx.Response(500),
            ]
        )

    async with ClusterClient(config) as client:
        result = await client.create_group(group_id)

        assert result.success is False
        assert result.rolled_back is False
        assert result.rollback_results is None
        assert all(not r.success for r in result.node_results)


@pytest.mark.asyncio
async def test_create_with_conflict_flag_false_triggers_rollback(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test create with 400 and treat_create_conflict_as_success=False."""
    group_id = "test-group"

    # First node: succeeds
    respx_mock.post(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    # Second node: 400 (conflict)
    respx_mock.post(f"https://{config.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(400)
    )

    # Third node: succeeds
    respx_mock.post(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    # Rollback first and third nodes
    respx_mock.delete(f"https://{config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )
    respx_mock.delete(f"https://{config.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(200)
    )

    async with ClusterClient(config) as client:
        result = await client.create_group(group_id)

        assert result.success is False
        assert result.rolled_back is True


@pytest.mark.asyncio
async def test_create_with_conflict_flag_true_no_rollback(
    config_with_conflict_success: Config, respx_mock: respx.MockRouter
) -> None:
    """Test create with 400 and treat_create_conflict_as_success=True."""
    group_id = "test-group"

    # First node: succeeds
    respx_mock.post(f"https://{config_with_conflict_success.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    # Second node: 400 but GET confirms it exists
    respx_mock.post(f"https://{config_with_conflict_success.hosts[1]}/v1/group/").mock(
        return_value=httpx.Response(400)
    )
    respx_mock.get(f"https://{config_with_conflict_success.hosts[1]}/v1/group/{group_id}/").mock(
        return_value=httpx.Response(200, json={"groupId": group_id})
    )

    # Third node: succeeds
    respx_mock.post(f"https://{config_with_conflict_success.hosts[2]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    async with ClusterClient(config_with_conflict_success) as client:
        result = await client.create_group(group_id)

        assert result.success is True
        assert result.rolled_back is False
        assert all(r.success for r in result.node_results)


@pytest.mark.asyncio
async def test_create_single_node_cluster(
    single_node_config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test create on a single-node cluster."""
    group_id = "test-group"

    respx_mock.post(f"https://{single_node_config.hosts[0]}/v1/group/").mock(
        return_value=httpx.Response(201)
    )

    async with ClusterClient(single_node_config) as client:
        result = await client.create_group(group_id)

        assert result.success is True
        assert len(result.node_results) == 1
        assert result.node_results[0].success is True

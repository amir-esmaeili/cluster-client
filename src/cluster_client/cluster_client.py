import asyncio
import logging
import uuid

from cluster_client.config import Config
from cluster_client.errors import RollbackIncompleteError
from cluster_client.http_client import HTTPClient
from cluster_client.logging_config import clear_correlation_id, set_correlation_id
from cluster_client.models import ClusterOperationResult, NodeResult
from cluster_client.node_client import NodeClient

logger = logging.getLogger(__name__)


class ClusterClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.http_client = HTTPClient(config)
        self.node_clients = [
            NodeClient(host, self.http_client, config) for host in config.hosts
        ]

    async def close(self) -> None:
        await self.http_client.close()

    async def __aenter__(self) -> "ClusterClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def create_group(self, group_id: str) -> ClusterOperationResult:
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        try:
            logger.info(
                f"Starting create operation for group '{group_id}' across {len(self.node_clients)} nodes",
                extra={"operation": "create", "group_id": group_id},
            )

            create_tasks = [
                client.create_group(group_id) for client in self.node_clients
            ]
            node_results = await asyncio.gather(*create_tasks, return_exceptions=False)

            succeeded_nodes = [result for result in node_results if result.success]
            failed_nodes = [result for result in node_results if not result.success]

            if not failed_nodes:
                logger.info(
                    f"Create operation succeeded on all {len(succeeded_nodes)} nodes",
                    extra={"operation": "create", "group_id": group_id},
                )
                return ClusterOperationResult(
                    operation="create",
                    group_id=group_id,
                    success=True,
                    node_results=node_results,
                    rolled_back=False,
                )

            logger.warning(
                f"Create failed on {len(failed_nodes)} nodes, initiating rollback on {len(succeeded_nodes)} nodes",
                extra={"operation": "create", "group_id": group_id},
            )

            if not succeeded_nodes:
                logger.info(
                    "All nodes failed, no rollback needed",
                    extra={"operation": "create", "group_id": group_id},
                )
                return ClusterOperationResult(
                    operation="create",
                    group_id=group_id,
                    success=False,
                    node_results=node_results,
                    rolled_back=False,
                )

            rollback_results = await self._rollback_creates(
                group_id, succeeded_nodes
            )

            rollback_failures = [
                result for result in rollback_results if not result.success
            ]

            if rollback_failures:
                orphaned_nodes = [result.host for result in rollback_failures]
                logger.critical(
                    f"Rollback incomplete for group '{group_id}'. "
                    f"Orphaned nodes: {', '.join(orphaned_nodes)}",
                    extra={
                        "operation": "create",
                        "group_id": group_id,
                        "orphaned_nodes": orphaned_nodes,
                    },
                )
                raise RollbackIncompleteError(
                    group_id=group_id,
                    orphaned_nodes=orphaned_nodes,
                    node_results=node_results,
                    rollback_results=rollback_results,
                )

            logger.info(
                f"Rollback completed successfully on all {len(rollback_results)} nodes",
                extra={"operation": "create", "group_id": group_id},
            )
            return ClusterOperationResult(
                operation="create",
                group_id=group_id,
                success=False,
                node_results=node_results,
                rolled_back=True,
                rollback_results=rollback_results,
            )

        finally:
            clear_correlation_id()

    async def _rollback_creates(
        self, group_id: str, succeeded_results: list[NodeResult]
    ) -> list[NodeResult]:
        logger.info(
            f"Rolling back creates on {len(succeeded_results)} nodes",
            extra={"operation": "rollback", "group_id": group_id},
        )

        succeeded_hosts = {result.host for result in succeeded_results}
        clients_to_rollback = [
            client for client in self.node_clients if client.host in succeeded_hosts
        ]

        rollback_tasks = [
            client.delete_group(group_id) for client in clients_to_rollback
        ]
        rollback_results = await asyncio.gather(*rollback_tasks, return_exceptions=False)

        return rollback_results

    async def delete_group(self, group_id: str) -> ClusterOperationResult:
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        try:
            logger.info(
                f"Starting delete operation for group '{group_id}' across {len(self.node_clients)} nodes",
                extra={"operation": "delete", "group_id": group_id},
            )

            delete_tasks = [
                client.delete_group(group_id) for client in self.node_clients
            ]
            node_results = await asyncio.gather(*delete_tasks, return_exceptions=False)

            failed_nodes = [result for result in node_results if not result.success]
            all_succeeded = len(failed_nodes) == 0

            if all_succeeded:
                logger.info(
                    f"Delete operation succeeded on all {len(node_results)} nodes",
                    extra={"operation": "delete", "group_id": group_id},
                )
            else:
                logger.warning(
                    f"Delete operation failed on {len(failed_nodes)} of {len(node_results)} nodes",
                    extra={"operation": "delete", "group_id": group_id},
                )

            return ClusterOperationResult(
                operation="delete",
                group_id=group_id,
                success=all_succeeded,
                node_results=node_results,
                rolled_back=False,
            )

        finally:
            clear_correlation_id()

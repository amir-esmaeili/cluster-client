from cluster_client.models import NodeResult


class ClusterClientError(Exception):
    pass


class RollbackIncompleteError(ClusterClientError):
    def __init__(
        self,
        group_id: str,
        orphaned_nodes: list[str],
        node_results: list[NodeResult],
        rollback_results: list[NodeResult],
    ) -> None:
        self.group_id = group_id
        self.orphaned_nodes = orphaned_nodes
        self.node_results = node_results
        self.rollback_results = rollback_results

        orphaned_list = ", ".join(orphaned_nodes)
        super().__init__(
            f"Rollback incomplete for group '{group_id}'. "
            f"Orphaned nodes: {orphaned_list}. "
            f"Manual cleanup required."
        )

from dataclasses import dataclass
from typing import Literal


@dataclass
class NodeResult:
    host: str
    success: bool
    status_code: int | None
    error: str | None
    attempts: int


@dataclass
class ClusterOperationResult:
    operation: Literal["create", "delete"]
    group_id: str
    success: bool
    node_results: list[NodeResult]
    rolled_back: bool = False
    rollback_results: list[NodeResult] | None = None

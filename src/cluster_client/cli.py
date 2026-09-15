import argparse
import asyncio
import logging
import sys

from cluster_client.cluster_client import ClusterClient
from cluster_client.config import Config
from cluster_client.errors import RollbackIncompleteError
from cluster_client.logging_config import setup_logging

logger = logging.getLogger(__name__)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cluster client for distributed group management"
    )
    parser.add_argument(
        "operation",
        choices=["create", "delete"],
        help="Operation to perform",
    )
    parser.add_argument(
        "--group-id",
        required=True,
        help="Group ID to operate on",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    setup_logging(args.log_level)

    try:
        config = Config.from_env()

        async with ClusterClient(config) as client:
            if args.operation == "create":
                result = await client.create_group(args.group_id)
            else:
                result = await client.delete_group(args.group_id)

            print(f"\nOperation: {result.operation}")
            print(f"Group ID: {result.group_id}")
            print(f"Success: {result.success}")
            print(f"\nNode results:")
            for node_result in result.node_results:
                status = "OK" if node_result.success else "FAIL"
                print(
                    f"  [{status}] {node_result.host}: "
                    f"status={node_result.status_code}, "
                    f"attempts={node_result.attempts}"
                )
                if node_result.error:
                    print(f"      Error: {node_result.error}")

            if result.rolled_back and result.rollback_results:
                print(f"\nRollback performed:")
                for rollback_result in result.rollback_results:
                    status = "OK" if rollback_result.success else "FAIL"
                    print(
                        f"  [{status}] {rollback_result.host}: "
                        f"status={rollback_result.status_code}"
                    )

            return 0 if result.success else 1

    except RollbackIncompleteError as e:
        print(f"\nCRITICAL: {e}", file=sys.stderr)
        print(f"\nOrphaned nodes requiring manual cleanup:", file=sys.stderr)
        for host in e.orphaned_nodes:
            print(f"  - {host}", file=sys.stderr)
        return 2

    except ValueError as e:
        print(f"\nConfiguration error: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        return 1


def cli_main() -> None:
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    cli_main()

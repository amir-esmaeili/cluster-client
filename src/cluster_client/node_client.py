import logging

import httpx
from tenacity import RetryError

from cluster_client.config import Config
from cluster_client.http_client import HTTPClient
from cluster_client.models import NodeResult

logger = logging.getLogger(__name__)


class NodeClient:
    def __init__(self, host: str, http_client: HTTPClient, config: Config) -> None:
        self.host = host
        self.http_client = http_client
        self.config = config

    async def create_group(self, group_id: str) -> NodeResult:
        url = f"http://{self.host}/v1/group/"
        payload = {"groupId": group_id}

        try:
            response, attempts = await self.http_client.request_with_retry(
                "POST", url, self.host, json=payload
            )

            logger.info(
                f"Successfully created group on {self.host}",
                extra={"host": self.host, "group_id": group_id},
            )

            return NodeResult(
                host=self.host,
                success=True,
                status_code=response.status_code,
                error=None,
                attempts=attempts,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                if self.config.treat_create_conflict_as_success:
                    get_result = await self.get_group(group_id)
                    if get_result.success:
                        logger.info(
                            f"Group already exists on {self.host}, treating as success",
                            extra={"host": self.host, "group_id": group_id},
                        )
                        return NodeResult(
                            host=self.host,
                            success=True,
                            status_code=e.response.status_code,
                            error="Group already exists (verified with GET)",
                            attempts=1,
                        )
                    else:
                        logger.error(
                            f"Inconsistent state on {self.host}: "
                            f"create returned 400 but GET returned 404",
                            extra={"host": self.host, "group_id": group_id},
                        )
                        return NodeResult(
                            host=self.host,
                            success=False,
                            status_code=e.response.status_code,
                            error="Inconsistent state: 400 on create but 404 on GET",
                            attempts=1,
                        )

                logger.error(
                    f"Create failed on {self.host} with 400",
                    extra={"host": self.host, "group_id": group_id, "status_code": 400},
                )
                return NodeResult(
                    host=self.host,
                    success=False,
                    status_code=e.response.status_code,
                    error=f"HTTP {e.response.status_code}: {e.response.text}",
                    attempts=1,
                )

            logger.error(
                f"Create failed on {self.host}",
                extra={
                    "host": self.host,
                    "group_id": group_id,
                    "status_code": e.response.status_code,
                },
            )
            return NodeResult(
                host=self.host,
                success=False,
                status_code=e.response.status_code,
                error=f"HTTP {e.response.status_code}: {e.response.text}",
                attempts=1,
            )

        except RetryError as e:
            attempts = self.config.max_retry_attempts
            error_msg = f"Retries exhausted after {attempts} attempts"

            if e.last_attempt.exception():
                error_msg += f": {type(e.last_attempt.exception()).__name__}"

            logger.error(
                f"Create failed on {self.host} after retries",
                extra={"host": self.host, "group_id": group_id, "attempt": attempts},
            )

            return NodeResult(
                host=self.host,
                success=False,
                status_code=None,
                error=error_msg,
                attempts=attempts,
            )

        except Exception as e:
            logger.error(
                f"Unexpected error creating group on {self.host}: {e}",
                extra={"host": self.host, "group_id": group_id},
            )
            return NodeResult(
                host=self.host,
                success=False,
                status_code=None,
                error=f"Unexpected error: {type(e).__name__}: {e}",
                attempts=1,
            )

    async def delete_group(self, group_id: str) -> NodeResult:
        url = f"http://{self.host}/v1/group/"
        payload = {"groupId": group_id}

        try:
            response, attempts = await self.http_client.request_with_retry(
                "DELETE", url, self.host, json=payload
            )

            logger.info(
                f"Successfully deleted group from {self.host}",
                extra={"host": self.host, "group_id": group_id},
            )

            return NodeResult(
                host=self.host,
                success=True,
                status_code=response.status_code,
                error=None,
                attempts=attempts,
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Delete failed on {self.host}",
                extra={
                    "host": self.host,
                    "group_id": group_id,
                    "status_code": e.response.status_code,
                },
            )
            return NodeResult(
                host=self.host,
                success=False,
                status_code=e.response.status_code,
                error=f"HTTP {e.response.status_code}: {e.response.text}",
                attempts=1,
            )

        except RetryError as e:
            attempts = self.config.max_retry_attempts
            error_msg = f"Retries exhausted after {attempts} attempts"

            if e.last_attempt.exception():
                error_msg += f": {type(e.last_attempt.exception()).__name__}"

            logger.error(
                f"Delete failed on {self.host} after retries",
                extra={"host": self.host, "group_id": group_id, "attempt": attempts},
            )

            return NodeResult(
                host=self.host,
                success=False,
                status_code=None,
                error=error_msg,
                attempts=attempts,
            )

        except Exception as e:
            logger.error(
                f"Unexpected error deleting group from {self.host}: {e}",
                extra={"host": self.host, "group_id": group_id},
            )
            return NodeResult(
                host=self.host,
                success=False,
                status_code=None,
                error=f"Unexpected error: {type(e).__name__}: {e}",
                attempts=1,
            )

    async def get_group(self, group_id: str) -> NodeResult:
        url = f"http://{self.host}/v1/group/{group_id}/"

        try:
            response, attempts = await self.http_client.request_with_retry(
                "GET", url, self.host
            )

            logger.debug(
                f"Group exists on {self.host}",
                extra={"host": self.host, "group_id": group_id},
            )

            return NodeResult(
                host=self.host,
                success=True,
                status_code=response.status_code,
                error=None,
                attempts=attempts,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(
                    f"Group not found on {self.host}",
                    extra={"host": self.host, "group_id": group_id},
                )
            else:
                logger.error(
                    f"Get failed on {self.host}",
                    extra={
                        "host": self.host,
                        "group_id": group_id,
                        "status_code": e.response.status_code,
                    },
                )

            return NodeResult(
                host=self.host,
                success=False,
                status_code=e.response.status_code,
                error=f"HTTP {e.response.status_code}",
                attempts=1,
            )

        except RetryError as e:
            attempts = self.config.max_retry_attempts
            error_msg = f"Retries exhausted after {attempts} attempts"

            if e.last_attempt.exception():
                error_msg += f": {type(e.last_attempt.exception()).__name__}"

            logger.error(
                f"Get failed on {self.host} after retries",
                extra={"host": self.host, "group_id": group_id, "attempt": attempts},
            )

            return NodeResult(
                host=self.host,
                success=False,
                status_code=None,
                error=error_msg,
                attempts=attempts,
            )

        except Exception as e:
            logger.error(
                f"Unexpected error getting group from {self.host}: {e}",
                extra={"host": self.host, "group_id": group_id},
            )
            return NodeResult(
                host=self.host,
                success=False,
                status_code=None,
                error=f"Unexpected error: {type(e).__name__}: {e}",
                attempts=1,
            )

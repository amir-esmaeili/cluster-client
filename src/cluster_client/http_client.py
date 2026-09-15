import logging
import random
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from cluster_client.config import Config

logger = logging.getLogger(__name__)


def is_transient_error(exception: BaseException) -> bool:
    if isinstance(exception, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
        return True

    if isinstance(exception, httpx.HTTPStatusError):
        return 500 <= exception.response.status_code < 600

    return False


class HTTPClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=config.read_timeout,
                connect=config.connect_timeout,
            )
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "HTTPClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def request_with_retry(
        self,
        method: str,
        url: str,
        host: str,
        **kwargs: Any,
    ) -> tuple[httpx.Response, int]:
        attempts = 0

        async for attempt in AsyncRetrying(
            retry=retry_if_exception(is_transient_error),
            stop=stop_after_attempt(self.config.max_retry_attempts),
            wait=wait_exponential_jitter(
                initial=self.config.base_backoff_delay,
                max=60.0,
                jitter=random.random() * self.config.base_backoff_delay,
            ),
            reraise=True,
        ):
            with attempt:
                attempts = attempt.retry_state.attempt_number

                try:
                    response = await self._client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response, attempts

                except httpx.HTTPStatusError as e:
                    if 400 <= e.response.status_code < 500:
                        logger.debug(
                            f"Non-retryable error from {host}: {e.response.status_code}",
                            extra={"host": host, "status_code": e.response.status_code},
                        )
                        raise

                    logger.warning(
                        f"Transient error from {host} (attempt {attempts}): "
                        f"{e.response.status_code}",
                        extra={
                            "host": host,
                            "attempt": attempts,
                            "status_code": e.response.status_code,
                        },
                    )
                    raise

                except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                    logger.warning(
                        f"Network/timeout error on {host} (attempt {attempts}): {type(e).__name__}",
                        extra={"host": host, "attempt": attempts},
                    )
                    raise

        raise RuntimeError("Retry logic failed unexpectedly")

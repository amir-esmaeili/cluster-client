"""Tests for HTTP client retry logic."""

import httpx
import pytest
import respx

from cluster_client.config import Config
from cluster_client.http_client import HTTPClient


@pytest.mark.asyncio
async def test_retry_on_500_then_success(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test that the client retries on 500 and eventually succeeds."""
    url = "https://node1.example.com/test"

    # First two attempts return 500, third succeeds
    route = respx_mock.get(url).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(200, json={"status": "ok"}),
        ]
    )

    async with HTTPClient(config) as client:
        response, attempts = await client.request_with_retry("GET", url, "node1.example.com")

        assert response.status_code == 200
        assert attempts == 3
        assert route.call_count == 3


@pytest.mark.asyncio
async def test_no_retry_on_400(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test that 4xx errors are not retried."""
    url = "https://node1.example.com/test"

    route = respx_mock.post(url).mock(return_value=httpx.Response(400))

    async with HTTPClient(config) as client:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.request_with_retry("POST", url, "node1.example.com")

        assert exc_info.value.response.status_code == 400
        assert route.call_count == 1  # No retry


@pytest.mark.asyncio
async def test_retry_exhausted_on_persistent_500(
    config: Config, respx_mock: respx.MockRouter
) -> None:
    """Test that retries are exhausted after max attempts."""
    url = "https://node1.example.com/test"

    # Always return 500
    route = respx_mock.get(url).mock(return_value=httpx.Response(500))

    async with HTTPClient(config) as client:
        # Tenacity reraises the last exception, which is HTTPStatusError
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.request_with_retry("GET", url, "node1.example.com")

        assert exc_info.value.response.status_code == 500
        # Should have tried max_retry_attempts times
        assert route.call_count == config.max_retry_attempts


@pytest.mark.asyncio
async def test_retry_on_timeout(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test that timeouts are retried."""
    url = "https://node1.example.com/test"

    # First attempt times out, second succeeds
    route = respx_mock.get(url).mock(
        side_effect=[
            httpx.TimeoutException("Read timeout"),
            httpx.Response(200),
        ]
    )

    async with HTTPClient(config) as client:
        response, attempts = await client.request_with_retry("GET", url, "node1.example.com")

        assert response.status_code == 200
        assert attempts == 2
        assert route.call_count == 2


@pytest.mark.asyncio
async def test_retry_on_network_error(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test that network errors are retried."""
    url = "https://node1.example.com/test"

    # First attempt has network error, second succeeds
    route = respx_mock.get(url).mock(
        side_effect=[
            httpx.ConnectError("Connection failed"),
            httpx.Response(200),
        ]
    )

    async with HTTPClient(config) as client:
        response, attempts = await client.request_with_retry("GET", url, "node1.example.com")

        assert response.status_code == 200
        assert attempts == 2
        assert route.call_count == 2


@pytest.mark.asyncio
async def test_immediate_success(config: Config, respx_mock: respx.MockRouter) -> None:
    """Test that successful requests don't retry."""
    url = "https://node1.example.com/test"

    route = respx_mock.post(url).mock(return_value=httpx.Response(201))

    async with HTTPClient(config) as client:
        response, attempts = await client.request_with_retry("POST", url, "node1.example.com")

        assert response.status_code == 201
        assert attempts == 1
        assert route.call_count == 1

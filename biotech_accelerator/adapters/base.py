"""Base adapter with shared HTTP client, retry, and typed error contract."""

import asyncio
import logging
import random
from json import JSONDecodeError
from typing import Optional

import httpx
from httpx import ConnectError, HTTPStatusError, Response, TimeoutException

logger = logging.getLogger(__name__)


class AdapterError(Exception):
    """Base class for all adapter errors."""

    def __init__(self, url: str, message: str):
        self.url = url
        super().__init__(f"{message} ({url})")


class AdapterTimeout(AdapterError):
    """Request timed out or connection failed after exhausting retries."""


class AdapterNotFound(AdapterError):
    """HTTP 404 — the requested resource does not exist."""

    def __init__(self, url: str):
        super().__init__(url, "Not found")


class AdapterHTTPError(AdapterError):
    """Non-retryable HTTP error (4xx other than 404, or 5xx after retries)."""

    def __init__(self, url: str, status_code: int):
        self.status_code = status_code
        super().__init__(url, f"HTTP {status_code}")


class AdapterParseError(AdapterError):
    """Response body could not be parsed (invalid JSON / XML / etc.)."""


_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class BaseAdapter:
    """Base class for all API adapters with shared HTTP client + retry."""

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
    ):
        self._client = httpx.AsyncClient(timeout=timeout)
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    # No __del__ here on purpose. It used to schedule client.aclose() with
    # loop.create_task() and drop the returned task, so the task could be
    # garbage-collected before it ran — an unreliable cleanup that hid the fact
    # that callers should close explicitly. Every caller uses close() or the
    # async context manager below; that is the cleanup path.

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _before_request(self) -> None:
        """Hook for subclasses to apply rate limiting before each attempt."""
        return None

    async def _request(self, method: str, url: str, **kwargs) -> Response:
        """HTTP request with retry and typed error reporting.

        Retries on connect errors, timeouts, and transient status codes
        (429, 5xx). 404 raises AdapterNotFound immediately. Other non-2xx
        responses raise AdapterHTTPError without retry.
        """
        last_transient: Optional[Exception] = None
        last_status: Optional[int] = None

        for attempt in range(self._max_retries):
            await self._before_request()
            try:
                response = await self._client.request(method, url, **kwargs)
            except TimeoutException as e:
                last_transient = e
                logger.warning(f"Timeout on {url} (attempt {attempt + 1}/{self._max_retries})")
            except ConnectError as e:
                last_transient = e
                logger.warning(
                    f"Connect failed on {url} (attempt {attempt + 1}/{self._max_retries}): {e}"
                )
            else:
                if response.status_code == 404:
                    raise AdapterNotFound(url)
                if response.status_code in _RETRYABLE_STATUSES:
                    last_status = response.status_code
                    last_transient = HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    logger.warning(
                        f"HTTP {response.status_code} on {url} "
                        f"(attempt {attempt + 1}/{self._max_retries})"
                    )
                elif response.is_error:
                    raise AdapterHTTPError(url, response.status_code)
                else:
                    return response

            if attempt + 1 < self._max_retries:
                delay = self._backoff_base * (2**attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)

        # Exhausted retries.
        if last_status is not None:
            raise AdapterHTTPError(url, last_status)
        raise AdapterTimeout(url, str(last_transient) if last_transient else "Max retries exceeded")

    async def _request_json(self, method: str, url: str, **kwargs) -> dict:
        """HTTP request returning parsed JSON. Raises AdapterError on failure."""
        response = await self._request(method, url, **kwargs)
        try:
            return response.json()
        except (JSONDecodeError, ValueError) as e:
            raise AdapterParseError(url, f"Invalid JSON: {e}") from e

    async def _get_json(self, url: str, **kwargs) -> dict:
        return await self._request_json("GET", url, **kwargs)

    async def _post_json(self, url: str, **kwargs) -> dict:
        return await self._request_json("POST", url, **kwargs)

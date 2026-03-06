"""Retry utility for async HTTP operations."""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from httpx import ConnectError, HTTPStatusError, TimeoutException

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retryable exceptions
RETRYABLE_EXCEPTIONS = (TimeoutException, ConnectError)


async def with_retry(
    coro_func: Callable[[], Any],
    max_retries: int = 3,
    backoff_base: float = 1.0,
    retryable_exceptions: tuple = RETRYABLE_EXCEPTIONS,
    retryable_status_codes: tuple = (429, 500, 502, 503, 504),
) -> Any:
    """
    Execute an async function with retry logic.

    Args:
        coro_func: Async function to call (no arguments)
        max_retries: Maximum number of retry attempts
        backoff_base: Base delay for exponential backoff (seconds)
        retryable_exceptions: Tuple of exception types to retry
        retryable_status_codes: HTTP status codes that trigger retry

    Returns:
        Result of the coroutine function

    Raises:
        The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await coro_func()
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = backoff_base * (2**attempt)
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} after {e.__class__.__name__}. "
                    f"Waiting {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)
        except HTTPStatusError as e:
            if e.response.status_code in retryable_status_codes:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = backoff_base * (2**attempt)
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} after HTTP {e.response.status_code}. "
                        f"Waiting {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
            else:
                raise

    if last_exception:
        raise last_exception


def retry_async(
    max_retries: int = 3,
    backoff_base: float = 1.0,
    retryable_exceptions: tuple = RETRYABLE_EXCEPTIONS,
):
    """
    Decorator for async functions with retry logic.

    Usage:
        @retry_async(max_retries=3)
        async def fetch_data():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_retry(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                backoff_base=backoff_base,
                retryable_exceptions=retryable_exceptions,
            )

        return wrapper

    return decorator

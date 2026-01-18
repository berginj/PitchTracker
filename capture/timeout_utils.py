"""Timeout and retry utilities for camera operations."""

from __future__ import annotations

import functools
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Callable, Optional, TypeVar

from exceptions import CameraConnectionError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def run_with_timeout(
    func: Callable[..., T],
    timeout_seconds: float,
    error_message: str = "Operation timed out",
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run function with timeout, raise CameraConnectionError if exceeded.

    Uses ThreadPoolExecutor to ensure proper thread cleanup on timeout.
    Previous implementation used daemon threads which leaked resources.

    Args:
        func: Function to run
        timeout_seconds: Timeout in seconds
        error_message: Error message if timeout occurs
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        CameraConnectionError: If operation times out
        Exception: Any exception raised by func

    Note:
        Thread is properly cleaned up whether operation succeeds, fails, or times out.
    """
    # Use ThreadPoolExecutor for proper thread management
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Submit function to executor
        future = executor.submit(func, *args, **kwargs)

        try:
            # Wait for result with timeout
            result = future.result(timeout=timeout_seconds)
            return result

        except FutureTimeoutError:
            # Timeout occurred - log and raise
            logger.error(f"{error_message} after {timeout_seconds}s")
            raise CameraConnectionError(
                f"{error_message} after {timeout_seconds}s",
                camera_id="unknown",
            )

        except Exception as e:
            # Function raised exception - re-raise it
            raise

    # ThreadPoolExecutor automatically cleans up thread on context exit


def exponential_backoff(attempt: int, base_delay: float = 0.5, max_delay: float = 5.0) -> float:
    """Calculate exponential backoff delay.

    Args:
        attempt: Attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds
    """
    delay = base_delay * (2**attempt)
    return min(delay, max_delay)


class RetryPolicy:
    """Configurable retry policy for camera operations."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 5.0,
        retry_on: tuple[type[Exception], ...] = (CameraConnectionError,),
    ):
        """Initialize retry policy.

        Args:
            max_attempts: Maximum number of attempts (including first)
            base_delay: Base delay for exponential backoff
            max_delay: Maximum delay between retries
            retry_on: Tuple of exception types to retry on
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retry_on = retry_on

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if should retry after exception.

        Args:
            attempt: Current attempt number (0-indexed)
            exception: Exception that occurred

        Returns:
            True if should retry
        """
        if attempt + 1 >= self.max_attempts:
            return False

        return isinstance(exception, self.retry_on)

    def get_delay(self, attempt: int) -> float:
        """Get delay before next attempt.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        return exponential_backoff(attempt, self.base_delay, self.max_delay)


def retry_on_failure(
    policy: Optional[RetryPolicy] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry function on failure with exponential backoff.

    Args:
        policy: Retry policy to use (default: 3 attempts, 0.5s base delay)

    Returns:
        Decorated function

    Example:
        @retry_on_failure()
        def open_camera(serial: str) -> Camera:
            # ... may raise CameraConnectionError ...
            pass
    """
    if policy is None:
        policy = RetryPolicy()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(policy.max_attempts):
                try:
                    if attempt > 0:
                        logger.info(
                            f"Retrying {func.__name__} (attempt {attempt + 1}/{policy.max_attempts})"
                        )

                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"{func.__name__} failed on attempt {attempt + 1}/{policy.max_attempts}: {e}"
                    )

                    if not policy.should_retry(attempt, e):
                        raise

                    # Wait before retrying
                    delay = policy.get_delay(attempt)
                    logger.debug(f"Waiting {delay:.2f}s before retry")
                    time.sleep(delay)

            # All attempts exhausted
            logger.error(f"{func.__name__} failed after {policy.max_attempts} attempts")
            raise last_exception  # type: ignore

        return wrapper

    return decorator


__all__ = [
    "run_with_timeout",
    "exponential_backoff",
    "RetryPolicy",
    "retry_on_failure",
]

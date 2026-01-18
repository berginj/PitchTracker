"""Tests for camera timeout and retry utilities.

Validates that timeout protection and retry logic work correctly
to prevent camera operations from hanging or failing unnecessarily.
"""

from __future__ import annotations

import time
from unittest.mock import Mock, patch

import pytest

from capture.timeout_utils import (
    RetryPolicy,
    exponential_backoff,
    retry_on_failure,
    run_with_timeout,
)
from exceptions import CameraConnectionError


class TestRunWithTimeout:
    """Test timeout wrapper for camera operations."""

    def test_successful_operation_completes(self):
        """Fast successful operations should complete normally."""

        def quick_func():
            return "success"

        result = run_with_timeout(quick_func, timeout_seconds=1.0)
        assert result == "success"

    def test_slow_operation_times_out(self):
        """Operations exceeding timeout should raise CameraConnectionError."""

        def slow_func():
            time.sleep(2.0)
            return "never reached"

        with pytest.raises(CameraConnectionError, match="timed out"):
            run_with_timeout(slow_func, timeout_seconds=0.5)

    def test_exception_propagated(self):
        """Exceptions from wrapped function should propagate."""

        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_with_timeout(failing_func, timeout_seconds=1.0)

    def test_timeout_with_arguments(self):
        """Timeout wrapper should pass through args and kwargs."""

        def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = run_with_timeout(
            func_with_args, 1.0, "ignored", 1, 2, c=3
        )
        assert result == "1-2-3"

    def test_custom_error_message(self):
        """Custom error messages should appear in exception."""

        def slow_func():
            time.sleep(2.0)

        with pytest.raises(CameraConnectionError, match="Custom error"):
            run_with_timeout(
                slow_func,
                timeout_seconds=0.1,
                error_message="Custom error message",
            )


class TestExponentialBackoff:
    """Test exponential backoff delay calculation."""

    def test_first_attempt_uses_base_delay(self):
        """First retry (attempt 0) should use base delay."""
        delay = exponential_backoff(0, base_delay=0.5)
        assert delay == 0.5

    def test_second_attempt_doubles_delay(self):
        """Second retry (attempt 1) should double the delay."""
        delay = exponential_backoff(1, base_delay=0.5)
        assert delay == 1.0

    def test_delay_respects_max(self):
        """Delay should never exceed max_delay."""
        delay = exponential_backoff(10, base_delay=1.0, max_delay=5.0)
        assert delay == 5.0

    def test_exponential_growth(self):
        """Delay should grow exponentially: 0.5, 1.0, 2.0, 4.0, 8.0..."""
        delays = [exponential_backoff(i, base_delay=0.5, max_delay=10.0) for i in range(5)]
        expected = [0.5, 1.0, 2.0, 4.0, 8.0]
        assert delays == expected


class TestRetryPolicy:
    """Test retry policy configuration."""

    def test_default_policy(self):
        """Default policy should retry CameraConnectionError 3 times."""
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.base_delay == 0.5
        assert policy.max_delay == 5.0

    def test_should_retry_on_correct_exception(self):
        """Should retry on configured exception types."""
        policy = RetryPolicy(retry_on=(ValueError,))

        # Should retry ValueError
        assert policy.should_retry(0, ValueError("test"))

        # Should not retry other exceptions
        assert not policy.should_retry(0, TypeError("test"))

    def test_should_not_retry_after_max_attempts(self):
        """Should stop retrying after max attempts."""
        policy = RetryPolicy(max_attempts=3)

        # Should retry on attempts 0 and 1
        assert policy.should_retry(0, CameraConnectionError("test", "cam1"))
        assert policy.should_retry(1, CameraConnectionError("test", "cam1"))

        # Should not retry on attempt 2 (would be 3rd total attempt)
        assert not policy.should_retry(2, CameraConnectionError("test", "cam1"))

    def test_get_delay_calculates_backoff(self):
        """get_delay should use exponential backoff."""
        policy = RetryPolicy(base_delay=1.0, max_delay=10.0)

        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0


class TestRetryOnFailure:
    """Test retry decorator for camera operations."""

    def test_successful_first_attempt(self):
        """Successful operations should not retry."""
        mock_func = Mock(return_value="success")

        @retry_on_failure()
        def test_func():
            return mock_func()

        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 1

    def test_retries_on_failure(self):
        """Should retry on configured exception types."""
        mock_func = Mock(side_effect=[
            CameraConnectionError("fail1", "cam1"),
            CameraConnectionError("fail2", "cam1"),
            "success"
        ])

        @retry_on_failure()
        def test_func():
            return mock_func()

        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3

    def test_exhausts_retries(self):
        """Should raise exception after max retries."""
        policy = RetryPolicy(max_attempts=3)
        mock_func = Mock(side_effect=CameraConnectionError("persistent", "cam1"))

        @retry_on_failure(policy=policy)
        def test_func():
            return mock_func()

        with pytest.raises(CameraConnectionError, match="persistent"):
            test_func()

        assert mock_func.call_count == 3

    def test_does_not_retry_wrong_exception(self):
        """Should not retry on non-configured exceptions."""
        policy = RetryPolicy(retry_on=(CameraConnectionError,))
        mock_func = Mock(side_effect=ValueError("wrong type"))

        @retry_on_failure(policy=policy)
        def test_func():
            return mock_func()

        with pytest.raises(ValueError, match="wrong type"):
            test_func()

        assert mock_func.call_count == 1

    def test_preserves_function_metadata(self):
        """Decorator should preserve function name and docstring."""

        @retry_on_failure()
        def my_func():
            """My docstring."""
            pass

        assert my_func.__name__ == "my_func"
        assert "My docstring" in my_func.__doc__

    def test_custom_retry_policy(self):
        """Should use custom retry policy when provided."""
        policy = RetryPolicy(max_attempts=5, base_delay=0.1, max_delay=1.0)
        attempt_count = {"count": 0}

        @retry_on_failure(policy=policy)
        def test_func():
            attempt_count["count"] += 1
            if attempt_count["count"] < 4:
                raise CameraConnectionError("retry", "cam1")
            return "success"

        result = test_func()
        assert result == "success"
        assert attempt_count["count"] == 4


class TestTimeoutRetryIntegration:
    """Test timeout and retry working together."""

    def test_timeout_within_retry(self):
        """Timeout can trigger retry if exception matches policy."""
        attempt_count = {"count": 0}

        def slow_then_fast():
            attempt_count["count"] += 1
            if attempt_count["count"] == 1:
                time.sleep(2.0)  # Will timeout
            return "success"

        @retry_on_failure(policy=RetryPolicy(retry_on=(CameraConnectionError,)))
        def test_func():
            return run_with_timeout(slow_then_fast, timeout_seconds=0.5)

        # First attempt times out (raises CameraConnectionError)
        # Retry succeeds
        result = test_func()
        assert result == "success"
        assert attempt_count["count"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

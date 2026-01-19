"""Unit tests for timeout thread cleanup (Phase 1 Fix #4)."""

import threading
import time
import unittest
from unittest.mock import patch

from capture.timeout_utils import run_with_timeout
from exceptions import CameraConnectionError


class TestTimeoutCleanup(unittest.TestCase):
    """Test timeout thread cleanup improvements."""

    def test_successful_operation_returns_result(self):
        """Test that successful operation returns result normally."""

        def fast_operation(x, y):
            return x + y

        result = run_with_timeout(fast_operation, 1.0, "Test", 5, 3)
        self.assertEqual(result, 8)

    def test_timeout_raises_camera_connection_error(self):
        """Test that timeout raises CameraConnectionError."""

        def slow_operation():
            time.sleep(5.0)
            return "Should not reach here"

        with self.assertRaises(CameraConnectionError) as context:
            run_with_timeout(slow_operation, 0.5, "Slow operation timed out")

        self.assertIn("Slow operation timed out", str(context.exception))
        self.assertIn("0.5s", str(context.exception))

    def test_exception_in_operation_propagated(self):
        """Test that exceptions from operation are propagated."""

        def failing_operation():
            raise ValueError("Operation failed")

        with self.assertRaises(ValueError) as context:
            run_with_timeout(failing_operation, 1.0, "Test")

        self.assertEqual(str(context.exception), "Operation failed")

    def test_no_thread_leak_on_success(self):
        """Test that no threads leak when operation succeeds."""

        initial_thread_count = threading.active_count()

        def fast_operation():
            return "success"

        # Run multiple times
        for _ in range(10):
            result = run_with_timeout(fast_operation, 1.0, "Test")
            self.assertEqual(result, "success")

        # Give threads time to clean up
        time.sleep(0.5)

        # Thread count should return to initial (or very close)
        final_thread_count = threading.active_count()
        self.assertLessEqual(final_thread_count, initial_thread_count + 1)

    def test_no_thread_leak_on_timeout(self):
        """Test that no threads leak even when timeout occurs."""

        initial_thread_count = threading.active_count()

        def slow_operation():
            time.sleep(10.0)  # Will timeout

        # Run multiple timeout operations
        for _ in range(5):
            try:
                run_with_timeout(slow_operation, 0.1, "Test")
            except CameraConnectionError:
                pass  # Expected

        # Give threads time to clean up
        time.sleep(0.5)

        # Thread count should NOT accumulate
        # Old implementation would have +5 ghost threads here
        final_thread_count = threading.active_count()
        self.assertLessEqual(final_thread_count, initial_thread_count + 2)

    def test_no_thread_leak_on_exception(self):
        """Test that no threads leak when operation raises exception."""

        initial_thread_count = threading.active_count()

        def failing_operation():
            raise RuntimeError("Test error")

        # Run multiple failing operations
        for _ in range(10):
            try:
                run_with_timeout(failing_operation, 1.0, "Test")
            except RuntimeError:
                pass  # Expected

        # Give threads time to clean up
        time.sleep(0.5)

        # Thread count should return to initial
        final_thread_count = threading.active_count()
        self.assertLessEqual(final_thread_count, initial_thread_count + 1)

    def test_operation_with_kwargs(self):
        """Test that operation with kwargs works correctly."""

        def operation_with_kwargs(a, b=10, c=20):
            return a + b + c

        result = run_with_timeout(operation_with_kwargs, 1.0, "Test", 5, b=15, c=25)
        self.assertEqual(result, 45)

    def test_timeout_message_includes_duration(self):
        """Test that timeout error message includes duration."""

        def slow_operation():
            time.sleep(10.0)

        with self.assertRaises(CameraConnectionError) as context:
            run_with_timeout(slow_operation, 0.3, "Camera open")

        error_msg = str(context.exception)
        self.assertIn("Camera open", error_msg)
        self.assertIn("0.3s", error_msg)

    def test_very_fast_operation(self):
        """Test that very fast operations work correctly."""

        def instant_operation():
            return 42

        result = run_with_timeout(instant_operation, 0.01, "Test")
        self.assertEqual(result, 42)

    def test_operation_with_none_return(self):
        """Test that operation returning None works correctly."""

        def operation_returns_none():
            return None

        result = run_with_timeout(operation_returns_none, 1.0, "Test")
        self.assertIsNone(result)

    def test_concurrent_timeout_operations(self):
        """Test that multiple concurrent timeout operations work correctly."""

        results = []
        errors = []

        def run_operation(index):
            try:
                if index % 2 == 0:
                    # Even indices succeed
                    result = run_with_timeout(lambda: f"result-{index}", 1.0, "Test")
                    results.append(result)
                else:
                    # Odd indices timeout
                    run_with_timeout(lambda: time.sleep(5.0), 0.1, "Test")
            except CameraConnectionError:
                errors.append(index)

        # Run 10 operations concurrently
        threads = []
        for i in range(10):
            t = threading.Thread(target=run_operation, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # Check results
        self.assertEqual(len(results), 5)  # Even indices
        self.assertEqual(len(errors), 5)   # Odd indices

    @patch('capture.timeout_utils.logger')
    def test_timeout_logs_error(self, mock_logger):
        """Test that timeout is logged."""

        def slow_operation():
            time.sleep(10.0)

        try:
            run_with_timeout(slow_operation, 0.1, "Test operation")
        except CameraConnectionError:
            pass

        # Should have logged error
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args[0][0]
        self.assertIn("Test operation", call_args)
        self.assertIn("0.1s", call_args)

    def test_repeated_timeout_operations_stable(self):
        """Test that repeated timeout operations remain stable (no accumulation)."""

        initial_thread_count = threading.active_count()

        def slow_operation():
            time.sleep(10.0)

        # Run many timeout operations
        for i in range(20):
            try:
                run_with_timeout(slow_operation, 0.05, "Test")
            except CameraConnectionError:
                pass

            # Check thread count periodically
            if i % 5 == 0:
                current_count = threading.active_count()
                # Thread count should not grow linearly
                self.assertLess(current_count, initial_thread_count + 5)

        # Final thread count should be close to initial
        time.sleep(0.5)
        final_count = threading.active_count()
        self.assertLess(final_count, initial_thread_count + 3)


class TestTimeoutVsOldImplementation(unittest.TestCase):
    """Compare new implementation against old daemon thread approach."""

    def test_thread_cleanup_comparison(self):
        """Demonstrate that new implementation cleans up threads properly.

        This test documents the improvement over the old daemon thread approach.
        """

        def slow_operation():
            time.sleep(10.0)

        initial_count = threading.active_count()

        # New implementation (using ThreadPoolExecutor)
        for _ in range(10):
            try:
                run_with_timeout(slow_operation, 0.1, "Test")
            except CameraConnectionError:
                pass

        time.sleep(0.5)
        final_count = threading.active_count()

        # Thread count should NOT grow by 10
        # Old daemon thread approach would have +10 ghost threads here
        thread_growth = final_count - initial_count
        self.assertLess(thread_growth, 3,
                        msg=f"Thread count grew by {thread_growth}, expected <3. "
                            f"Old implementation would have grown by 10.")


if __name__ == '__main__':
    unittest.main()

"""Unit tests for cleanup manager (Phase 3 Fix #10-11)."""

import threading
import time
import unittest
from unittest.mock import Mock

from app.lifecycle import CleanupManager, CleanupTask, SessionCleanupVerifier, get_cleanup_manager


class TestCleanupTask(unittest.TestCase):
    """Test CleanupTask dataclass."""

    def test_cleanup_task_creation(self):
        """Test creating CleanupTask."""
        callback = Mock()
        task = CleanupTask(
            name="test_task",
            callback=callback,
            timeout=10.0,
            critical=True,
        )

        self.assertEqual(task.name, "test_task")
        self.assertEqual(task.callback, callback)
        self.assertEqual(task.timeout, 10.0)
        self.assertTrue(task.critical)

    def test_cleanup_task_defaults(self):
        """Test CleanupTask default values."""
        callback = Mock()
        task = CleanupTask(name="test", callback=callback)

        self.assertEqual(task.timeout, 5.0)
        self.assertFalse(task.critical)


class TestCleanupManager(unittest.TestCase):
    """Test CleanupManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = CleanupManager(default_timeout=2.0)

    def test_register_cleanup_task(self):
        """Test registering cleanup task."""
        callback = Mock()
        self.manager.register_cleanup("test_task", callback)

        # Task should be registered (can't inspect directly, but cleanup will call it)
        self.assertTrue(True)  # Registration doesn't raise

    def test_cleanup_calls_registered_tasks(self):
        """Test that cleanup calls all registered tasks."""
        callback1 = Mock()
        callback2 = Mock()

        self.manager.register_cleanup("task1", callback1)
        self.manager.register_cleanup("task2", callback2)

        success = self.manager.cleanup()

        self.assertTrue(success)
        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_unregister_cleanup_task(self):
        """Test unregistering cleanup task."""
        callback = Mock()

        self.manager.register_cleanup("test_task", callback)
        removed = self.manager.unregister_cleanup("test_task")

        self.assertTrue(removed)

        # Task should not be called during cleanup
        self.manager.cleanup()
        callback.assert_not_called()

    def test_unregister_nonexistent_task(self):
        """Test unregistering task that doesn't exist."""
        removed = self.manager.unregister_cleanup("nonexistent")
        self.assertFalse(removed)

    def test_cleanup_task_timeout(self):
        """Test that slow tasks are timed out."""

        def slow_task():
            time.sleep(10.0)  # Will timeout

        self.manager.register_cleanup("slow_task", slow_task, timeout=0.5)

        start = time.time()
        success = self.manager.cleanup()
        elapsed = time.time() - start

        # Should timeout quickly (not wait full 10s)
        self.assertLess(elapsed, 2.0)
        self.assertTrue(success)  # Non-critical task timeout doesn't fail cleanup

    def test_critical_task_failure_reported(self):
        """Test that critical task failure is reported."""

        def failing_task():
            raise RuntimeError("Task failed")

        self.manager.register_cleanup("critical_task", failing_task, critical=True)

        success = self.manager.cleanup()
        self.assertFalse(success)  # Critical task failed

    def test_non_critical_task_failure_continues(self):
        """Test that non-critical task failure doesn't stop cleanup."""

        def failing_task():
            raise RuntimeError("Task failed")

        successful_task = Mock()

        self.manager.register_cleanup("failing_task", failing_task, critical=False)
        self.manager.register_cleanup("success_task", successful_task)

        success = self.manager.cleanup()

        # Should continue despite failure
        self.assertTrue(success)
        successful_task.assert_called_once()

    def test_verify_cleanup(self):
        """Test cleanup verification."""
        verification = self.manager.verify_cleanup()

        self.assertIn("threads_remaining", verification)
        self.assertIn("cleanup_registered", verification)
        self.assertIsInstance(verification["threads_remaining"], int)

    def test_cleanup_in_progress_blocks(self):
        """Test that cleanup in progress blocks second cleanup."""

        def slow_task():
            time.sleep(1.0)

        self.manager.register_cleanup("slow", slow_task)

        # Start cleanup in thread
        cleanup_thread = threading.Thread(target=self.manager.cleanup)
        cleanup_thread.start()

        time.sleep(0.1)  # Let it start

        # Try to cleanup again
        success = self.manager.cleanup()
        self.assertFalse(success)  # Should fail because already in progress

        cleanup_thread.join()

    def test_task_execution_order(self):
        """Test that tasks execute in registration order."""
        order = []

        def task1():
            order.append(1)

        def task2():
            order.append(2)

        def task3():
            order.append(3)

        self.manager.register_cleanup("task1", task1)
        self.manager.register_cleanup("task2", task2)
        self.manager.register_cleanup("task3", task3)

        self.manager.cleanup()

        self.assertEqual(order, [1, 2, 3])


class TestSessionCleanupVerifier(unittest.TestCase):
    """Test SessionCleanupVerifier functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.verifier = SessionCleanupVerifier()

    def test_register_expected_file(self):
        """Test registering expected file."""
        self.verifier.register_expected_file("/path/to/file.txt")
        # Should not raise

    def test_register_handle_to_close(self):
        """Test registering handle to close."""
        self.verifier.register_handle_to_close("test_handle")
        # Should not raise

    def test_verify_missing_file_fails(self):
        """Test that missing file causes verification failure."""
        self.verifier.register_expected_file("/nonexistent/file.txt")

        success, issues = self.verifier.verify_session_cleanup()

        self.assertFalse(success)
        self.assertGreater(len(issues), 0)
        self.assertTrue(any("missing" in i.lower() for i in issues))

    def test_verify_empty_file_fails(self):
        """Test that empty file causes verification failure."""
        import tempfile

        # Create empty file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filepath = f.name

        try:
            self.verifier.register_expected_file(filepath)

            success, issues = self.verifier.verify_session_cleanup()

            self.assertFalse(success)
            self.assertGreater(len(issues), 0)
            self.assertTrue(any("empty" in i.lower() for i in issues))

        finally:
            # Clean up
            import os

            os.unlink(filepath)

    def test_verify_existing_file_succeeds(self):
        """Test that existing non-empty file passes verification."""
        import tempfile

        # Create file with content
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            filepath = f.name

        try:
            self.verifier.register_expected_file(filepath)

            success, issues = self.verifier.verify_session_cleanup()

            self.assertTrue(success)
            self.assertEqual(len(issues), 0)

        finally:
            # Clean up
            import os

            os.unlink(filepath)


class TestGlobalCleanupManager(unittest.TestCase):
    """Test global cleanup manager functions."""

    def test_get_cleanup_manager_singleton(self):
        """Test that get_cleanup_manager returns singleton."""
        manager1 = get_cleanup_manager()
        manager2 = get_cleanup_manager()
        self.assertIs(manager1, manager2)


if __name__ == "__main__":
    unittest.main()

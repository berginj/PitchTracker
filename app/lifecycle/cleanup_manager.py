"""Cleanup manager for graceful shutdown and resource cleanup."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CleanupTask:
    """Task to execute during cleanup."""

    name: str
    callback: Callable[[], None]
    timeout: float = 5.0
    critical: bool = False  # If True, failure blocks shutdown


class CleanupManager:
    """Manager for graceful shutdown and cleanup.

    Ensures all resources are properly cleaned up on shutdown with
    timeout handling and error reporting.
    """

    def __init__(self, default_timeout: float = 10.0):
        """Initialize cleanup manager.

        Args:
            default_timeout: Default timeout for cleanup operations
        """
        self._tasks: List[CleanupTask] = []
        self._default_timeout = default_timeout
        self._lock = threading.Lock()
        self._cleanup_in_progress = False

    def register_cleanup(
        self,
        name: str,
        callback: Callable[[], None],
        timeout: Optional[float] = None,
        critical: bool = False,
    ) -> None:
        """Register cleanup task.

        Args:
            name: Task name
            callback: Cleanup callback function
            timeout: Timeout for this task (uses default if None)
            critical: Whether task is critical (blocks shutdown on failure)
        """
        with self._lock:
            task = CleanupTask(
                name=name,
                callback=callback,
                timeout=timeout or self._default_timeout,
                critical=critical,
            )
            self._tasks.append(task)
            logger.debug(f"Registered cleanup task: {name}")

    def unregister_cleanup(self, name: str) -> bool:
        """Unregister cleanup task.

        Args:
            name: Task name

        Returns:
            True if task was found and removed
        """
        with self._lock:
            for i, task in enumerate(self._tasks):
                if task.name == name:
                    self._tasks.pop(i)
                    logger.debug(f"Unregistered cleanup task: {name}")
                    return True
        return False

    def cleanup(self) -> bool:
        """Execute all cleanup tasks.

        Returns:
            True if all critical tasks succeeded
        """
        if self._cleanup_in_progress:
            logger.warning("Cleanup already in progress")
            return False

        self._cleanup_in_progress = True
        logger.info("Starting cleanup...")

        # Get tasks (copy to avoid holding lock)
        with self._lock:
            tasks = self._tasks.copy()

        all_critical_succeeded = True
        start_time = time.time()

        # Execute tasks
        for task in tasks:
            task_start = time.time()
            logger.info(f"Executing cleanup task: {task.name}")

            try:
                # Run task in thread with timeout
                success = self._run_with_timeout(task.callback, task.timeout)

                if success:
                    elapsed = time.time() - task_start
                    logger.info(f"Cleanup task '{task.name}' completed in {elapsed:.2f}s")
                else:
                    logger.error(f"Cleanup task '{task.name}' timed out after {task.timeout}s")
                    if task.critical:
                        all_critical_succeeded = False

            except Exception as e:
                logger.error(f"Cleanup task '{task.name}' failed: {e}", exc_info=True)
                if task.critical:
                    all_critical_succeeded = False

        total_elapsed = time.time() - start_time
        logger.info(f"Cleanup completed in {total_elapsed:.2f}s")

        self._cleanup_in_progress = False
        return all_critical_succeeded

    def _run_with_timeout(self, callback: Callable[[], None], timeout: float) -> bool:
        """Run callback with timeout.

        Args:
            callback: Function to run
            timeout: Timeout in seconds

        Returns:
            True if completed before timeout
        """
        result = {"completed": False, "exception": None}

        def wrapper():
            try:
                callback()
                result["completed"] = True
            except Exception as e:
                result["exception"] = e

        thread = threading.Thread(target=wrapper)
        thread.daemon = False
        thread.start()
        thread.join(timeout=timeout)

        if result["exception"]:
            raise result["exception"]

        return result["completed"]

    def verify_cleanup(self) -> dict:
        """Verify cleanup was successful.

        Returns:
            Dictionary with cleanup verification results
        """
        verification = {
            "threads_remaining": threading.active_count(),
            "cleanup_registered": len(self._tasks),
        }

        # Add warnings if issues detected
        if verification["threads_remaining"] > 2:  # Main + monitor thread is acceptable
            logger.warning(
                f"Cleanup verification: {verification['threads_remaining']} threads still active"
            )

        return verification


class SessionCleanupVerifier:
    """Verifies that session resources are properly cleaned up."""

    def __init__(self):
        """Initialize session cleanup verifier."""
        self._expected_files: List[str] = []
        self._expected_closed_handles: List[str] = []

    def register_expected_file(self, filepath: str) -> None:
        """Register file that should exist after session.

        Args:
            filepath: File path to verify
        """
        self._expected_files.append(filepath)

    def register_handle_to_close(self, handle_name: str) -> None:
        """Register handle that should be closed.

        Args:
            handle_name: Handle name to track
        """
        self._expected_closed_handles.append(handle_name)

    def verify_session_cleanup(self) -> tuple[bool, List[str]]:
        """Verify session cleanup.

        Returns:
            Tuple of (success, list_of_issues)
        """
        issues = []

        # Check files exist
        from pathlib import Path

        for filepath in self._expected_files:
            path = Path(filepath)
            if not path.exists():
                issues.append(f"Expected file missing: {filepath}")
            elif path.stat().st_size == 0:
                issues.append(f"Expected file is empty: {filepath}")

        # Log results
        if issues:
            logger.error(f"Session cleanup verification failed: {len(issues)} issues found")
            for issue in issues:
                logger.error(f"  - {issue}")
            return False, issues
        else:
            logger.info("Session cleanup verification passed")
            return True, []


# Global cleanup manager instance
_cleanup_manager: Optional[CleanupManager] = None
_manager_lock = threading.Lock()


def get_cleanup_manager() -> CleanupManager:
    """Get global cleanup manager instance.

    Returns:
        Global cleanup manager
    """
    global _cleanup_manager
    if _cleanup_manager is None:
        with _manager_lock:
            if _cleanup_manager is None:
                _cleanup_manager = CleanupManager()
                logger.debug("Created global cleanup manager")
    return _cleanup_manager


__all__ = [
    "CleanupTask",
    "CleanupManager",
    "SessionCleanupVerifier",
    "get_cleanup_manager",
]

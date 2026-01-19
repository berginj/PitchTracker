"""Error recovery strategies for handling system failures gracefully."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

from app.events.error_bus import ErrorCategory, ErrorEvent, ErrorSeverity, get_error_bus

logger = logging.getLogger(__name__)


class RecoveryAction(Enum):
    """Recovery actions that can be taken for errors."""

    IGNORE = "ignore"  # Log and ignore
    RETRY = "retry"  # Retry the operation
    RESTART_COMPONENT = "restart_component"  # Restart the failing component
    STOP_SESSION = "stop_session"  # Stop current recording session
    SHUTDOWN = "shutdown"  # Graceful application shutdown


@dataclass
class RecoveryStrategy:
    """Strategy for recovering from specific error types."""

    category: ErrorCategory
    severity: ErrorSeverity
    action: RecoveryAction
    max_retries: int = 3
    retry_delay: float = 1.0
    handler: Optional[Callable[[ErrorEvent], bool]] = None


class ErrorRecoveryManager:
    """Manager for error recovery strategies.

    Subscribes to error events and attempts automatic recovery based on
    configured strategies.
    """

    def __init__(self):
        """Initialize error recovery manager."""
        self._strategies: List[RecoveryStrategy] = []
        self._recovery_handlers: Dict[str, Callable[[ErrorEvent], bool]] = {}
        self._lock = threading.Lock()
        self._subscribed = False

        # Setup default strategies
        self._setup_default_strategies()

    def _setup_default_strategies(self) -> None:
        """Setup default recovery strategies."""

        # Detection errors: log and continue
        self.add_strategy(
            RecoveryStrategy(
                category=ErrorCategory.DETECTION,
                severity=ErrorSeverity.ERROR,
                action=RecoveryAction.IGNORE,
            )
        )

        # Critical detection errors: notify but continue
        self.add_strategy(
            RecoveryStrategy(
                category=ErrorCategory.DETECTION,
                severity=ErrorSeverity.CRITICAL,
                action=RecoveryAction.IGNORE,
            )
        )

        # Critical disk space: stop session
        self.add_strategy(
            RecoveryStrategy(
                category=ErrorCategory.DISK_SPACE,
                severity=ErrorSeverity.CRITICAL,
                action=RecoveryAction.STOP_SESSION,
            )
        )

        # Disk space warnings: just notify
        self.add_strategy(
            RecoveryStrategy(
                category=ErrorCategory.DISK_SPACE,
                severity=ErrorSeverity.WARNING,
                action=RecoveryAction.IGNORE,
            )
        )

        # Critical recording errors: stop session
        self.add_strategy(
            RecoveryStrategy(
                category=ErrorCategory.RECORDING,
                severity=ErrorSeverity.CRITICAL,
                action=RecoveryAction.STOP_SESSION,
            )
        )

        # Camera errors: log and continue
        self.add_strategy(
            RecoveryStrategy(
                category=ErrorCategory.CAMERA,
                severity=ErrorSeverity.ERROR,
                action=RecoveryAction.IGNORE,
            )
        )

        logger.debug("Default recovery strategies configured")

    def add_strategy(self, strategy: RecoveryStrategy) -> None:
        """Add recovery strategy.

        Args:
            strategy: Recovery strategy to add
        """
        with self._lock:
            self._strategies.append(strategy)
        logger.debug(
            f"Added recovery strategy: {strategy.category.value}/{strategy.severity.value} -> {strategy.action.value}"
        )

    def register_handler(self, name: str, handler: Callable[[ErrorEvent], bool]) -> None:
        """Register recovery handler function.

        Args:
            name: Handler name
            handler: Handler function that takes ErrorEvent and returns True if recovery succeeded
        """
        with self._lock:
            self._recovery_handlers[name] = handler
        logger.debug(f"Registered recovery handler: {name}")

    def start(self) -> None:
        """Start error recovery manager (subscribe to error bus)."""
        if not self._subscribed:
            get_error_bus().subscribe(self._on_error_event)
            self._subscribed = True
            logger.info("Error recovery manager started")

    def stop(self) -> None:
        """Stop error recovery manager (unsubscribe from error bus)."""
        if self._subscribed:
            get_error_bus().unsubscribe(self._on_error_event)
            self._subscribed = False
            logger.info("Error recovery manager stopped")

    def _on_error_event(self, event: ErrorEvent) -> None:
        """Handle error event and attempt recovery.

        Args:
            event: Error event to handle
        """
        # Find matching strategy
        strategy = self._find_strategy(event)

        if strategy is None:
            # No strategy defined - just log
            logger.warning(f"No recovery strategy for {event.category.value}/{event.severity.value}")
            return

        # Execute recovery action
        try:
            self._execute_recovery(event, strategy)
        except Exception as e:
            logger.error(f"Error executing recovery for {event}: {e}", exc_info=True)

    def _find_strategy(self, event: ErrorEvent) -> Optional[RecoveryStrategy]:
        """Find matching recovery strategy for event.

        Args:
            event: Error event

        Returns:
            Matching strategy or None
        """
        with self._lock:
            for strategy in self._strategies:
                if strategy.category == event.category and strategy.severity == event.severity:
                    return strategy
        return None

    def _execute_recovery(self, event: ErrorEvent, strategy: RecoveryStrategy) -> None:
        """Execute recovery action.

        Args:
            event: Error event
            strategy: Recovery strategy
        """
        action = strategy.action

        if action == RecoveryAction.IGNORE:
            # Just log - error already logged by error bus
            logger.debug(f"Recovery action IGNORE for {event.category.value}/{event.severity.value}")

        elif action == RecoveryAction.RETRY:
            logger.info(f"Attempting recovery action RETRY for {event}")
            if strategy.handler:
                for attempt in range(strategy.max_retries):
                    try:
                        if strategy.handler(event):
                            logger.info(f"Recovery succeeded on attempt {attempt + 1}")
                            return
                    except Exception as e:
                        logger.warning(f"Recovery attempt {attempt + 1} failed: {e}")

                    if attempt < strategy.max_retries - 1:
                        time.sleep(strategy.retry_delay)

                logger.error(f"Recovery failed after {strategy.max_retries} attempts")

        elif action == RecoveryAction.RESTART_COMPONENT:
            logger.info(f"Attempting recovery action RESTART_COMPONENT for {event}")
            if strategy.handler:
                try:
                    strategy.handler(event)
                except Exception as e:
                    logger.error(f"Component restart failed: {e}")

        elif action == RecoveryAction.STOP_SESSION:
            logger.warning(f"Executing recovery action STOP_SESSION for {event}")
            # Call registered stop_session handler if available
            handler = self._recovery_handlers.get("stop_session")
            if handler:
                try:
                    handler(event)
                    logger.info("Session stopped successfully for recovery")
                except Exception as e:
                    logger.error(f"Failed to stop session: {e}")
            else:
                logger.warning("No stop_session handler registered")

        elif action == RecoveryAction.SHUTDOWN:
            logger.critical(f"Executing recovery action SHUTDOWN for {event}")
            # Call registered shutdown handler if available
            handler = self._recovery_handlers.get("shutdown")
            if handler:
                try:
                    handler(event)
                    logger.info("Application shutdown initiated for recovery")
                except Exception as e:
                    logger.error(f"Failed to shutdown application: {e}")
            else:
                logger.warning("No shutdown handler registered")


# Global error recovery manager instance
_recovery_manager: Optional[ErrorRecoveryManager] = None
_manager_lock = threading.Lock()


def get_recovery_manager() -> ErrorRecoveryManager:
    """Get global error recovery manager instance.

    Returns:
        Global error recovery manager
    """
    global _recovery_manager
    if _recovery_manager is None:
        with _manager_lock:
            if _recovery_manager is None:
                _recovery_manager = ErrorRecoveryManager()
                logger.debug("Created global error recovery manager")
    return _recovery_manager


__all__ = [
    "RecoveryAction",
    "RecoveryStrategy",
    "ErrorRecoveryManager",
    "get_recovery_manager",
]

"""Centralized error event bus for system-wide error handling.

This module provides a publish-subscribe error event system that allows
components to report errors and other components to react to them.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    INFO = "info"  # Informational, not really an error
    WARNING = "warning"  # Warning, operation continues
    ERROR = "error"  # Error occurred, operation may fail
    CRITICAL = "critical"  # Critical error, system may be unstable


class ErrorCategory(Enum):
    """Error categories for classification."""

    CAMERA = "camera"
    DETECTION = "detection"
    RECORDING = "recording"
    DISK_SPACE = "disk_space"
    NETWORK = "network"
    CALIBRATION = "calibration"
    TRACKING = "tracking"
    SYSTEM = "system"


@dataclass
class ErrorEvent:
    """Error event with context information."""

    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    source: str
    timestamp: float = field(default_factory=time.time)
    exception: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of error event."""
        exc_info = f" ({self.exception.__class__.__name__})" if self.exception else ""
        return f"[{self.severity.value.upper()}] {self.category.value}/{self.source}: {self.message}{exc_info}"


class ErrorEventBus:
    """Centralized error event bus for publish-subscribe error handling."""

    def __init__(self):
        """Initialize error event bus."""
        self._subscribers: Dict[ErrorCategory, List[Callable[[ErrorEvent], None]]] = {}
        self._all_subscribers: List[Callable[[ErrorEvent], None]] = []
        self._lock = threading.Lock()
        self._event_history: List[ErrorEvent] = []
        self._max_history = 100
        self._error_counts: Dict[ErrorCategory, int] = {}

    def subscribe(
        self, callback: Callable[[ErrorEvent], None], category: Optional[ErrorCategory] = None
    ) -> None:
        """Subscribe to error events.

        Args:
            callback: Function to call when error occurs
            category: Specific category to subscribe to, or None for all errors
        """
        with self._lock:
            if category is None:
                self._all_subscribers.append(callback)
                callback_name = getattr(callback, '__name__', repr(callback))
                logger.debug(f"Subscribed to all error events: {callback_name}")
            else:
                if category not in self._subscribers:
                    self._subscribers[category] = []
                self._subscribers[category].append(callback)
                callback_name = getattr(callback, '__name__', repr(callback))
                logger.debug(f"Subscribed to {category.value} errors: {callback_name}")

    def unsubscribe(
        self, callback: Callable[[ErrorEvent], None], category: Optional[ErrorCategory] = None
    ) -> None:
        """Unsubscribe from error events.

        Args:
            callback: Function to unsubscribe
            category: Category to unsubscribe from, or None for all
        """
        with self._lock:
            if category is None:
                if callback in self._all_subscribers:
                    self._all_subscribers.remove(callback)
                    callback_name = getattr(callback, '__name__', repr(callback))
                    logger.debug(f"Unsubscribed from all errors: {callback_name}")
            else:
                if category in self._subscribers and callback in self._subscribers[category]:
                    self._subscribers[category].remove(callback)
                    callback_name = getattr(callback, '__name__', repr(callback))
                    logger.debug(f"Unsubscribed from {category.value} errors: {callback_name}")

    def publish(self, event: ErrorEvent) -> None:
        """Publish error event to subscribers.

        Args:
            event: Error event to publish
        """
        # Add to history
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)

            # Update error counts
            self._error_counts[event.category] = self._error_counts.get(event.category, 0) + 1

            # Get subscribers
            category_subscribers = self._subscribers.get(event.category, []).copy()
            all_subscribers = self._all_subscribers.copy()

        # Log the event
        log_level = {
            ErrorSeverity.INFO: logging.INFO,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }[event.severity]

        logger.log(log_level, str(event), exc_info=event.exception)

        # Notify subscribers (outside lock to avoid deadlocks)
        for callback in category_subscribers + all_subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event subscriber {callback.__name__}: {e}", exc_info=True)

    def get_history(
        self, category: Optional[ErrorCategory] = None, limit: int = 100
    ) -> List[ErrorEvent]:
        """Get recent error history.

        Args:
            category: Filter by category, or None for all
            limit: Maximum number of events to return

        Returns:
            List of recent error events
        """
        with self._lock:
            history = self._event_history.copy()

        if category is not None:
            history = [e for e in history if e.category == category]

        return history[-limit:]

    def get_error_counts(self) -> Dict[ErrorCategory, int]:
        """Get error counts by category.

        Returns:
            Dictionary of error counts per category
        """
        with self._lock:
            return self._error_counts.copy()

    def clear_history(self) -> None:
        """Clear error history and counts."""
        with self._lock:
            self._event_history.clear()
            self._error_counts.clear()
        logger.debug("Error history cleared")


# Global error event bus instance
_error_bus: Optional[ErrorEventBus] = None
_bus_lock = threading.Lock()


def get_error_bus() -> ErrorEventBus:
    """Get global error event bus instance.

    Returns:
        Global error event bus
    """
    global _error_bus
    if _error_bus is None:
        with _bus_lock:
            if _error_bus is None:
                _error_bus = ErrorEventBus()
                logger.debug("Created global error event bus")
    return _error_bus


def publish_error(
    category: ErrorCategory,
    severity: ErrorSeverity,
    message: str,
    source: str,
    exception: Optional[Exception] = None,
    **metadata: Any,
) -> None:
    """Convenience function to publish error event.

    Args:
        category: Error category
        severity: Error severity
        message: Error message
        source: Source component
        exception: Optional exception
        **metadata: Additional metadata
    """
    event = ErrorEvent(
        category=category,
        severity=severity,
        message=message,
        source=source,
        exception=exception,
        metadata=metadata,
    )
    get_error_bus().publish(event)


__all__ = [
    "ErrorSeverity",
    "ErrorCategory",
    "ErrorEvent",
    "ErrorEventBus",
    "get_error_bus",
    "publish_error",
]

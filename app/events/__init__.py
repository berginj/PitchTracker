"""Event system for application-wide event handling."""

from app.events.error_bus import (
    ErrorCategory,
    ErrorEvent,
    ErrorEventBus,
    ErrorSeverity,
    get_error_bus,
    publish_error,
)

__all__ = [
    "ErrorCategory",
    "ErrorEvent",
    "ErrorEventBus",
    "ErrorSeverity",
    "get_error_bus",
    "publish_error",
]

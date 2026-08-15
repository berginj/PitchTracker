"""Event system for application-wide event handling."""

from app.events.error_bus import (
    ErrorCategory,
    ErrorEvent,
    ErrorEventBus,
    ErrorSeverity,
    get_error_bus,
    publish_error,
)
from app.events.event_metadata import EventMetadata, hydrate_metadata, make_event_metadata

__all__ = [
    "ErrorCategory",
    "ErrorEvent",
    "ErrorEventBus",
    "ErrorSeverity",
    "EventMetadata",
    "get_error_bus",
    "hydrate_metadata",
    "make_event_metadata",
    "publish_error",
]

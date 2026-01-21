"""Thread-safe EventBus for service communication.

The EventBus provides a publish-subscribe pattern for decoupled service communication.
Services publish typed events, and other services subscribe with type-safe handlers.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Type, TypeVar

from log_config.logger import get_logger
from app.events import ErrorCategory, ErrorSeverity, publish_error

logger = get_logger(__name__)

# Type variables for type-safe event handling
EventType = TypeVar('EventType')
EventHandler = Callable[[EventType], None]


class EventBus:
    """Thread-safe event bus for service communication.

    Features:
    - Type-safe publish/subscribe
    - Thread-safe for concurrent publishers/subscribers
    - Error isolation (handler errors don't crash bus)
    - Synchronous event delivery (handlers run on publisher's thread)

    Thread Safety:
        - subscribe() is thread-safe
        - unsubscribe() is thread-safe
        - publish() is thread-safe
        - Handlers are called synchronously on the publisher's thread

    Performance:
        - Low overhead (~0.1ms per event for 10 subscribers)
        - No queuing/buffering (handlers run immediately)
        - Handlers should be fast (< 5ms recommended)

    Example:
        ```python
        bus = EventBus()

        # Subscribe
        def handle_frame(event: FrameCapturedEvent):
            print(f"Frame from {event.camera_id}")

        bus.subscribe(FrameCapturedEvent, handle_frame)

        # Publish
        event = FrameCapturedEvent(camera_id="left", frame=frame, timestamp_ns=123)
        bus.publish(event)
        ```
    """

    def __init__(self):
        """Initialize event bus."""
        self._subscribers: Dict[Type, List[EventHandler]] = {}
        self._lock = threading.Lock()
        self._event_count: Dict[Type, int] = {}
        self._start_time = time.time()

        logger.info("EventBus initialized")

    def subscribe(self, event_type: Type[EventType], handler: EventHandler) -> None:
        """Register handler for event type.

        Args:
            event_type: The event class to subscribe to (e.g., FrameCapturedEvent)
            handler: Callback function that takes event as parameter

        Thread-Safe: Yes

        Example:
            ```python
            def handle_observation(event: ObservationDetectedEvent):
                print(f"Observation: {event.observation}")

            bus.subscribe(ObservationDetectedEvent, handle_observation)
            ```
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
                self._event_count[event_type] = 0

            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed handler to {event_type.__name__} "
                        f"({len(self._subscribers[event_type])} total subscribers)")

    def unsubscribe(self, event_type: Type[EventType], handler: EventHandler) -> bool:
        """Unregister handler for event type.

        Args:
            event_type: The event class to unsubscribe from
            handler: The callback function to remove

        Returns:
            True if handler was found and removed, False otherwise

        Thread-Safe: Yes
        """
        with self._lock:
            if event_type not in self._subscribers:
                return False

            try:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Unsubscribed handler from {event_type.__name__} "
                           f"({len(self._subscribers[event_type])} remaining)")
                return True
            except ValueError:
                return False

    def publish(self, event: EventType) -> None:
        """Publish event to all subscribers.

        Handlers are called synchronously on the publisher's thread.
        If a handler raises an exception, it is logged and other handlers
        still execute.

        Args:
            event: Event instance to publish

        Thread-Safe: Yes

        Performance:
            - Acquires lock briefly to copy subscriber list
            - Calls handlers outside lock (parallel-safe)
            - ~0.01ms overhead + handler execution time

        Example:
            ```python
            event = PitchStartEvent(
                pitch_id="pitch_001",
                pitch_index=1,
                timestamp_ns=time.time_ns()
            )
            bus.publish(event)
            ```
        """
        event_type = type(event)
        handlers = []

        # Copy handler list inside lock (fast)
        with self._lock:
            handlers = self._subscribers.get(event_type, []).copy()
            self._event_count[event_type] = self._event_count.get(event_type, 0) + 1

        # Call handlers outside lock (slower, but allows concurrent publishing)
        if not handlers:
            logger.debug(f"Published {event_type.__name__} with no subscribers")
            return

        logger.debug(f"Publishing {event_type.__name__} to {len(handlers)} subscribers")

        failed_handlers = 0
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                failed_handlers += 1
                logger.error(
                    f"Event handler error for {event_type.__name__}: "
                    f"{e.__class__.__name__}: {e}",
                    exc_info=True
                )

                # Publish error event (but don't let it crash the bus)
                try:
                    publish_error(
                        category=ErrorCategory.INTERNAL,
                        severity=ErrorSeverity.WARNING,
                        message=f"Event handler failed: {e}",
                        details=f"Event: {event_type.__name__}, Handler: {handler.__name__}"
                    )
                except:
                    pass  # Last resort - don't crash on error reporting

        if failed_handlers > 0:
            logger.warning(f"{failed_handlers}/{len(handlers)} handlers failed for {event_type.__name__}")

    def get_subscriber_count(self, event_type: Type[EventType]) -> int:
        """Get number of subscribers for an event type.

        Args:
            event_type: Event class to check

        Returns:
            Number of registered handlers

        Thread-Safe: Yes
        """
        with self._lock:
            return len(self._subscribers.get(event_type, []))

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics.

        Returns:
            Dict with statistics:
            - event_types: Number of event types registered
            - total_subscribers: Total number of subscriptions
            - event_counts: Dict of event_type -> publish count
            - uptime_seconds: Time since bus creation

        Thread-Safe: Yes
        """
        with self._lock:
            stats = {
                "event_types": len(self._subscribers),
                "total_subscribers": sum(len(handlers) for handlers in self._subscribers.values()),
                "event_counts": {
                    event_type.__name__: count
                    for event_type, count in self._event_count.items()
                },
                "uptime_seconds": time.time() - self._start_time
            }
        return stats

    def clear_all_subscribers(self) -> None:
        """Remove all subscribers (useful for testing).

        Thread-Safe: Yes

        Warning: This will break all event communication. Only use for cleanup.
        """
        with self._lock:
            self._subscribers.clear()
            self._event_count.clear()
            logger.warning("Cleared all EventBus subscribers")

    def __repr__(self) -> str:
        """String representation of EventBus state."""
        stats = self.get_stats()
        return (f"EventBus(event_types={stats['event_types']}, "
                f"subscribers={stats['total_subscribers']}, "
                f"uptime={stats['uptime_seconds']:.1f}s)")

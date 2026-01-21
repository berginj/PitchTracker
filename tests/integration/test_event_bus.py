"""Integration tests for EventBus.

Tests the thread-safe publish/subscribe event system that enables
service communication in the refactored architecture.
"""

import threading
import time
from dataclasses import dataclass
from typing import List

import pytest

from app.events.event_bus import EventBus
from app.events.event_types import (
    FrameCapturedEvent,
    ObservationDetectedEvent,
    PitchStartEvent,
    PitchEndEvent,
    ErrorEvent
)
from contracts import Frame, StereoObservation


# Test fixtures for Frame and StereoObservation
@dataclass
class MockFrame:
    """Mock Frame for testing."""
    data: bytes
    width: int
    height: int
    timestamp_ns: int


@dataclass
class MockObservation:
    """Mock StereoObservation for testing."""
    timestamp_ns: int
    x: float
    y: float
    z: float


class TestEventBusBasics:
    """Test basic EventBus functionality."""

    def test_subscribe_and_publish(self):
        """Test basic subscribe and publish."""
        bus = EventBus()
        events_received = []

        def handler(event: PitchStartEvent):
            events_received.append(event)

        bus.subscribe(PitchStartEvent, handler)

        event = PitchStartEvent(
            pitch_id="test_001",
            pitch_index=1,
            timestamp_ns=123456789
        )
        bus.publish(event)

        assert len(events_received) == 1
        assert events_received[0].pitch_id == "test_001"
        assert events_received[0].pitch_index == 1

    def test_multiple_subscribers(self):
        """Test multiple handlers for same event type."""
        bus = EventBus()
        handler1_events = []
        handler2_events = []
        handler3_events = []

        def handler1(event: PitchStartEvent):
            handler1_events.append(event)

        def handler2(event: PitchStartEvent):
            handler2_events.append(event)

        def handler3(event: PitchStartEvent):
            handler3_events.append(event)

        bus.subscribe(PitchStartEvent, handler1)
        bus.subscribe(PitchStartEvent, handler2)
        bus.subscribe(PitchStartEvent, handler3)

        event = PitchStartEvent(
            pitch_id="test_002",
            pitch_index=2,
            timestamp_ns=987654321
        )
        bus.publish(event)

        # All handlers should receive the event
        assert len(handler1_events) == 1
        assert len(handler2_events) == 1
        assert len(handler3_events) == 1
        assert handler1_events[0].pitch_id == "test_002"
        assert handler2_events[0].pitch_id == "test_002"
        assert handler3_events[0].pitch_id == "test_002"

    def test_unsubscribe(self):
        """Test unsubscribing handlers."""
        bus = EventBus()
        events_received = []

        def handler(event: PitchStartEvent):
            events_received.append(event)

        bus.subscribe(PitchStartEvent, handler)

        # Publish first event - should be received
        event1 = PitchStartEvent(
            pitch_id="test_003",
            pitch_index=1,
            timestamp_ns=111
        )
        bus.publish(event1)
        assert len(events_received) == 1

        # Unsubscribe
        success = bus.unsubscribe(PitchStartEvent, handler)
        assert success is True

        # Publish second event - should NOT be received
        event2 = PitchStartEvent(
            pitch_id="test_004",
            pitch_index=2,
            timestamp_ns=222
        )
        bus.publish(event2)
        assert len(events_received) == 1  # Still 1, not 2

    def test_unsubscribe_nonexistent(self):
        """Test unsubscribing handler that was never subscribed."""
        bus = EventBus()

        def handler(event: PitchStartEvent):
            pass

        # Unsubscribe without subscribing first
        success = bus.unsubscribe(PitchStartEvent, handler)
        assert success is False

    def test_publish_with_no_subscribers(self):
        """Test publishing when no one is listening."""
        bus = EventBus()

        event = PitchStartEvent(
            pitch_id="test_005",
            pitch_index=1,
            timestamp_ns=333
        )

        # Should not raise exception
        bus.publish(event)

    def test_multiple_event_types(self):
        """Test bus handles multiple event types independently."""
        bus = EventBus()
        pitch_start_events = []
        pitch_end_events = []

        def handle_start(event: PitchStartEvent):
            pitch_start_events.append(event)

        def handle_end(event: PitchEndEvent):
            pitch_end_events.append(event)

        bus.subscribe(PitchStartEvent, handle_start)
        bus.subscribe(PitchEndEvent, handle_end)

        # Publish different event types
        start_event = PitchStartEvent(
            pitch_id="test_006",
            pitch_index=1,
            timestamp_ns=444
        )
        end_event = PitchEndEvent(
            pitch_id="test_006",
            observations=[],
            timestamp_ns=555,
            duration_ns=111
        )

        bus.publish(start_event)
        bus.publish(end_event)

        assert len(pitch_start_events) == 1
        assert len(pitch_end_events) == 1
        assert pitch_start_events[0].pitch_id == "test_006"
        assert pitch_end_events[0].pitch_id == "test_006"


class TestEventBusThreadSafety:
    """Test EventBus thread safety."""

    def test_concurrent_publishers(self):
        """Test multiple threads publishing simultaneously."""
        bus = EventBus()
        events_received = []
        lock = threading.Lock()

        def handler(event: PitchStartEvent):
            with lock:
                events_received.append(event)

        bus.subscribe(PitchStartEvent, handler)

        def publish_events(thread_id: int, count: int):
            for i in range(count):
                event = PitchStartEvent(
                    pitch_id=f"thread_{thread_id}_pitch_{i}",
                    pitch_index=i,
                    timestamp_ns=time.time_ns()
                )
                bus.publish(event)

        # Create 10 threads, each publishing 10 events
        threads = []
        for i in range(10):
            t = threading.Thread(target=publish_events, args=(i, 10))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Should receive all 100 events
        assert len(events_received) == 100

    def test_concurrent_subscribers(self):
        """Test multiple threads subscribing simultaneously."""
        bus = EventBus()
        events_received = []
        lock = threading.Lock()

        def create_handler(handler_id: int):
            def handler(event: PitchStartEvent):
                with lock:
                    events_received.append((handler_id, event))
            return handler

        def subscribe_handler(handler_id: int):
            handler = create_handler(handler_id)
            bus.subscribe(PitchStartEvent, handler)

        # Create 10 threads, each subscribing a handler
        threads = []
        for i in range(10):
            t = threading.Thread(target=subscribe_handler, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Publish one event
        event = PitchStartEvent(
            pitch_id="test_007",
            pitch_index=1,
            timestamp_ns=666
        )
        bus.publish(event)

        # Should be received by all 10 handlers
        assert len(events_received) == 10

    def test_subscribe_while_publishing(self):
        """Test subscribing while events are being published."""
        bus = EventBus()
        events_received = []
        lock = threading.Lock()
        publish_count = 100
        published = 0

        def handler(event: PitchStartEvent):
            with lock:
                events_received.append(event)

        def publisher():
            nonlocal published
            for i in range(publish_count):
                event = PitchStartEvent(
                    pitch_id=f"test_pub_{i}",
                    pitch_index=i,
                    timestamp_ns=time.time_ns()
                )
                bus.publish(event)
                published = i + 1
                time.sleep(0.001)  # Small delay

        def subscriber():
            time.sleep(0.01)  # Wait for some events to be published
            bus.subscribe(PitchStartEvent, handler)

        # Start publisher, then subscriber
        pub_thread = threading.Thread(target=publisher)
        sub_thread = threading.Thread(target=subscriber)

        pub_thread.start()
        sub_thread.start()

        pub_thread.join()
        sub_thread.join()

        # Should receive some (but not all) events
        # since subscription happened after some publishes
        assert 0 < len(events_received) < publish_count


class TestEventBusErrorHandling:
    """Test EventBus error isolation."""

    def test_handler_exception_isolation(self):
        """Test that handler exceptions don't crash bus."""
        bus = EventBus()
        handler1_events = []
        handler2_events = []
        handler3_events = []

        def handler1(event: PitchStartEvent):
            handler1_events.append(event)
            raise ValueError("Handler 1 error!")

        def handler2(event: PitchStartEvent):
            handler2_events.append(event)

        def handler3(event: PitchStartEvent):
            handler3_events.append(event)

        bus.subscribe(PitchStartEvent, handler1)
        bus.subscribe(PitchStartEvent, handler2)
        bus.subscribe(PitchStartEvent, handler3)

        event = PitchStartEvent(
            pitch_id="test_008",
            pitch_index=1,
            timestamp_ns=777
        )

        # Should not raise exception
        bus.publish(event)

        # Handler 1 should have received event (before raising)
        assert len(handler1_events) == 1
        # Handlers 2 and 3 should still receive event
        assert len(handler2_events) == 1
        assert len(handler3_events) == 1

    def test_multiple_handler_exceptions(self):
        """Test multiple handlers raising exceptions."""
        bus = EventBus()
        events_received = []

        def bad_handler1(event: PitchStartEvent):
            raise RuntimeError("Error 1")

        def bad_handler2(event: PitchStartEvent):
            raise ValueError("Error 2")

        def good_handler(event: PitchStartEvent):
            events_received.append(event)

        bus.subscribe(PitchStartEvent, bad_handler1)
        bus.subscribe(PitchStartEvent, bad_handler2)
        bus.subscribe(PitchStartEvent, good_handler)

        event = PitchStartEvent(
            pitch_id="test_009",
            pitch_index=1,
            timestamp_ns=888
        )

        # Should not raise exception
        bus.publish(event)

        # Good handler should still receive event
        assert len(events_received) == 1


class TestEventBusStatistics:
    """Test EventBus statistics tracking."""

    def test_get_subscriber_count(self):
        """Test getting subscriber count for event type."""
        bus = EventBus()

        def handler1(event: PitchStartEvent):
            pass

        def handler2(event: PitchStartEvent):
            pass

        def handler3(event: PitchEndEvent):
            pass

        # Initially no subscribers
        assert bus.get_subscriber_count(PitchStartEvent) == 0
        assert bus.get_subscriber_count(PitchEndEvent) == 0

        # Subscribe handlers
        bus.subscribe(PitchStartEvent, handler1)
        bus.subscribe(PitchStartEvent, handler2)
        bus.subscribe(PitchEndEvent, handler3)

        assert bus.get_subscriber_count(PitchStartEvent) == 2
        assert bus.get_subscriber_count(PitchEndEvent) == 1

    def test_get_stats(self):
        """Test getting overall bus statistics."""
        bus = EventBus()

        def handler1(event: PitchStartEvent):
            pass

        def handler2(event: PitchEndEvent):
            pass

        bus.subscribe(PitchStartEvent, handler1)
        bus.subscribe(PitchEndEvent, handler2)

        # Publish some events
        bus.publish(PitchStartEvent(pitch_id="p1", pitch_index=1, timestamp_ns=111))
        bus.publish(PitchStartEvent(pitch_id="p2", pitch_index=2, timestamp_ns=222))
        bus.publish(PitchEndEvent(pitch_id="p1", observations=[], timestamp_ns=333, duration_ns=222))

        stats = bus.get_stats()

        assert stats["event_types"] == 2
        assert stats["total_subscribers"] == 2
        assert stats["event_counts"]["PitchStartEvent"] == 2
        assert stats["event_counts"]["PitchEndEvent"] == 1
        assert stats["uptime_seconds"] > 0

    def test_clear_all_subscribers(self):
        """Test clearing all subscribers."""
        bus = EventBus()
        events_received = []

        def handler(event: PitchStartEvent):
            events_received.append(event)

        bus.subscribe(PitchStartEvent, handler)

        # Publish before clear
        event1 = PitchStartEvent(pitch_id="p1", pitch_index=1, timestamp_ns=111)
        bus.publish(event1)
        assert len(events_received) == 1

        # Clear all
        bus.clear_all_subscribers()

        # Publish after clear - should not be received
        event2 = PitchStartEvent(pitch_id="p2", pitch_index=2, timestamp_ns=222)
        bus.publish(event2)
        assert len(events_received) == 1  # Still 1, not 2

        # Stats should be cleared
        stats = bus.get_stats()
        assert stats["event_types"] == 0
        assert stats["total_subscribers"] == 0


class TestEventBusRepr:
    """Test EventBus string representation."""

    def test_repr(self):
        """Test __repr__ output."""
        bus = EventBus()

        def handler(event: PitchStartEvent):
            pass

        bus.subscribe(PitchStartEvent, handler)
        bus.subscribe(PitchStartEvent, handler)  # Subscribe twice

        repr_str = repr(bus)
        assert "EventBus" in repr_str
        assert "event_types=1" in repr_str
        assert "subscribers=2" in repr_str
        assert "uptime=" in repr_str


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

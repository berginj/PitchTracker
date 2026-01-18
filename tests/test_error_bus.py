"""Unit tests for error event bus (Phase 2 Fix #1)."""

import time
import unittest
from unittest.mock import Mock

from app.events import (
    ErrorCategory,
    ErrorEvent,
    ErrorEventBus,
    ErrorSeverity,
    get_error_bus,
    publish_error,
)


class TestErrorEvent(unittest.TestCase):
    """Test ErrorEvent dataclass."""

    def test_error_event_creation(self):
        """Test that ErrorEvent can be created with all fields."""
        event = ErrorEvent(
            category=ErrorCategory.DETECTION,
            severity=ErrorSeverity.ERROR,
            message="Test error",
            source="TestSource",
            exception=ValueError("test"),
            metadata={"key": "value"},
        )

        self.assertEqual(event.category, ErrorCategory.DETECTION)
        self.assertEqual(event.severity, ErrorSeverity.ERROR)
        self.assertEqual(event.message, "Test error")
        self.assertEqual(event.source, "TestSource")
        self.assertIsInstance(event.exception, ValueError)
        self.assertEqual(event.metadata, {"key": "value"})
        self.assertIsInstance(event.timestamp, float)

    def test_error_event_string_representation(self):
        """Test ErrorEvent __str__ method."""
        event = ErrorEvent(
            category=ErrorCategory.CAMERA,
            severity=ErrorSeverity.WARNING,
            message="Camera disconnected",
            source="CameraManager",
        )

        str_repr = str(event)
        self.assertIn("WARNING", str_repr)
        self.assertIn("camera", str_repr)
        self.assertIn("Camera disconnected", str_repr)
        self.assertIn("CameraManager", str_repr)


class TestErrorEventBus(unittest.TestCase):
    """Test ErrorEventBus functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.bus = ErrorEventBus()

    def test_subscribe_to_all_errors(self):
        """Test subscribing to all error events."""
        callback = Mock()
        self.bus.subscribe(callback)

        # Publish event
        event = ErrorEvent(
            category=ErrorCategory.DETECTION,
            severity=ErrorSeverity.ERROR,
            message="Test",
            source="Test",
        )
        self.bus.publish(event)

        # Callback should be called
        callback.assert_called_once_with(event)

    def test_subscribe_to_specific_category(self):
        """Test subscribing to specific error category."""
        callback = Mock()
        self.bus.subscribe(callback, category=ErrorCategory.DISK_SPACE)

        # Publish matching event
        event1 = ErrorEvent(
            category=ErrorCategory.DISK_SPACE,
            severity=ErrorSeverity.WARNING,
            message="Low disk space",
            source="Test",
        )
        self.bus.publish(event1)
        callback.assert_called_once_with(event1)

        # Publish non-matching event
        event2 = ErrorEvent(
            category=ErrorCategory.DETECTION,
            severity=ErrorSeverity.ERROR,
            message="Detection failed",
            source="Test",
        )
        self.bus.publish(event2)

        # Should still only be called once (for matching event)
        self.assertEqual(callback.call_count, 1)

    def test_multiple_subscribers(self):
        """Test multiple subscribers to same category."""
        callback1 = Mock()
        callback2 = Mock()

        self.bus.subscribe(callback1, category=ErrorCategory.CAMERA)
        self.bus.subscribe(callback2, category=ErrorCategory.CAMERA)

        event = ErrorEvent(
            category=ErrorCategory.CAMERA,
            severity=ErrorSeverity.ERROR,
            message="Camera error",
            source="Test",
        )
        self.bus.publish(event)

        # Both callbacks should be called
        callback1.assert_called_once_with(event)
        callback2.assert_called_once_with(event)

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        callback = Mock()
        self.bus.subscribe(callback)

        # Publish event - should be received
        event1 = ErrorEvent(
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.INFO,
            message="Test 1",
            source="Test",
        )
        self.bus.publish(event1)
        callback.assert_called_once()

        # Unsubscribe
        self.bus.unsubscribe(callback)

        # Publish another event - should not be received
        event2 = ErrorEvent(
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.INFO,
            message="Test 2",
            source="Test",
        )
        self.bus.publish(event2)

        # Should still only have one call (from before unsubscribe)
        self.assertEqual(callback.call_count, 1)

    def test_event_history(self):
        """Test that event history is maintained."""
        # Publish multiple events
        for i in range(5):
            event = ErrorEvent(
                category=ErrorCategory.DETECTION,
                severity=ErrorSeverity.ERROR,
                message=f"Error {i}",
                source="Test",
            )
            self.bus.publish(event)

        # Check history
        history = self.bus.get_history()
        self.assertEqual(len(history), 5)

        # Check order (should be chronological)
        for i, event in enumerate(history):
            self.assertIn(f"Error {i}", event.message)

    def test_history_filtered_by_category(self):
        """Test getting history filtered by category."""
        # Publish events of different categories
        for category in [ErrorCategory.CAMERA, ErrorCategory.DETECTION, ErrorCategory.DISK_SPACE]:
            event = ErrorEvent(
                category=category,
                severity=ErrorSeverity.ERROR,
                message=f"{category.value} error",
                source="Test",
            )
            self.bus.publish(event)

        # Get filtered history
        camera_history = self.bus.get_history(category=ErrorCategory.CAMERA)
        self.assertEqual(len(camera_history), 1)
        self.assertEqual(camera_history[0].category, ErrorCategory.CAMERA)

    def test_history_limit(self):
        """Test that history respects max size."""
        # Publish more events than max history (100)
        for i in range(150):
            event = ErrorEvent(
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.INFO,
                message=f"Event {i}",
                source="Test",
            )
            self.bus.publish(event)

        # History should be limited to 100
        history = self.bus.get_history()
        self.assertEqual(len(history), 100)

        # Should have the most recent 100
        self.assertIn("Event 149", history[-1].message)
        self.assertIn("Event 50", history[0].message)

    def test_error_counts(self):
        """Test that error counts are tracked per category."""
        # Publish multiple events
        for _ in range(3):
            self.bus.publish(
                ErrorEvent(
                    category=ErrorCategory.CAMERA,
                    severity=ErrorSeverity.ERROR,
                    message="Camera error",
                    source="Test",
                )
            )

        for _ in range(2):
            self.bus.publish(
                ErrorEvent(
                    category=ErrorCategory.DETECTION,
                    severity=ErrorSeverity.ERROR,
                    message="Detection error",
                    source="Test",
                )
            )

        # Check counts
        counts = self.bus.get_error_counts()
        self.assertEqual(counts[ErrorCategory.CAMERA], 3)
        self.assertEqual(counts[ErrorCategory.DETECTION], 2)

    def test_clear_history(self):
        """Test clearing history and counts."""
        # Publish events
        for i in range(5):
            self.bus.publish(
                ErrorEvent(
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.INFO,
                    message=f"Event {i}",
                    source="Test",
                )
            )

        # Clear
        self.bus.clear_history()

        # Check history is empty
        history = self.bus.get_history()
        self.assertEqual(len(history), 0)

        # Check counts are reset
        counts = self.bus.get_error_counts()
        self.assertEqual(len(counts), 0)

    def test_subscriber_exception_does_not_crash(self):
        """Test that exception in subscriber doesn't crash bus."""

        def failing_callback(event):
            raise RuntimeError("Subscriber failed")

        normal_callback = Mock()

        self.bus.subscribe(failing_callback)
        self.bus.subscribe(normal_callback)

        # Publish event
        event = ErrorEvent(
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            message="Test",
            source="Test",
        )

        # Should not raise exception
        self.bus.publish(event)

        # Normal callback should still be called
        normal_callback.assert_called_once_with(event)


class TestGlobalErrorBus(unittest.TestCase):
    """Test global error bus functions."""

    def test_get_error_bus_singleton(self):
        """Test that get_error_bus returns singleton."""
        bus1 = get_error_bus()
        bus2 = get_error_bus()
        self.assertIs(bus1, bus2)

    def test_publish_error_convenience_function(self):
        """Test publish_error convenience function."""
        callback = Mock()
        get_error_bus().subscribe(callback)

        # Publish using convenience function
        publish_error(
            category=ErrorCategory.RECORDING,
            severity=ErrorSeverity.WARNING,
            message="Test warning",
            source="TestSource",
            test_key="test_value",
        )

        # Callback should be called
        callback.assert_called_once()
        event = callback.call_args[0][0]
        self.assertEqual(event.category, ErrorCategory.RECORDING)
        self.assertEqual(event.severity, ErrorSeverity.WARNING)
        self.assertEqual(event.message, "Test warning")
        self.assertEqual(event.source, "TestSource")
        self.assertEqual(event.metadata["test_key"], "test_value")


if __name__ == "__main__":
    unittest.main()

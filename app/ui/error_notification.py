"""UI error notification widget for displaying system errors to users."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.events import ErrorCategory, ErrorEvent, ErrorSeverity, get_error_bus

logger = logging.getLogger(__name__)


class ErrorNotificationWidget(QWidget):
    """Widget for displaying error notifications in the UI."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize error notification widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._current_notification: Optional[QFrame] = None
        self._setup_ui()
        self._subscribe_to_errors()

    def _setup_ui(self) -> None:
        """Setup UI components."""
        self.setObjectName("ErrorNotificationWidget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)

        # Hidden by default
        self.setVisible(False)

    def _subscribe_to_errors(self) -> None:
        """Subscribe to error events from error bus."""
        # Subscribe to all errors
        get_error_bus().subscribe(self._on_error_event)
        logger.debug("ErrorNotificationWidget subscribed to error events")

    def _on_error_event(self, event: ErrorEvent) -> None:
        """Handle error event from error bus.

        Args:
            event: Error event
        """
        # Only show warnings and above
        if event.severity in [ErrorSeverity.WARNING, ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]:
            # Use Qt signal to ensure UI update happens on main thread
            self._show_notification_safe(event)

    def _show_notification_safe(self, event: ErrorEvent) -> None:
        """Show notification in thread-safe manner.

        Args:
            event: Error event to display
        """
        # This should be called from main thread via signal/slot
        # For now, call directly (assumes error bus publishes from main thread)
        self._show_notification(event)

    def _show_notification(self, event: ErrorEvent) -> None:
        """Show error notification in UI.

        Args:
            event: Error event to display
        """
        # Clear existing notification
        if self._current_notification is not None:
            self._layout.removeWidget(self._current_notification)
            self._current_notification.deleteLater()
            self._current_notification = None

        # Create notification frame
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFrameShadow(QFrame.Shadow.Raised)

        # Set background color based on severity
        severity_colors = {
            ErrorSeverity.WARNING: "#FFF3CD",  # Light yellow
            ErrorSeverity.ERROR: "#F8D7DA",  # Light red
            ErrorSeverity.CRITICAL: "#F5C2C7",  # Darker red
        }
        bg_color = severity_colors.get(event.severity, "#F8F9FA")
        frame.setStyleSheet(f"QFrame {{ background-color: {bg_color}; padding: 10px; border-radius: 5px; }}")

        # Frame layout
        frame_layout = QHBoxLayout(frame)

        # Severity icon/label
        severity_label = QLabel(self._get_severity_icon(event.severity))
        severity_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        frame_layout.addWidget(severity_label)

        # Message layout
        message_layout = QVBoxLayout()

        # Title (category + severity)
        title = QLabel(f"{event.severity.value.upper()}: {event.category.value.replace('_', ' ').title()}")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        message_layout.addWidget(title)

        # Message
        message_label = QLabel(event.message)
        message_label.setWordWrap(True)
        message_layout.addWidget(message_label)

        # Source and timestamp
        timestamp = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
        source_label = QLabel(f"Source: {event.source} at {timestamp}")
        source_label.setStyleSheet("font-size: 10px; color: #6c757d;")
        message_layout.addWidget(source_label)

        frame_layout.addLayout(message_layout, 1)

        # Dismiss button
        dismiss_btn = QPushButton("✕")
        dismiss_btn.setFixedSize(30, 30)
        dismiss_btn.setStyleSheet(
            "QPushButton { "
            "background-color: transparent; "
            "border: none; "
            "font-size: 16px; "
            "font-weight: bold; "
            "} "
            "QPushButton:hover { "
            "background-color: rgba(0, 0, 0, 0.1); "
            "}"
        )
        dismiss_btn.clicked.connect(self._dismiss_notification)
        frame_layout.addWidget(dismiss_btn)

        # Add frame to layout
        self._layout.addWidget(frame)
        self._current_notification = frame

        # Show widget
        self.setVisible(True)

        logger.debug(f"Displayed error notification: {event.message}")

    def _get_severity_icon(self, severity: ErrorSeverity) -> str:
        """Get icon for severity level.

        Args:
            severity: Error severity

        Returns:
            Unicode icon string
        """
        icons = {
            ErrorSeverity.INFO: "ℹ️",
            ErrorSeverity.WARNING: "⚠️",
            ErrorSeverity.ERROR: "❌",
            ErrorSeverity.CRITICAL: "🔥",
        }
        return icons.get(severity, "❓")

    def _dismiss_notification(self) -> None:
        """Dismiss current notification."""
        if self._current_notification is not None:
            self._layout.removeWidget(self._current_notification)
            self._current_notification.deleteLater()
            self._current_notification = None

        # Hide widget if no notifications
        self.setVisible(False)
        logger.debug("Dismissed error notification")

    def cleanup(self) -> None:
        """Cleanup error notification widget."""
        # Unsubscribe from error bus
        get_error_bus().unsubscribe(self._on_error_event)
        logger.debug("ErrorNotificationWidget unsubscribed from error events")


class ErrorNotificationBridge(QObject):
    """Bridge for thread-safe error notifications to Qt UI.

    This class ensures error events from background threads are properly
    marshaled to the Qt main thread using signals/slots.
    """

    error_received = Signal(object)  # ErrorEvent

    def __init__(self, widget: ErrorNotificationWidget):
        """Initialize notification bridge.

        Args:
            widget: Error notification widget to update
        """
        super().__init__()
        self._widget = widget

        # Connect signal to widget update
        self.error_received.connect(self._widget._show_notification, Qt.ConnectionType.QueuedConnection)

        # Subscribe to error bus
        get_error_bus().subscribe(self._on_error_event)
        logger.debug("ErrorNotificationBridge subscribed to error events")

    def _on_error_event(self, event: ErrorEvent) -> None:
        """Handle error event from error bus.

        Args:
            event: Error event
        """
        # Only show warnings and above
        if event.severity in [ErrorSeverity.WARNING, ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]:
            # Emit signal to marshal to main thread
            self.error_received.emit(event)

    def cleanup(self) -> None:
        """Cleanup notification bridge."""
        get_error_bus().unsubscribe(self._on_error_event)
        logger.debug("ErrorNotificationBridge unsubscribed from error events")


__all__ = [
    "ErrorNotificationWidget",
    "ErrorNotificationBridge",
]

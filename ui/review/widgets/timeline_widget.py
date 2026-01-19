"""Timeline scrubber widget for review mode."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets


class TimelineWidget(QtWidgets.QWidget):
    """Timeline scrubber for seeking through video.

    Displays a horizontal bar representing the video timeline with:
    - Current frame position indicator
    - Click/drag to seek
    - Frame counter display

    Signals:
        seek_requested: Emitted when user seeks to frame (int frame_index)
    """

    # Signals
    seek_requested = QtCore.Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize timeline widget.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        self._current_frame = 0
        self._total_frames = 0
        self._fps = 30.0
        self._dragging = False

        self.setMinimumHeight(80)
        self.setMaximumHeight(80)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def set_current_frame(self, frame_index: int) -> None:
        """Set current frame position.

        Args:
            frame_index: Current frame index (0-based)
        """
        self._current_frame = frame_index
        self.update()  # Trigger repaint

    def set_total_frames(self, total: int) -> None:
        """Set total frame count.

        Args:
            total: Total number of frames
        """
        self._total_frames = total
        self.update()

    def set_fps(self, fps: float) -> None:
        """Set video frame rate.

        Args:
            fps: Frames per second
        """
        self._fps = fps

    def reset(self) -> None:
        """Reset timeline to initial state."""
        self._current_frame = 0
        self._total_frames = 0
        self._fps = 30.0
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the timeline.

        Args:
            event: Paint event
        """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Get widget dimensions
        width = self.width()
        height = self.height()

        # Background
        painter.fillRect(0, 0, width, height, QtGui.QColor("#1e1e1e"))

        if self._total_frames == 0:
            # No video loaded - show placeholder text
            painter.setPen(QtGui.QColor("#888"))
            painter.drawText(
                QtCore.QRect(0, 0, width, height),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "No video loaded",
            )
            return

        # Timeline bar area (leaving space for labels)
        bar_y = 30
        bar_height = 20
        margin = 10

        # Draw timeline bar background
        bar_rect = QtCore.QRect(margin, bar_y, width - 2 * margin, bar_height)
        painter.fillRect(bar_rect, QtGui.QColor("#333"))

        # Draw border
        painter.setPen(QtGui.QColor("#555"))
        painter.drawRect(bar_rect)

        # Calculate progress
        if self._total_frames > 0:
            progress = self._current_frame / max(1, self._total_frames - 1)
        else:
            progress = 0.0

        # Draw progress bar
        progress_width = int((width - 2 * margin) * progress)
        if progress_width > 0:
            progress_rect = QtCore.QRect(margin, bar_y, progress_width, bar_height)
            painter.fillRect(progress_rect, QtGui.QColor("#2196F3"))

        # Draw current position indicator (vertical line)
        indicator_x = margin + progress_width
        painter.setPen(QtGui.QPen(QtGui.QColor("#FFF"), 2))
        painter.drawLine(indicator_x, bar_y - 5, indicator_x, bar_y + bar_height + 5)

        # Draw frame counter text
        current_time_ms = (self._current_frame / self._fps) * 1000.0 if self._fps > 0 else 0.0
        total_time_ms = (self._total_frames / self._fps) * 1000.0 if self._fps > 0 else 0.0

        frame_text = (
            f"Frame {self._current_frame + 1}/{self._total_frames}  "
            f"({self._format_time(current_time_ms)} / {self._format_time(total_time_ms)})"
        )

        painter.setPen(QtGui.QColor("#FFF"))
        painter.drawText(
            QtCore.QRect(0, 5, width, 20),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            frame_text,
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse press - start seeking.

        Args:
            event: Mouse event
        """
        if self._total_frames == 0:
            return

        self._dragging = True
        self._seek_to_position(event.position().x())

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse move - continue seeking while dragging.

        Args:
            event: Mouse event
        """
        if self._dragging:
            self._seek_to_position(event.position().x())

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse release - end seeking.

        Args:
            event: Mouse event
        """
        self._dragging = False

    def _seek_to_position(self, x: float) -> None:
        """Seek to frame at x position.

        Args:
            x: X coordinate within widget
        """
        width = self.width()
        margin = 10

        # Calculate frame index from x position
        bar_width = width - 2 * margin
        relative_x = max(0, min(x - margin, bar_width))
        progress = relative_x / bar_width

        frame_index = int(progress * (self._total_frames - 1))
        frame_index = max(0, min(frame_index, self._total_frames - 1))

        # Emit seek request
        self.seek_requested.emit(frame_index)

    @staticmethod
    def _format_time(ms: float) -> str:
        """Format milliseconds as MM:SS.mmm.

        Args:
            ms: Time in milliseconds

        Returns:
            Formatted time string
        """
        total_seconds = ms / 1000.0
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60

        return f"{minutes:02d}:{seconds:06.3f}"

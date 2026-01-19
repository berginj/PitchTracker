"""Chart widgets for session progression view."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets


class VelocityTrendChart(QtWidgets.QWidget):
    """Line chart showing velocity trend over session."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize velocity trend chart.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._data: List[Tuple[int, float]] = []  # (pitch_index, velocity_mph)
        self.setMinimumSize(400, 200)

    def update_data(self, data: List[Tuple[int, float]]) -> None:
        """Update chart data.

        Args:
            data: List of (pitch_index, velocity_mph) tuples
        """
        self._data = data
        self.update()

    def clear(self) -> None:
        """Clear chart data."""
        self._data.clear()
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the chart."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        margin = 40

        # Draw background
        painter.fillRect(0, 0, width, height, QtGui.QColor(250, 250, 250))

        # Draw border
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.lightGray, 1))
        painter.drawRect(0, 0, width - 1, height - 1)

        if not self._data:
            # No data - show placeholder
            painter.setPen(QtCore.Qt.GlobalColor.gray)
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(
                QtCore.QRect(0, 0, width, height),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "No velocity data"
            )
            return

        # Get data range
        velocities = [v for _, v in self._data]
        v_min = max(0, min(velocities) - 5)
        v_max = max(velocities) + 5
        pitch_count = len(self._data)

        # Plot area
        plot_width = width - 2 * margin
        plot_height = height - 2 * margin

        def to_screen_x(pitch_idx: int) -> int:
            norm = pitch_idx / max(1, pitch_count - 1)
            return int(margin + norm * plot_width)

        def to_screen_y(velocity: float) -> int:
            norm = (velocity - v_min) / max(1, v_max - v_min)
            return int(height - margin - norm * plot_height)

        # Draw grid lines
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.lightGray, 1, QtCore.Qt.PenStyle.DashLine))
        for i in range(5):
            v = v_min + (v_max - v_min) * i / 4
            y = to_screen_y(v)
            painter.drawLine(margin, y, width - margin, y)

        # Draw axes
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black, 2))
        painter.drawLine(margin, height - margin, width - margin, height - margin)  # X-axis
        painter.drawLine(margin, margin, margin, height - margin)  # Y-axis

        # Draw labels
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        # Y-axis labels (velocity)
        for i in range(5):
            v = v_min + (v_max - v_min) * i / 4
            y = to_screen_y(v)
            painter.drawText(5, y + 5, f"{v:.0f}")

        # X-axis label
        painter.drawText(width // 2 - 30, height - 5, "Pitch Number")

        # Y-axis label
        painter.save()
        painter.translate(10, height // 2 + 30)
        painter.rotate(-90)
        painter.drawText(0, 0, "Velocity (mph)")
        painter.restore()

        # Draw line
        if len(self._data) >= 2:
            painter.setPen(QtGui.QPen(QtGui.QColor(33, 150, 243), 3))  # Blue
            points = [QtCore.QPoint(to_screen_x(i), to_screen_y(v)) for i, v in self._data]
            painter.drawPolyline(points)

            # Draw points
            painter.setBrush(QtGui.QBrush(QtGui.QColor(33, 150, 243)))
            for point in points:
                painter.drawEllipse(point, 4, 4)


class StrikeRatioGauge(QtWidgets.QWidget):
    """Circular gauge showing strike percentage."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize strike ratio gauge.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._percentage = 0.0  # 0.0 to 1.0
        self.setMinimumSize(200, 200)

    def set_percentage(self, percentage: float) -> None:
        """Set strike percentage.

        Args:
            percentage: Strike percentage (0.0 to 1.0)
        """
        self._percentage = max(0.0, min(1.0, percentage))
        self.update()

    def clear(self) -> None:
        """Clear gauge."""
        self._percentage = 0.0
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the gauge."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        size = min(width, height)
        center_x = width // 2
        center_y = height // 2
        radius = size // 2 - 20

        # Draw background circle
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.lightGray, 10))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        # Draw strike percentage arc
        # Green gradient based on percentage
        color = self._get_color_for_percentage(self._percentage)
        painter.setPen(QtGui.QPen(color, 10, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))

        # Arc starts at 90 degrees (top), goes clockwise
        start_angle = 90 * 16  # Qt uses 1/16th degree units
        span_angle = -int(self._percentage * 360 * 16)  # Negative for clockwise

        painter.drawArc(
            center_x - radius,
            center_y - radius,
            radius * 2,
            radius * 2,
            start_angle,
            span_angle
        )

        # Draw percentage text
        painter.setPen(QtCore.Qt.GlobalColor.black)
        font = painter.font()
        font.setPointSize(24)
        font.setBold(True)
        painter.setFont(font)
        text = f"{self._percentage * 100:.0f}%"
        painter.drawText(
            QtCore.QRect(0, center_y - 20, width, 40),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            text
        )

        # Draw label
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(
            QtCore.QRect(0, center_y + 20, width, 30),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            "Strike %"
        )

    def _get_color_for_percentage(self, pct: float) -> QtGui.QColor:
        """Get color based on percentage.

        Args:
            pct: Percentage (0.0 to 1.0)

        Returns:
            Color (red → yellow → green)
        """
        if pct < 0.5:
            # Red to yellow
            r = 255
            g = int(255 * pct * 2)
            b = 0
        else:
            # Yellow to green
            r = int(255 * (1 - pct) * 2)
            g = 255
            b = 0
        return QtGui.QColor(r, g, b)


class AccuracyTrendChart(QtWidgets.QWidget):
    """Line chart showing rolling strike accuracy."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize accuracy trend chart.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._data: List[Tuple[int, float]] = []  # (pitch_index, accuracy)
        self.setMinimumSize(300, 150)

    def update_data(self, data: List[Tuple[int, float]]) -> None:
        """Update chart data.

        Args:
            data: List of (pitch_index, accuracy) tuples where accuracy is 0.0-1.0
        """
        self._data = data
        self.update()

    def clear(self) -> None:
        """Clear chart data."""
        self._data.clear()
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the chart."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        margin = 30

        # Draw background
        painter.fillRect(0, 0, width, height, QtGui.QColor(250, 250, 250))

        # Draw border
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.lightGray, 1))
        painter.drawRect(0, 0, width - 1, height - 1)

        if not self._data:
            painter.setPen(QtCore.Qt.GlobalColor.gray)
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(
                QtCore.QRect(0, 0, width, height),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "No accuracy data"
            )
            return

        pitch_count = len(self._data)
        plot_width = width - 2 * margin
        plot_height = height - 2 * margin

        def to_screen_x(pitch_idx: int) -> int:
            norm = pitch_idx / max(1, pitch_count - 1)
            return int(margin + norm * plot_width)

        def to_screen_y(accuracy: float) -> int:
            # Accuracy is 0.0 to 1.0
            return int(height - margin - accuracy * plot_height)

        # Draw grid
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.lightGray, 1, QtCore.Qt.PenStyle.DashLine))
        for i in range(5):
            acc = i / 4.0
            y = to_screen_y(acc)
            painter.drawLine(margin, y, width - margin, y)

        # Draw axes
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black, 2))
        painter.drawLine(margin, height - margin, width - margin, height - margin)
        painter.drawLine(margin, margin, margin, height - margin)

        # Labels
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        for i in range(5):
            acc = i / 4.0
            y = to_screen_y(acc)
            painter.drawText(5, y + 5, f"{acc*100:.0f}%")

        painter.drawText(width // 2 - 20, height - 5, "Pitch #")

        # Draw line
        if len(self._data) >= 2:
            painter.setPen(QtGui.QPen(QtGui.QColor(76, 175, 80), 3))  # Green
            points = [QtCore.QPoint(to_screen_x(i), to_screen_y(acc)) for i, acc in self._data]
            painter.drawPolyline(points)

            # Draw points
            painter.setBrush(QtGui.QBrush(QtGui.QColor(76, 175, 80)))
            for point in points:
                painter.drawEllipse(point, 3, 3)


class FastestPitchWidget(QtWidgets.QWidget):
    """Large display showing fastest pitch in session."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize fastest pitch widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._speed = 0.0
        self.setMinimumSize(200, 100)

    def set_speed(self, speed: float) -> None:
        """Set fastest pitch speed.

        Args:
            speed: Speed in mph
        """
        self._speed = speed
        self.update()

    def clear(self) -> None:
        """Clear display."""
        self._speed = 0.0
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the widget."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Draw background
        painter.fillRect(0, 0, width, height, QtGui.QColor(255, 235, 59))  # Yellow

        # Draw border
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black, 2))
        painter.drawRect(0, 0, width - 1, height - 1)

        # Draw label
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QtCore.QRect(0, 10, width, 30),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            "FASTEST PITCH"
        )

        # Draw speed
        font.setPointSize(36)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(211, 47, 47))  # Red
        speed_text = f"{self._speed:.1f}" if self._speed > 0 else "--"
        painter.drawText(
            QtCore.QRect(0, 40, width, 50),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            speed_text
        )

        # Draw units
        font.setPointSize(14)
        painter.setFont(font)
        painter.setPen(QtCore.Qt.GlobalColor.black)
        painter.drawText(
            QtCore.QRect(0, height - 30, width, 25),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            "mph"
        )


__all__ = [
    "VelocityTrendChart",
    "StrikeRatioGauge",
    "AccuracyTrendChart",
    "FastestPitchWidget"
]

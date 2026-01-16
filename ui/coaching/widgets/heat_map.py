"""Heat map widget for visualizing pitch location distribution."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets


class HeatMapWidget(QtWidgets.QWidget):
    """Heat map widget showing pitch count by strike zone location.

    Displays a 3x3 grid with pitch counts in each zone.
    Color intensity represents frequency.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)

        # Zone counts (3x3 grid, row-major order)
        # Zones: [0,0] [0,1] [0,2]
        #        [1,0] [1,1] [1,2]
        #        [2,0] [2,1] [2,2]
        self._zone_counts = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        self._max_count = 1  # For color scaling

    def add_pitch(self, zone_x: int, zone_y: int) -> None:
        """Add a pitch to the specified zone.

        Args:
            zone_x: Zone x coordinate (0=left, 1=center, 2=right)
            zone_y: Zone y coordinate (0=top, 1=middle, 2=bottom)
        """
        if 0 <= zone_x < 3 and 0 <= zone_y < 3:
            self._zone_counts[zone_y][zone_x] += 1
            self._max_count = max(self._max_count, self._zone_counts[zone_y][zone_x])
            self.update()

    def clear(self) -> None:
        """Clear all pitch counts."""
        self._zone_counts = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        self._max_count = 1
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the heat map."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Get widget dimensions
        width = self.width()
        height = self.height()

        # Calculate cell size (leave margin)
        margin = 10
        cell_width = (width - 2 * margin) / 3
        cell_height = (height - 2 * margin) / 3

        # Draw 3x3 grid
        for row in range(3):
            for col in range(3):
                count = self._zone_counts[row][col]

                # Calculate cell position
                x = margin + col * cell_width
                y = margin + row * cell_height

                # Calculate color intensity based on count
                intensity = count / self._max_count if self._max_count > 0 else 0
                color = self._get_heat_color(intensity)

                # Draw cell
                painter.fillRect(
                    int(x), int(y), int(cell_width), int(cell_height),
                    color
                )

                # Draw border
                painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black, 2))
                painter.drawRect(int(x), int(y), int(cell_width), int(cell_height))

                # Draw count text
                if count > 0:
                    painter.setPen(QtCore.Qt.GlobalColor.black)
                    font = painter.font()
                    font.setPointSize(16)
                    font.setBold(True)
                    painter.setFont(font)

                    text_rect = QtCore.QRectF(x, y, cell_width, cell_height)
                    painter.drawText(
                        text_rect,
                        QtCore.Qt.AlignmentFlag.AlignCenter,
                        str(count)
                    )

        # Draw zone labels
        painter.setPen(QtCore.Qt.GlobalColor.gray)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        # Top labels (High, Middle, Low)
        painter.drawText(
            QtCore.QRect(0, 0, width, margin),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            "HIGH - MID - LOW"
        )

    def _get_heat_color(self, intensity: float) -> QtGui.QColor:
        """Get color based on intensity (0.0 to 1.0).

        Color scale: white (0) → light blue → blue → red (1)
        """
        if intensity == 0:
            return QtGui.QColor(255, 255, 255)  # White
        elif intensity < 0.25:
            # White to light blue
            t = intensity / 0.25
            return QtGui.QColor(
                int(255 - t * 100),
                int(255 - t * 100),
                255
            )
        elif intensity < 0.5:
            # Light blue to blue
            t = (intensity - 0.25) / 0.25
            return QtGui.QColor(
                int(155 - t * 122),
                int(155 - t * 155),
                255
            )
        elif intensity < 0.75:
            # Blue to purple
            t = (intensity - 0.5) / 0.25
            return QtGui.QColor(
                int(33 + t * 95),
                0,
                int(255 - t * 55)
            )
        else:
            # Purple to red
            t = (intensity - 0.75) / 0.25
            return QtGui.QColor(
                int(128 + t * 127),
                0,
                int(200 - t * 200)
            )


class StrikeZoneOverlay(QtWidgets.QWidget):
    """Strike zone overlay widget for camera preview.

    Draws a 3x3 strike zone grid over the camera image.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Strike zone boundaries (normalized 0.0-1.0)
        self._zone_left = 0.3
        self._zone_right = 0.7
        self._zone_top = 0.2
        self._zone_bottom = 0.7

        # Latest pitch location (normalized 0.0-1.0)
        self._latest_pitch: Optional[tuple[float, float]] = None

    def set_strike_zone(self, left: float, right: float, top: float, bottom: float) -> None:
        """Set strike zone boundaries (normalized coordinates 0.0-1.0)."""
        self._zone_left = left
        self._zone_right = right
        self._zone_top = top
        self._zone_bottom = bottom
        self.update()

    def set_latest_pitch(self, x: float, y: float) -> None:
        """Set latest pitch location (normalized coordinates 0.0-1.0).

        Args:
            x: Horizontal position (0.0=left, 1.0=right)
            y: Vertical position (0.0=top, 1.0=bottom)
        """
        self._latest_pitch = (x, y)
        self.update()

    def clear_latest_pitch(self) -> None:
        """Clear the latest pitch marker."""
        self._latest_pitch = None
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the strike zone overlay."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Calculate strike zone pixel coordinates
        zone_left_px = int(width * self._zone_left)
        zone_right_px = int(width * self._zone_right)
        zone_top_px = int(height * self._zone_top)
        zone_bottom_px = int(height * self._zone_bottom)
        zone_width = zone_right_px - zone_left_px
        zone_height = zone_bottom_px - zone_top_px

        # Draw strike zone border (green)
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.green, 3))
        painter.drawRect(zone_left_px, zone_top_px, zone_width, zone_height)

        # Draw 3x3 grid (lighter green)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 255, 0, 128), 2))

        # Vertical lines
        for i in range(1, 3):
            x = zone_left_px + (zone_width * i / 3)
            painter.drawLine(int(x), zone_top_px, int(x), zone_bottom_px)

        # Horizontal lines
        for i in range(1, 3):
            y = zone_top_px + (zone_height * i / 3)
            painter.drawLine(zone_left_px, int(y), zone_right_px, int(y))

        # Draw latest pitch location
        if self._latest_pitch:
            pitch_x, pitch_y = self._latest_pitch
            px = int(width * pitch_x)
            py = int(height * pitch_y)

            # Draw pitch marker (red circle)
            painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.red, 2))
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 180)))
            painter.drawEllipse(px - 8, py - 8, 16, 16)

        # Draw label
        painter.setPen(QtCore.Qt.GlobalColor.green)
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            zone_left_px + 5, zone_top_px + 20,
            "STRIKE ZONE"
        )


__all__ = ["HeatMapWidget", "StrikeZoneOverlay"]

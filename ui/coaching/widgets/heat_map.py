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


class TrajectoryWidget(QtWidgets.QWidget):
    """Trajectory visualization widget showing pitch path from release to plate.

    Displays a 2D side view (Y-Z plane) with:
    - Mound and plate positions
    - Pitch trajectories (last 5 pitches)
    - Release point and plate crossing
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(300, 200)

        # Trajectory data: list of (y_positions, z_positions) tuples
        self._trajectories: list[tuple[list[float], list[float]]] = []
        self._max_trajectories = 5

        # Field dimensions (in feet)
        self._mound_y = 60.5  # Distance from plate to mound
        self._plate_y = 0.0
        self._ground_z = 0.0

    def add_trajectory(self, y_positions: list[float], z_positions: list[float]) -> None:
        """Add a trajectory to display.

        Args:
            y_positions: Y coordinates in feet (distance from plate)
            z_positions: Z coordinates in feet (height above ground)
        """
        if len(y_positions) != len(z_positions) or len(y_positions) == 0:
            return

        # Add trajectory (keep last N)
        self._trajectories.append((y_positions, z_positions))
        if len(self._trajectories) > self._max_trajectories:
            self._trajectories.pop(0)

        self.update()

    def clear(self) -> None:
        """Clear all trajectories."""
        self._trajectories.clear()
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the trajectory view."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Set up coordinate system
        # Y: 0 (plate) to 70 feet (past mound)
        # Z: 0 (ground) to 10 feet (above ground)
        margin = 20
        plot_width = width - 2 * margin
        plot_height = height - 2 * margin

        y_min, y_max = -5, 70  # feet
        z_min, z_max = 0, 10  # feet

        def to_screen_x(y_ft: float) -> int:
            """Convert Y coordinate (feet) to screen X.

            TV broadcast view: Plate (0 ft) on RIGHT, Mound (60 ft) on LEFT.
            """
            norm = (y_ft - y_min) / (y_max - y_min)
            # Inverted: plate (0) → right, mound (60) → left
            return int(width - margin - norm * plot_width)

        def to_screen_y(z_ft: float) -> int:
            """Convert Z coordinate (feet) to screen Y (inverted)."""
            norm = (z_ft - z_min) / (z_max - z_min)
            return int(height - margin - norm * plot_height)

        # Draw background
        painter.fillRect(0, 0, width, height, QtGui.QColor(240, 240, 240))

        # Draw ground line
        ground_y = to_screen_y(0)
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.darkGreen, 2))
        painter.drawLine(margin, ground_y, width - margin, ground_y)

        # Draw mound
        mound_x = to_screen_x(self._mound_y)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(139, 69, 19)))
        painter.drawEllipse(mound_x - 10, ground_y - 10, 20, 10)

        # Draw plate
        plate_x = to_screen_x(self._plate_y)
        painter.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.white))
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black, 2))
        plate_points = [
            QtCore.QPoint(plate_x - 8, ground_y),
            QtCore.QPoint(plate_x + 8, ground_y),
            QtCore.QPoint(plate_x + 8, ground_y - 8),
            QtCore.QPoint(plate_x, ground_y - 12),
            QtCore.QPoint(plate_x - 8, ground_y - 8),
        ]
        painter.drawPolygon(plate_points)

        # Draw strike zone at plate
        strike_zone_bottom = to_screen_y(1.5)  # ~18 inches
        strike_zone_top = to_screen_y(3.5)  # ~42 inches
        strike_zone_width = 20
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.blue, 2))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRect(
            plate_x - strike_zone_width // 2,
            strike_zone_top,
            strike_zone_width,
            strike_zone_bottom - strike_zone_top,
        )

        # Draw trajectories
        if self._trajectories:
            # Oldest to newest (so newest is on top)
            for i, (y_pos, z_pos) in enumerate(self._trajectories):
                # Fade older trajectories
                alpha = int(100 + (155 * i / max(1, len(self._trajectories) - 1)))
                color = QtGui.QColor(255, 0, 0, alpha)
                painter.setPen(QtGui.QPen(color, 2))

                # Draw trajectory line
                points = []
                for y, z in zip(y_pos, z_pos):
                    points.append(QtCore.QPoint(to_screen_x(y), to_screen_y(z)))

                if len(points) >= 2:
                    painter.drawPolyline(points)

                    # Draw release point (first point)
                    painter.setBrush(QtGui.QBrush(color))
                    painter.drawEllipse(points[0], 4, 4)

                    # Draw plate crossing (last point)
                    painter.drawEllipse(points[-1], 5, 5)

        # Draw labels
        painter.setPen(QtCore.Qt.GlobalColor.black)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        # Mound label
        painter.drawText(mound_x - 20, ground_y + 15, "Mound")

        # Plate label
        painter.drawText(plate_x - 15, ground_y + 15, "Plate")

        # Distance markers
        for dist in [20, 40, 60]:
            x = to_screen_x(dist)
            painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.gray, 1, QtCore.Qt.PenStyle.DashLine))
            painter.drawLine(x, margin, x, height - margin)
            painter.setPen(QtCore.Qt.GlobalColor.gray)
            painter.drawText(x - 10, height - 5, f"{dist}'")


__all__ = ["HeatMapWidget", "StrikeZoneOverlay", "TrajectoryWidget"]

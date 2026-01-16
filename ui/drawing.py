"""Drawing functions for rendering frames with overlays."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui

from detect.fiducials import FiducialDetection
from ui.geometry import Rect, Overlay


def frame_to_pixmap(
    image: np.ndarray,
    overlays: list[Overlay] | None = None,
    detections: list | None = None,
    lane_detections: list | None = None,
    plate_detections: list | None = None,
    plate_rect: Optional[Rect] = None,
    zone: tuple[int, int] | None = None,
    trail: list[tuple[int, int]] | None = None,
    checkerboard: list[tuple[float, float]] | None = None,
    fiducials: list[FiducialDetection] | None = None,
) -> QtGui.QPixmap:
    """Convert numpy array frame to QPixmap with overlays.

    Args:
        image: Grayscale or RGB image
        overlays: List of (rect, color) tuples for ROI overlays
        detections: Ball detections (red)
        lane_detections: Lane-filtered detections (cyan)
        plate_detections: Plate-filtered detections (orange)
        plate_rect: Plate rectangle for grid overlay
        zone: Strike zone cell (row, col) to highlight
        trail: Trajectory trail points
        checkerboard: Checkerboard corner points
        fiducials: AprilTag fiducial detections

    Returns:
        QPixmap ready for display
    """
    # Convert numpy array to QImage
    if image.ndim == 2:
        # Grayscale
        height, width = image.shape
        qimage = QtGui.QImage(
            image.data,
            width,
            height,
            image.strides[0],
            QtGui.QImage.Format_Grayscale8,
        )
    else:
        # RGB
        height, width, _ = image.shape
        rgb = image[..., ::-1].copy()  # BGR to RGB
        qimage = QtGui.QImage(
            rgb.data,
            width,
            height,
            rgb.strides[0],
            QtGui.QImage.Format_RGB888,
        )

    pixmap = QtGui.QPixmap.fromImage(qimage)

    # Draw overlays if any
    needs_painting = overlays or detections or lane_detections or plate_detections or plate_rect or zone or trail
    if needs_painting:
        painter = QtGui.QPainter(pixmap)

        # Draw ROI rectangles
        if overlays:
            for rect, color in overlays:
                painter.setPen(QtGui.QPen(color, 2))
                painter.drawRect(*rect)

        # Draw detections
        draw_detections(painter, detections, QtGui.QColor(255, 0, 0))
        draw_detections(painter, lane_detections, QtGui.QColor(0, 200, 255))
        draw_detections(painter, plate_detections, QtGui.QColor(255, 180, 0))

        # Draw trajectory trail
        draw_trail(painter, trail, QtGui.QColor(0, 255, 100))

        # Draw calibration targets
        draw_checkerboard(painter, checkerboard)
        draw_fiducials(painter, fiducials)

        # Draw strike zone grid
        if plate_rect:
            draw_plate_grid(painter, plate_rect, QtGui.QColor(255, 180, 0), zone)

        painter.end()

    return pixmap


def draw_detections(
    painter: QtGui.QPainter,
    detections: list | None,
    color: QtGui.QColor,
) -> None:
    """Draw ball detection ellipses.

    Args:
        painter: QPainter instance
        detections: List of detections with u, v, radius_px attributes
        color: Circle color
    """
    if not detections:
        return

    painter.setPen(QtGui.QPen(color, 2))
    for det in detections:
        radius = max(2, int(det.radius_px))
        painter.drawEllipse(
            int(det.u - radius),
            int(det.v - radius),
            int(radius * 2),
            int(radius * 2),
        )


def draw_checkerboard(
    painter: QtGui.QPainter,
    corners: list[tuple[float, float]] | None,
) -> None:
    """Draw checkerboard calibration pattern corners.

    Args:
        painter: QPainter instance
        corners: List of (x, y) corner coordinates
    """
    if not corners:
        return

    painter.setPen(QtGui.QPen(QtGui.QColor(0, 220, 0), 2))
    for x, y in corners:
        painter.drawEllipse(int(x) - 2, int(y) - 2, 4, 4)


def draw_fiducials(
    painter: QtGui.QPainter,
    detections: list[FiducialDetection] | None,
) -> None:
    """Draw AprilTag fiducial markers.

    Args:
        painter: QPainter instance
        detections: List of FiducialDetection objects
    """
    if not detections:
        return

    for det in detections:
        # Color based on tag ID (plate=orange, rubber=cyan)
        color = QtGui.QColor(255, 180, 0) if det.tag_id == 0 else QtGui.QColor(0, 200, 255)
        painter.setPen(QtGui.QPen(color, 2))

        # Draw quadrilateral outline
        pts = det.corners
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Label with tag ID
        painter.drawText(int(pts[0][0]), int(pts[0][1]) - 4, f"id {det.tag_id}")


def draw_plate_grid(
    painter: QtGui.QPainter,
    rect: Rect,
    color: QtGui.QColor,
    zone: tuple[int, int] | None,
) -> None:
    """Draw 3x3 strike zone grid on plate rectangle.

    Args:
        painter: QPainter instance
        rect: Plate rectangle (x1, y1, x2, y2)
        color: Grid line color
        zone: Optional (row, col) cell to highlight (1-indexed)
    """
    x1, y1, x2, y2 = rect
    width = x2 - x1
    height = y2 - y1

    if width <= 0 or height <= 0:
        return

    # Highlight specific zone cell if provided
    if zone is not None:
        row, col = zone
        col_index = max(1, min(3, col)) - 1  # Clamp to 0-2
        row_index = max(1, min(3, row)) - 1
        cell_w = width / 3.0
        cell_h = height / 3.0

        # Invert row for Qt coordinate system (top=0)
        row_from_top = 2 - row_index

        # Calculate cell bounds
        cell_x1 = x1 + int(cell_w * col_index)
        cell_y1 = y1 + int(cell_h * row_from_top)
        cell_x2 = x1 + int(cell_w * (col_index + 1))
        cell_y2 = y1 + int(cell_h * (row_from_top + 1))

        # Fill with translucent color
        brush = QtGui.QBrush(QtGui.QColor(255, 180, 0, 60))
        painter.fillRect(
            QtCore.QRect(cell_x1, cell_y1, cell_x2 - cell_x1, cell_y2 - cell_y1),
            brush,
        )

    # Draw 3x3 grid lines
    painter.setPen(QtGui.QPen(color, 1, QtCore.Qt.DashLine))
    for i in range(1, 3):
        x = x1 + int(width * i / 3.0)
        y = y1 + int(height * i / 3.0)
        painter.drawLine(x, y1, x, y2)  # Vertical line
        painter.drawLine(x1, y, x2, y)  # Horizontal line


def draw_trail(
    painter: QtGui.QPainter,
    trail: list[tuple[int, int]] | None,
    color: QtGui.QColor,
) -> None:
    """Draw ball trajectory trail.

    Args:
        painter: QPainter instance
        trail: List of (x, y) points
        color: Trail line color
    """
    if not trail or len(trail) < 2:
        return

    painter.setPen(QtGui.QPen(color, 2))
    for i in range(1, len(trail)):
        x1, y1 = trail[i - 1]
        x2, y2 = trail[i]
        painter.drawLine(x1, y1, x2, y2)


__all__ = [
    "frame_to_pixmap",
    "draw_detections",
    "draw_checkerboard",
    "draw_fiducials",
    "draw_plate_grid",
    "draw_trail",
]

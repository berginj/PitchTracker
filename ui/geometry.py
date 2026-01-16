"""Geometry helper functions for UI components."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui

# Type aliases
Rect = tuple[int, int, int, int]
Overlay = tuple[Rect, QtGui.QColor]


def points_to_rect(start: QtCore.QPoint, end: QtCore.QPoint) -> Optional[Rect]:
    """Convert two points to a rectangle.

    Args:
        start: Starting point
        end: Ending point

    Returns:
        Rectangle (x1, y1, x2, y2) or None if points form a line
    """
    x1 = start.x()
    y1 = start.y()
    x2 = end.x()
    y2 = end.y()
    if x1 == x2 or y1 == y2:
        return None
    return (x1, y1, x2, y2)


def normalize_rect(rect: Rect, image_size: Optional[tuple[int, int]]) -> Optional[Rect]:
    """Normalize rectangle to image bounds.

    Args:
        rect: Rectangle to normalize (x1, y1, x2, y2)
        image_size: Image dimensions (width, height)

    Returns:
        Normalized rectangle or None if too small or invalid
    """
    if image_size is None:
        return None
    width, height = image_size
    x1, y1, x2, y2 = rect
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    x1 = max(0, min(x1, width - 1))
    x2 = max(0, min(x2, width - 1))
    y1 = max(0, min(y1, height - 1))
    y2 = max(0, min(y2, height - 1))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    return (x1, y1, x2, y2)


def rect_to_polygon(rect: Optional[Rect]) -> list[tuple[int, int]] | None:
    """Convert rectangle to polygon (4 corners).

    Args:
        rect: Rectangle (x1, y1, x2, y2)

    Returns:
        List of 4 corner points or None
    """
    if rect is None:
        return None
    x1, y1, x2, y2 = rect
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def polygon_to_rect(polygon: Optional[list[tuple[int, int]]]) -> Optional[Rect]:
    """Convert polygon to bounding rectangle.

    Args:
        polygon: List of points

    Returns:
        Bounding rectangle (x1, y1, x2, y2) or None
    """
    if not polygon:
        return None
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def roi_overlays(
    lane_rect: Optional[Rect],
    plate_rect: Optional[Rect],
    active_rect: Optional[Rect],
) -> list[Overlay]:
    """Build list of ROI overlays with colors.

    Args:
        lane_rect: Lane ROI rectangle
        plate_rect: Plate ROI rectangle
        active_rect: Currently active/drawing rectangle

    Returns:
        List of (rect, color) tuples for rendering
    """
    overlays: list[Overlay] = []
    if lane_rect:
        overlays.append((lane_rect, QtGui.QColor(0, 200, 255)))
    if plate_rect:
        overlays.append((plate_rect, QtGui.QColor(255, 180, 0)))
    if active_rect:
        overlays.append((active_rect, QtGui.QColor(0, 255, 0)))
    return overlays


__all__ = [
    "Rect",
    "Overlay",
    "points_to_rect",
    "normalize_rect",
    "rect_to_polygon",
    "polygon_to_rect",
    "roi_overlays",
]

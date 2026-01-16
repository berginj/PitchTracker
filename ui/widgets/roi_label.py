"""Custom QLabel widget for interactive ROI drawing."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.geometry import Rect, points_to_rect


class RoiLabel(QtWidgets.QLabel):
    """Interactive label widget for drawing ROI rectangles with mouse.

    Supports click-and-drag rectangle selection with live preview.
    Maps widget coordinates to image coordinates accounting for scaling.
    """

    def __init__(self, on_rect_update: Callable[[Rect, bool], None]) -> None:
        """Initialize ROI label.

        Args:
            on_rect_update: Callback function (rect, is_final) called during/after drawing
        """
        super().__init__()
        self._on_rect_update = on_rect_update
        self._mode: Optional[str] = None
        self._start: Optional[QtCore.QPoint] = None
        self._image_size: Optional[tuple[int, int]] = None

    def set_mode(self, mode: Optional[str]) -> None:
        """Set drawing mode (enables/disables interaction).

        Args:
            mode: Mode identifier string or None to disable
        """
        self._mode = mode

    def set_image_size(self, width: int, height: int) -> None:
        """Set the underlying image dimensions for coordinate mapping.

        Args:
            width: Image width in pixels
            height: Image height in pixels
        """
        self._image_size = (width, height)

    def image_size(self) -> Optional[tuple[int, int]]:
        """Get the stored image dimensions.

        Returns:
            (width, height) tuple or None if not set
        """
        return self._image_size

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse press to start rectangle drawing.

        Args:
            event: Mouse event
        """
        if self._mode is None or self._image_size is None:
            return
        if event.button() == QtCore.Qt.LeftButton:
            self._start = event.position().toPoint()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse move to update rectangle preview.

        Args:
            event: Mouse event
        """
        if self._start is None or self._image_size is None:
            return

        current = event.position().toPoint()
        start = self._map_point(self._start)
        end = self._map_point(current)
        rect = points_to_rect(start, end)

        if rect:
            self._on_rect_update(rect, False)  # Preview (not final)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse release to finalize rectangle.

        Args:
            event: Mouse event
        """
        if self._start is None or self._image_size is None:
            return

        if event.button() == QtCore.Qt.LeftButton:
            end = event.position().toPoint()
            start = self._map_point(self._start)
            end = self._map_point(end)
            rect = points_to_rect(start, end)

            if rect:
                self._on_rect_update(rect, True)  # Final

        self._start = None

    def _map_point(self, point: QtCore.QPoint) -> QtCore.QPoint:
        """Map widget coordinates to image coordinates.

        Accounts for label scaling (image may be stretched/shrunk to fit label).

        Args:
            point: Point in widget coordinates

        Returns:
            Point in image coordinates
        """
        if self._image_size is None:
            return point

        label_w = max(self.width(), 1)
        label_h = max(self.height(), 1)
        img_w, img_h = self._image_size

        # Scale from label dimensions to image dimensions
        x = int(point.x() * img_w / label_w)
        y = int(point.y() * img_h / label_h)

        return QtCore.QPoint(x, y)


__all__ = ["RoiLabel"]

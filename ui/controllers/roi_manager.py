"""ROI (Region of Interest) management controller.

Extracted from MainWindow to reduce god class complexity.
Manages lane and plate ROI drawing, saving, and loading.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable, Tuple, TYPE_CHECKING

from PySide6 import QtWidgets

from configs.lane_io import load_lane_rois, save_lane_rois
from configs.roi_io import load_rois, save_rois
from detect.lane import LaneRoi
from ui.geometry import Rect, normalize_rect, polygon_to_rect, rect_to_polygon
from log_config.logger import get_logger

if TYPE_CHECKING:
    from ui.widgets import RoiLabel

logger = get_logger(__name__)


class RoiManager:
    """Manages ROI drawing, saving, and loading.

    Responsibilities:
    - Tracking ROI mode (lane, plate, lane_right)
    - Managing ROI rectangles (lane, plate, lane_right)
    - Saving and loading ROIs to/from files
    - Coordinating between left and right camera views
    """

    def __init__(
        self,
        roi_path: Path,
        lane_path: Path,
        left_view: "RoiLabel",
        right_view: "RoiLabel",
        status_label: QtWidgets.QLabel,
        get_camera_serials: Callable[[], Tuple[Optional[str], Optional[str]]],
    ):
        """Initialize ROI manager.

        Args:
            roi_path: Path to ROI configuration file
            lane_path: Path to lane ROI configuration file
            left_view: Left camera view widget
            right_view: Right camera view widget
            status_label: Label for status messages
            get_camera_serials: Callback to get (left_serial, right_serial)
        """
        self._roi_path = roi_path
        self._lane_path = lane_path
        self._left_view = left_view
        self._right_view = right_view
        self._status_label = status_label
        self._get_camera_serials = get_camera_serials

        # ROI state
        self._roi_mode: Optional[str] = None
        self._lane_rect: Optional[Rect] = None
        self._lane_rect_right: Optional[Rect] = None
        self._plate_rect: Optional[Rect] = None
        self._active_rect: Optional[Rect] = None

        logger.debug(f"RoiManager initialized with roi_path={roi_path}, lane_path={lane_path}")

    # Properties for accessing ROI state
    @property
    def roi_mode(self) -> Optional[str]:
        """Get current ROI drawing mode."""
        return self._roi_mode

    @property
    def lane_rect(self) -> Optional[Rect]:
        """Get left lane ROI rectangle."""
        return self._lane_rect

    @property
    def lane_rect_right(self) -> Optional[Rect]:
        """Get right lane ROI rectangle."""
        return self._lane_rect_right

    @property
    def plate_rect(self) -> Optional[Rect]:
        """Get plate ROI rectangle."""
        return self._plate_rect

    @property
    def active_rect(self) -> Optional[Rect]:
        """Get currently drawing rectangle (not finalized)."""
        return self._active_rect

    @lane_rect_right.setter
    def lane_rect_right(self, value: Optional[Rect]) -> None:
        """Set right lane ROI rectangle."""
        self._lane_rect_right = value

    def set_roi_mode(self, mode: str) -> None:
        """Set the ROI drawing mode.

        Args:
            mode: ROI mode ('lane', 'plate', 'lane_right', or None)
        """
        self._roi_mode = mode
        logger.info(f"Setting ROI mode: {mode}")

        if mode == "lane_right":
            self._left_view.set_mode(None)
            self._right_view.set_mode(mode)
            self._status_label.setText("ROI mode: lane_right (drag rectangle on right view)")
        else:
            self._left_view.set_mode(mode)
            self._right_view.set_mode(None)
            self._status_label.setText(f"ROI mode: {mode} (drag rectangle on left view)")

    def on_rect_update(self, rect: Rect, final: bool) -> None:
        """Handle rectangle update from left view.

        Args:
            rect: Rectangle coordinates (x1, y1, x2, y2)
            final: True if drawing is complete, False if still dragging
        """
        rect = normalize_rect(rect, self._left_view.image_size())
        if rect is None:
            return

        if final:
            if self._roi_mode == "lane":
                self._lane_rect = rect
                logger.debug(f"Lane ROI set: {rect}")
            elif self._roi_mode == "plate":
                self._plate_rect = rect
                logger.debug(f"Plate ROI set: {rect}")
            self._active_rect = None
        else:
            self._active_rect = rect

    def on_right_rect_update(self, rect: Rect, final: bool) -> None:
        """Handle rectangle update from right view.

        Args:
            rect: Rectangle coordinates (x1, y1, x2, y2)
            final: True if drawing is complete, False if still dragging
        """
        rect = normalize_rect(rect, self._right_view.image_size())
        if rect is None:
            return

        if final:
            if self._roi_mode == "lane_right":
                self._lane_rect_right = rect
                logger.debug(f"Right lane ROI set: {rect}")
            self._active_rect = None
        else:
            self._active_rect = rect

    def clear_lane(self) -> None:
        """Clear lane ROI for both views."""
        self._lane_rect = None
        self._lane_rect_right = None
        self._status_label.setText("Lane ROI cleared.")
        logger.info("Lane ROI cleared")

    def clear_plate(self) -> None:
        """Clear plate ROI."""
        self._plate_rect = None
        self._status_label.setText("Plate ROI cleared.")
        logger.info("Plate ROI cleared")

    def save_rois(self) -> None:
        """Save ROIs to configuration files."""
        lane_poly = rect_to_polygon(self._lane_rect)
        lane_right_poly = rect_to_polygon(self._lane_rect_right) if self._lane_rect_right else None
        plate_poly = rect_to_polygon(self._plate_rect)

        # Save main ROI file
        save_rois(self._roi_path, lane_poly, plate_poly)
        logger.info(f"Saved ROIs to {self._roi_path}")

        # Save per-camera lane ROIs
        if lane_poly is not None:
            left_serial, right_serial = self._get_camera_serials()
            left_id = left_serial or "left"
            right_id = right_serial or "right"
            lane_rois = {
                left_id: LaneRoi(polygon=lane_poly),
                right_id: LaneRoi(polygon=lane_right_poly or lane_poly),
            }
            save_lane_rois(self._lane_path, lane_rois)
            logger.info(f"Saved lane ROIs to {self._lane_path}")

        self._status_label.setText("ROIs saved.")

    def load_rois(self) -> None:
        """Load ROIs from configuration files."""
        # Load main ROI file
        rois = load_rois(self._roi_path)
        self._lane_rect = polygon_to_rect(rois.get("lane"))
        self._plate_rect = polygon_to_rect(rois.get("plate"))
        self._lane_rect_right = None

        # Load per-camera lane ROIs
        lane_rois = load_lane_rois(self._lane_path)
        left_serial, right_serial = self._get_camera_serials()
        left_id = left_serial or "left"
        right_id = right_serial or "right"

        if lane_rois:
            left_lane = lane_rois.get(left_id) or lane_rois.get("left")
            right_lane = lane_rois.get(right_id) or lane_rois.get("right")
            if left_lane:
                self._lane_rect = polygon_to_rect(left_lane.polygon)
            if right_lane:
                self._lane_rect_right = polygon_to_rect(right_lane.polygon)

        if self._lane_rect or self._plate_rect:
            self._status_label.setText("ROIs loaded.")
            logger.info(f"Loaded ROIs: lane={self._lane_rect is not None}, plate={self._plate_rect is not None}")
        else:
            logger.debug("No ROIs found to load")

    def propose_right_lane(
        self,
        parent: QtWidgets.QWidget,
        left_frame_size: Optional[Tuple[int, int]],
        right_frame_size: Optional[Tuple[int, int]],
    ) -> bool:
        """Propose right lane ROI based on left lane position.

        Args:
            parent: Parent widget for message boxes
            left_frame_size: (width, height) of left frame, or None
            right_frame_size: (width, height) of right frame, or None

        Returns:
            True if right lane was proposed, False otherwise
        """
        if self._lane_rect is None:
            QtWidgets.QMessageBox.information(
                parent,
                "Propose Right Lane",
                "Draw the left lane ROI first.",
            )
            return False

        if left_frame_size is None or right_frame_size is None:
            QtWidgets.QMessageBox.warning(
                parent,
                "Propose Right Lane",
                "Start capture before proposing the right lane.",
            )
            return False

        left_w, left_h = left_frame_size
        right_w, right_h = right_frame_size

        # Normalize left lane coordinates and apply to right frame
        x1, y1, x2, y2 = self._lane_rect
        nx1 = x1 / max(left_w, 1)
        ny1 = y1 / max(left_h, 1)
        nx2 = x2 / max(left_w, 1)
        ny2 = y2 / max(left_h, 1)

        rx1 = int(nx1 * right_w)
        ry1 = int(ny1 * right_h)
        rx2 = int(nx2 * right_w)
        ry2 = int(ny2 * right_h)

        self._lane_rect_right = (rx1, ry1, rx2, ry2)
        self._status_label.setText("Right lane proposed. Adjust if needed and save.")
        logger.info(f"Proposed right lane ROI: {self._lane_rect_right}")
        return True

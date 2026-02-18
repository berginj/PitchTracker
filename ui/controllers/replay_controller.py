"""Video replay management controller.

Extracted from MainWindow to reduce god class complexity.
Manages video replay, frame stepping, and detection visualization.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

import cv2
from PySide6 import QtWidgets, QtGui

from contracts import Frame
from detect.config import Mode, FilterConfig, DetectorConfig as CvDetectorConfig
from detect.classical_detector import ClassicalDetector
from ui.drawing import frame_to_pixmap
from ui.geometry import Rect, roi_overlays, rect_to_polygon
from log_config.logger import get_logger

if TYPE_CHECKING:
    from configs.settings import AppConfig
    from ui.widgets import RoiLabel

logger = get_logger(__name__)


class ReplayController:
    """Manages video replay and frame-by-frame analysis.

    Responsibilities:
    - Opening and playing video files
    - Frame-by-frame stepping
    - Running detection on replay frames
    - Rendering detection trail overlay
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        left_view: "RoiLabel",
        right_view: "RoiLabel",
        status_label: QtWidgets.QLabel,
        get_config: Callable[[], "AppConfig"],
        get_lane_rect: Callable[[], Optional[Rect]],
        get_plate_rect: Callable[[], Optional[Rect]],
        get_active_rect: Callable[[], Optional[Rect]],
        stop_capture: Callable[[], None],
        start_timer: Callable[[int], None],
    ):
        """Initialize replay controller.

        Args:
            parent: Parent widget for dialogs
            left_view: Left camera view widget
            right_view: Right camera view widget
            status_label: Label for status messages
            get_config: Callback to get current config
            get_lane_rect: Callback to get lane ROI
            get_plate_rect: Callback to get plate ROI
            get_active_rect: Callback to get active drawing rect
            stop_capture: Callback to stop live capture
            start_timer: Callback to start refresh timer (takes ms interval)
        """
        self._parent = parent
        self._left_view = left_view
        self._right_view = right_view
        self._status_label = status_label
        self._get_config = get_config
        self._get_lane_rect = get_lane_rect
        self._get_plate_rect = get_plate_rect
        self._get_active_rect = get_active_rect
        self._stop_capture = stop_capture
        self._start_timer = start_timer

        # Replay state
        self._replay_capture: Optional[cv2.VideoCapture] = None
        self._replay_frame_index: int = 0
        self._replay_trail: deque[tuple[int, int]] = deque(maxlen=30)
        self._replay_detector: Optional[ClassicalDetector] = None
        self._replay_paused: bool = False

        logger.debug("ReplayController initialized")

    @property
    def is_active(self) -> bool:
        """Check if replay is currently active."""
        return self._replay_capture is not None

    @property
    def is_paused(self) -> bool:
        """Check if replay is paused."""
        return self._replay_paused

    def start_replay(self) -> bool:
        """Start video replay from a file.

        Opens a file dialog and starts replay if a valid file is selected.

        Returns:
            True if replay started successfully, False otherwise
        """
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._parent,
            "Select left camera video",
            str(Path("recordings")),
            "Video Files (*.avi *.mp4)",
        )
        if not path:
            logger.debug("Replay cancelled - no file selected")
            return False

        logger.info(f"Starting replay: {path}")

        # Stop any active capture
        self._stop_capture()

        # Open video
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            logger.warning(f"Failed to open replay video: {path}")
            self._status_label.setText("Failed to open replay video.")
            return False

        self._replay_capture = capture
        self._replay_frame_index = 0
        self._replay_trail.clear()
        self._init_replay_detector()
        self._replay_paused = False

        # Start refresh timer
        config = self._get_config()
        refresh_ms = int(1000 / max(config.ui.refresh_hz, 1))
        self._start_timer(refresh_ms)

        self._status_label.setText("Replay mode.")
        logger.info("Replay started successfully")
        return True

    def stop_replay(self) -> None:
        """Stop current replay and release resources."""
        if self._replay_capture is not None:
            logger.info("Stopping replay")
            self._replay_capture.release()
            self._replay_capture = None

        self._replay_frame_index = 0
        self._replay_trail.clear()
        self._replay_detector = None

    def _init_replay_detector(self) -> None:
        """Initialize detector for replay frames."""
        config = self._get_config()
        cfg = config.detector

        filter_cfg = FilterConfig(
            min_area=cfg.filters.min_area,
            max_area=cfg.filters.max_area,
            min_circularity=cfg.filters.min_circularity,
            max_circularity=cfg.filters.max_circularity,
            min_velocity=cfg.filters.min_velocity,
            max_velocity=cfg.filters.max_velocity,
        )

        detector_cfg = CvDetectorConfig(
            frame_diff_threshold=cfg.frame_diff_threshold,
            bg_diff_threshold=cfg.bg_diff_threshold,
            bg_alpha=cfg.bg_alpha,
            edge_threshold=cfg.edge_threshold,
            blob_threshold=cfg.blob_threshold,
            runtime_budget_ms=cfg.runtime_budget_ms,
            crop_padding_px=cfg.crop_padding_px,
            min_consecutive=cfg.min_consecutive,
            filters=filter_cfg,
        )

        roi_by_camera = None
        lane_rect = self._get_lane_rect()
        if lane_rect:
            roi_by_camera = {"replay_left": rect_to_polygon(lane_rect)}

        self._replay_detector = ClassicalDetector(
            config=detector_cfg,
            mode=Mode(cfg.mode),
            roi_by_camera=roi_by_camera,
        )
        logger.debug("Replay detector initialized")

    def update_replay(self) -> bool:
        """Update replay with next frame.

        Returns:
            True if frame was processed, False if replay ended or not active
        """
        if self._replay_capture is None:
            return False

        if self._replay_paused:
            return False

        ok, frame = self._replay_capture.read()
        if not ok:
            logger.info("Replay finished")
            self._status_label.setText("Replay finished.")
            self.stop_replay()
            return False

        self._replay_frame_index += 1
        height, width = frame.shape[:2]

        # Convert to grayscale if needed
        config = self._get_config()
        if config.camera.pixfmt == "GRAY8":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # Create frame object for detector
        frame_obj = Frame(
            camera_id="replay_left",
            frame_index=self._replay_frame_index,
            t_capture_monotonic_ns=0,
            image=gray,
            width=width,
            height=height,
            pixfmt=config.camera.pixfmt,
        )

        # Run detection
        detections = []
        if self._replay_detector is not None:
            detections = self._replay_detector.detect(frame_obj)

        # Update trail with best detection
        if detections:
            best = max(detections, key=lambda det: det.confidence)
            self._replay_trail.append((int(best.u), int(best.v)))

        # Render frame
        overlays = roi_overlays(
            self._get_lane_rect(),
            self._get_plate_rect(),
            self._get_active_rect(),
        )

        pixmap = frame_to_pixmap(
            gray,
            overlays,
            detections,
            lane_detections=[],
            plate_detections=[],
            plate_rect=self._get_plate_rect(),
            zone=None,
            trail=list(self._replay_trail),
        )

        self._left_view.setPixmap(pixmap)
        self._right_view.setPixmap(QtGui.QPixmap())

        return True

    def toggle_pause(self) -> None:
        """Toggle replay pause state."""
        if self._replay_capture is None:
            return

        self._replay_paused = not self._replay_paused
        status = "Replay paused." if self._replay_paused else "Replay mode."
        self._status_label.setText(status)
        logger.debug(f"Replay pause toggled: {self._replay_paused}")

    def step_frame(self) -> None:
        """Advance replay by one frame (when paused)."""
        if self._replay_capture is None:
            return

        self._replay_paused = True
        # Temporarily unpause to process one frame
        self._replay_paused = False
        self.update_replay()
        self._replay_paused = True
        logger.debug(f"Stepped to frame {self._replay_frame_index}")

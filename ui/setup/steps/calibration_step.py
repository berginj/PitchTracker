"""Step 2: Stereo Calibration - Capture ChArUco board images and calibrate."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PySide6 import QtCore, QtWidgets

from capture import CameraDevice
from log_config.logger import get_logger
from ui.setup.steps.base_step import BaseStep
from ui.setup.steps.calibration_step_alignment import CalibrationStepAlignmentMixin
from ui.setup.steps.calibration_step_alignment_compare import CalibrationStepAlignmentCompareMixin
from ui.setup.steps.calibration_step_alignment_history import CalibrationStepAlignmentHistoryMixin
from ui.setup.steps.calibration_step_alignment_presets import CalibrationStepAlignmentPresetsMixin
from ui.setup.steps.calibration_step_alignment_reports import CalibrationStepAlignmentReportsMixin
from ui.setup.steps.calibration_step_calibration_run import CalibrationStepCalibrationRunMixin
from ui.setup.steps.calibration_step_camera_adjustments import CalibrationStepCameraAdjustmentsMixin
from ui.setup.steps.calibration_step_camera_analysis import CalibrationStepCameraAnalysisMixin
from ui.setup.steps.calibration_step_camera_runtime import CalibrationStepCameraRuntimeMixin
from ui.setup.steps.calibration_step_charuco_detection import CalibrationStepCharucoDetectionMixin
from ui.setup.steps.calibration_step_layout import CalibrationStepLayoutMixin
from ui.setup.steps.calibration_step_lifecycle import CalibrationStepLifecycleMixin
from ui.setup.steps.calibration_step_panels import CalibrationStepPanelsMixin
from ui.setup.steps.calibration_step_preview_capture import CalibrationStepPreviewCaptureMixin
from ui.setup.steps.calibration_step_status import CalibrationStepStatusMixin
from ui.themes import (
    get_style_manager,
)

logger = get_logger(__name__)


class CalibrationStep(
    CalibrationStepStatusMixin,
    CalibrationStepLayoutMixin,
    CalibrationStepPanelsMixin,
    CalibrationStepLifecycleMixin,
    CalibrationStepCameraAdjustmentsMixin,
    CalibrationStepCameraAnalysisMixin,
    CalibrationStepCameraRuntimeMixin,
    CalibrationStepPreviewCaptureMixin,
    CalibrationStepCharucoDetectionMixin,
    CalibrationStepAlignmentMixin,
    CalibrationStepCalibrationRunMixin,
    CalibrationStepAlignmentHistoryMixin,
    CalibrationStepAlignmentReportsMixin,
    CalibrationStepAlignmentPresetsMixin,
    CalibrationStepAlignmentCompareMixin,
    BaseStep,
):
    """Step 2: Stereo calibration with ChArUco board pattern.

    Workflow:
    1. Show live preview from both cameras
    2. Detect ChArUco board in real-time (robust to partial occlusion)
    3. Capture image pairs when user clicks "Capture"
    4. Run calibration when minimum images captured
    5. Show results and save to config
    """

    def __init__(
        self,
        backend: str = "uvc",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._theme = self._style_manager.theme
        self._backend = backend
        self._left_camera: Optional[CameraDevice] = None
        self._right_camera: Optional[CameraDevice] = None
        self._left_serial: Optional[str | int] = None  # Can be string or int from some code paths
        self._right_serial: Optional[str | int] = None  # Can be string or int from some code paths

        # Calibration settings (default board)
        self._pattern_cols = 6  # Default: 6 columns
        self._pattern_rows = 6  # Default: 6 rows
        self._square_mm = 30.0  # Default: 30mm square size
        self._min_captures = 10
        self._config_path = Path("configs/default.yaml")

        # Capture state
        self._captures: list[tuple[np.ndarray, np.ndarray]] = []
        self._temp_dir = Path("calibration/temp")
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        # Calibration results
        self._calibration_result: Optional[dict] = None

        # Alignment history tracking
        self._alignment_history: list = []  # Track alignment iterations
        self._alignment_results: Optional = None  # Current alignment results
        self._baseline_alignment: Optional = None  # Baseline from first capture (drift detection)
        self._warmup_attempts: int = 0  # Camera warmup retry counter

        # Detection optimization (prevent processing loop)
        self._cached_dict_name: Optional[str] = None  # Best dictionary found
        self._dict_scan_counter: int = 0  # Only rescan every N frames
        self._last_auto_detect_time: float = 0  # Debounce auto-detection
        self._detection_log_counter: int = 0  # Reduce log spam
        self._pattern_locked: bool = True  # Manual board settings are locked unless auto-detect is enabled
        self._user_changed_pattern: bool = False  # Track if user manually changed pattern

        # Smart calibration features
        self._show_marker_overlay: bool = True  # Show marker position indicators
        self._camera_history_file: Path = Path("configs") / "camera_history.json"  # Track camera assignments
        self._detected_patterns: list = []  # Multiple detected ChArUco patterns
        self._auto_swap_on_startup: bool = True  # Auto-check camera orientation on startup

        # Camera capability detection (Phase 3)
        self._camera_capabilities: Optional = None  # CameraCapabilities from detection
        self._calibration_mode: str = "FULL"  # "QUICK" or "FULL"
        self._camera_detection_complete: bool = False  # Track if detection ran
        self._focus_warning_state: str = "ok"  # Avoid repeated focus warnings every preview frame

        self._build_ui()

        # Preview timer
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)

__all__ = ["CalibrationStep"]

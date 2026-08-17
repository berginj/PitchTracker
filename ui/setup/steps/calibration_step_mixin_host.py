"""Typed host contract for the stereo-calibration step mixins."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional, overload

import numpy as np
from PySide6 import QtCore, QtWidgets

from analysis.camera_alignment_types import AlignmentResults
from calib.camera_capabilities import CameraCapabilities
from capture import CameraDevice
from ui.setup.steps.base_step import BaseStep
from ui.themes import GlassTheme, StyleManager


class CalibrationStepMixinHost(BaseStep):
    """Declare shared state while preserving one concrete ``BaseStep`` base."""

    _style_manager: StyleManager
    _theme: GlassTheme
    _backend: str
    _left_camera: CameraDevice | None
    _right_camera: CameraDevice | None
    _left_serial: str | int | None
    _right_serial: str | int | None
    _pattern_cols: int
    _pattern_rows: int
    _square_mm: float
    _min_captures: int
    _config_path: Path
    _captures: list[tuple[np.ndarray, np.ndarray]]
    _temp_dir: Path
    _calibration_result: dict[str, Any] | None
    _alignment_history: list[dict[str, Any]]
    _alignment_results: AlignmentResults | None
    _baseline_alignment: AlignmentResults | None
    _warmup_attempts: int
    _cached_dict_name: str | None
    _dict_scan_counter: int
    _last_auto_detect_time: float
    _detection_log_counter: int
    _pattern_locked: bool
    _user_changed_pattern: bool
    _show_marker_overlay: bool
    _camera_history_file: Path
    _detected_patterns: list[Any]
    _auto_swap_on_startup: bool
    _camera_capabilities: CameraCapabilities | None
    _calibration_mode: str
    _camera_detection_complete: bool
    _focus_warning_state: str
    _preview_timer: QtCore.QTimer

    _pattern_cols_spin: QtWidgets.QSpinBox
    _pattern_rows_spin: QtWidgets.QSpinBox
    _square_spin: QtWidgets.QDoubleSpinBox
    _auto_detect_pattern_checkbox: QtWidgets.QCheckBox
    _pattern_info_label: QtWidgets.QLabel
    _flip_left_btn: QtWidgets.QPushButton
    _flip_right_btn: QtWidgets.QPushButton
    _rotate_left_spin: QtWidgets.QDoubleSpinBox
    _rotate_right_spin: QtWidgets.QDoubleSpinBox
    _auto_correct_checkbox: QtWidgets.QCheckBox
    _baseline_spin: QtWidgets.QDoubleSpinBox
    _baseline_inches_label: QtWidgets.QLabel
    _alignment_status_label: QtWidgets.QLabel
    _quality_gauge: QtWidgets.QLabel
    _alignment_details: QtWidgets.QLabel
    _guidance_label: QtWidgets.QLabel
    _prediction_label: QtWidgets.QLabel
    _history_group: QtWidgets.QGroupBox
    _history_list: QtWidgets.QTextEdit
    _recheck_alignment_btn: QtWidgets.QPushButton
    _quick_check_btn: QtWidgets.QPushButton
    _alignment_details_btn: QtWidgets.QPushButton
    _show_features_btn: QtWidgets.QPushButton
    _export_report_btn: QtWidgets.QPushButton
    _save_preset_btn: QtWidgets.QPushButton
    _load_preset_btn: QtWidgets.QPushButton
    _compare_preset_btn: QtWidgets.QPushButton
    _instruction_label: QtWidgets.QLabel
    _camera_type_label: QtWidgets.QLabel
    _camera_stability_label: QtWidgets.QLabel
    _quick_radio: QtWidgets.QRadioButton
    _capture_count_label: QtWidgets.QLabel
    _capture_progress_bar: QtWidgets.QProgressBar
    _left_view: QtWidgets.QLabel
    _left_status: QtWidgets.QLabel
    _left_focus: QtWidgets.QLabel
    _right_view: QtWidgets.QLabel
    _right_status: QtWidgets.QLabel
    _right_focus: QtWidgets.QLabel
    _capture_button: QtWidgets.QPushButton
    _calibrate_button: QtWidgets.QPushButton
    _progress_bar: QtWidgets.QProgressBar
    _results_text: QtWidgets.QTextEdit
    _webcam_warning_label: QtWidgets.QLabel
    _webcam_warning: QtWidgets.QFrame

    def _build_ui(self) -> None:
        raise NotImplementedError

    def _build_settings_group(self) -> QtWidgets.QWidget:
        raise NotImplementedError

    def _build_alignment_widget(self) -> QtWidgets.QGroupBox:
        raise NotImplementedError

    def _on_pattern_changed(self, value: int) -> None:
        raise NotImplementedError

    def _on_square_size_changed(self, value: float) -> None:
        raise NotImplementedError

    def _on_auto_detect_toggled(self, state: int) -> None:
        raise NotImplementedError

    def _on_mode_changed(self) -> None:
        raise NotImplementedError

    def _toggle_flip(self, camera: str, checked: bool) -> None:
        raise NotImplementedError

    def _set_manual_rotation(self, camera: str, degrees: float) -> None:
        raise NotImplementedError

    def _reset_all_corrections(self) -> None:
        raise NotImplementedError

    def _swap_left_right(self, save_to_history: bool = True) -> None:
        raise NotImplementedError

    def _auto_swap_cameras(self) -> None:
        raise NotImplementedError

    def _update_baseline(self, value_ft: float) -> None:
        raise NotImplementedError

    def _set_capture_progress_state(self, count: int, *, ready: bool) -> None:
        raise NotImplementedError

    def _set_detection_status(
        self,
        label: QtWidgets.QLabel,
        *,
        detected: bool,
        waiting_text: str = "Waiting for board...",
    ) -> None:
        raise NotImplementedError

    def _set_focus_status(self, label: QtWidgets.QLabel, text: str, tone: str) -> None:
        raise NotImplementedError

    def _set_camera_type_state(self, text: str, tone: str) -> None:
        raise NotImplementedError

    def _set_camera_stability_state(self, text: str, tone: str) -> None:
        raise NotImplementedError

    def _set_pattern_info_state(self, text: str, tone: str) -> None:
        raise NotImplementedError

    def _set_baseline_state(self, text: str, tone: str, tooltip: str) -> None:
        raise NotImplementedError

    def _set_alignment_state(self, text: str, tone: str = "info") -> None:
        raise NotImplementedError

    def _set_quality_gauge_state(self, text: str, tone: str = "info") -> None:
        raise NotImplementedError

    def _set_results_state(self, text: str, tone: str) -> None:
        raise NotImplementedError

    def _set_webcam_warning(self, text: str | None) -> None:
        raise NotImplementedError

    def _tone_for_alignment_quality(self, quality: str) -> str:
        raise NotImplementedError

    def _tone_for_quality_score(self, score: float) -> str:
        raise NotImplementedError

    def _tone_for_calibration_rating(self, rating: str) -> str:
        raise NotImplementedError

    def _run_automatic_alignment_check(self) -> None:
        raise NotImplementedError

    def _run_quick_alignment_check(self) -> None:
        raise NotImplementedError

    def _display_alignment_results(
        self,
        results: AlignmentResults,
        quick_check: bool = False,
    ) -> None:
        raise NotImplementedError

    def _check_alignment_drift(self, left_img: np.ndarray, right_img: np.ndarray) -> bool:
        raise NotImplementedError

    def _show_alignment_details(self) -> None:
        raise NotImplementedError

    def _show_feature_overlay(self) -> None:
        raise NotImplementedError

    def _export_alignment_report(self) -> None:
        raise NotImplementedError

    def _save_alignment_preset(self) -> None:
        raise NotImplementedError

    def _load_alignment_preset(self) -> None:
        raise NotImplementedError

    def _compare_with_preset(self) -> None:
        raise NotImplementedError

    def _restart_cameras_after_correction(self) -> None:
        raise NotImplementedError

    def _check_camera_history(self) -> bool:
        raise NotImplementedError

    def _load_alignment_history(self) -> None:
        raise NotImplementedError

    def _update_alignment_history(self, results: AlignmentResults) -> None:
        raise NotImplementedError

    def _clear_temp_images(self) -> None:
        raise NotImplementedError

    def _open_cameras(self) -> None:
        raise NotImplementedError

    def _close_cameras(self) -> None:
        raise NotImplementedError

    def _force_release_cameras(self) -> None:
        raise NotImplementedError

    def _capture_image_pair(self) -> None:
        raise NotImplementedError

    def _run_calibration(self) -> None:
        raise NotImplementedError

    def _detect_charuco_ids(self, image: np.ndarray) -> tuple[np.ndarray | None, float]:
        raise NotImplementedError

    def _detect_charuco(self, image: np.ndarray) -> tuple[bool, np.ndarray, float]:
        raise NotImplementedError

    def _auto_detect_charuco_pattern(
        self,
        marker_ids: np.ndarray,
    ) -> Optional[tuple[int, int, float]]:
        raise NotImplementedError

    def _try_checkerboard_fallback(
        self,
        gray: np.ndarray,
        annotated: np.ndarray,
        blur_score: float,
        is_blurry: bool,
    ) -> Optional[tuple[bool, np.ndarray, float]]:
        raise NotImplementedError

    @overload
    def _get_marker_horizontal_position(
        self,
        image: np.ndarray,
        return_details: Literal[False] = False,
    ) -> float | None: ...

    @overload
    def _get_marker_horizontal_position(
        self,
        image: np.ndarray,
        return_details: Literal[True],
    ) -> tuple[float | None, int, Any, Any] | None: ...

    def _get_marker_horizontal_position(
        self,
        image: np.ndarray,
        return_details: bool = False,
    ) -> float | tuple[float | None, int, Any, Any] | None:
        raise NotImplementedError

    def _draw_marker_position_overlay(
        self,
        display_image: np.ndarray,
        original_image: np.ndarray,
    ) -> np.ndarray:
        raise NotImplementedError

    def _update_focus_indicators(self, left_blur: float, right_blur: float) -> None:
        raise NotImplementedError

    def _update_pattern_info(self) -> None:
        raise NotImplementedError

    def _wait_for_camera_warmup(self) -> None:
        raise NotImplementedError


__all__ = ["CalibrationStepMixinHost"]

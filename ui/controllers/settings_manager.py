"""Application settings management controller.

Extracted from MainWindow to reduce god class complexity.
Manages detector, strike zone, and recording settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING, Any

import yaml
from PySide6 import QtWidgets

from detect.config import Mode, FilterConfig, DetectorConfig as CvDetectorConfig
from log_config.logger import get_logger
from ui.themes import show_message_dialog

if TYPE_CHECKING:
    from configs.settings import AppConfig

logger = get_logger(__name__)


class SettingsManager:
    """Manages application settings and configuration.

    Responsibilities:
    - Detector settings (classical and ML)
    - Strike zone settings
    - Recording settings
    - Settings dialogs
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        status_label: QtWidgets.QLabel,
        get_config: Callable[[], "AppConfig"],
        get_config_path: Callable[[], Path],
        # Detector widget getters
        get_detector_mode: Callable[[], str],
        get_frame_diff: Callable[[], float],
        get_bg_diff: Callable[[], float],
        get_bg_alpha: Callable[[], float],
        get_edge_thresh: Callable[[], float],
        get_blob_thresh: Callable[[], float],
        get_min_area: Callable[[], int],
        get_min_circ: Callable[[], float],
        # Detector widget setters
        set_detector_mode: Callable[[str], None],
        set_frame_diff: Callable[[float], None],
        set_bg_diff: Callable[[float], None],
        set_bg_alpha: Callable[[float], None],
        set_edge_thresh: Callable[[float], None],
        set_blob_thresh: Callable[[float], None],
        set_min_area: Callable[[int], None],
        set_min_circ: Callable[[float], None],
        # Strike zone widget getters
        get_ball_type: Callable[[], str],
        get_batter_height: Callable[[], float],
        get_top_ratio: Callable[[], float],
        get_bottom_ratio: Callable[[], float],
        # Strike zone widget setters
        set_ball_type: Callable[[str], None],
        set_batter_height: Callable[[float], None],
        set_top_ratio: Callable[[float], None],
        set_bottom_ratio: Callable[[float], None],
        # Service callbacks
        apply_detector_to_service: Callable[[CvDetectorConfig, Mode, dict], None],
        apply_ball_type_to_service: Callable[[str], None],
        apply_batter_height_to_service: Callable[[float], None],
        apply_strike_ratios_to_service: Callable[[float, float], None],
        update_plate_map_zone: Callable[[], None],
    ):
        """Initialize settings manager.

        Args:
            parent: Parent widget for dialogs
            status_label: Label for status messages
            get_config: Callback to get current config
            get_config_path: Callback to get config file path
            ... (widget getters/setters and service callbacks)
        """
        self._parent = parent
        self._status_label = status_label
        self._get_config = get_config
        self._get_config_path = get_config_path

        # Detector getters
        self._get_detector_mode = get_detector_mode
        self._get_frame_diff = get_frame_diff
        self._get_bg_diff = get_bg_diff
        self._get_bg_alpha = get_bg_alpha
        self._get_edge_thresh = get_edge_thresh
        self._get_blob_thresh = get_blob_thresh
        self._get_min_area = get_min_area
        self._get_min_circ = get_min_circ

        # Detector setters
        self._set_detector_mode = set_detector_mode
        self._set_frame_diff = set_frame_diff
        self._set_bg_diff = set_bg_diff
        self._set_bg_alpha = set_bg_alpha
        self._set_edge_thresh = set_edge_thresh
        self._set_blob_thresh = set_blob_thresh
        self._set_min_area = set_min_area
        self._set_min_circ = set_min_circ

        # Strike zone getters
        self._get_ball_type = get_ball_type
        self._get_batter_height = get_batter_height
        self._get_top_ratio = get_top_ratio
        self._get_bottom_ratio = get_bottom_ratio

        # Strike zone setters
        self._set_ball_type_widget = set_ball_type
        self._set_batter_height_widget = set_batter_height
        self._set_top_ratio_widget = set_top_ratio
        self._set_bottom_ratio_widget = set_bottom_ratio

        # Service callbacks
        self._apply_detector_to_service = apply_detector_to_service
        self._apply_ball_type_to_service = apply_ball_type_to_service
        self._apply_batter_height_to_service = apply_batter_height_to_service
        self._apply_strike_ratios_to_service = apply_strike_ratios_to_service
        self._update_plate_map_zone = update_plate_map_zone

        # ML detector state (stored here since not directly tied to widgets)
        self._detector_type: str = "classical"
        self._detector_model_path: str = ""
        self._detector_model_input_size: tuple = (640, 640)
        self._detector_model_conf_threshold: float = 0.5
        self._detector_model_class_id: int = 0
        self._detector_model_format: str = "onnx"
        self._detection_threading: str = "sync"
        self._detection_workers: int = 1

        logger.debug("SettingsManager initialized")

    def load_detector_defaults(self) -> None:
        """Load detector settings from config into UI widgets."""
        cfg = self._get_config().detector
        self._detector_type = cfg.type
        self._detector_model_path = cfg.model_path or ""
        self._detector_model_input_size = tuple(cfg.model_input_size)
        self._detector_model_conf_threshold = float(cfg.model_conf_threshold)
        self._detector_model_class_id = int(cfg.model_class_id)
        self._detector_model_format = cfg.model_format

        self._set_detector_mode(cfg.mode)
        self._set_frame_diff(cfg.frame_diff_threshold)
        self._set_bg_diff(cfg.bg_diff_threshold)
        self._set_bg_alpha(cfg.bg_alpha)
        self._set_edge_thresh(cfg.edge_threshold)
        self._set_blob_thresh(cfg.blob_threshold)
        self._set_min_area(cfg.filters.min_area)
        self._set_min_circ(cfg.filters.min_circularity)
        logger.debug("Detector defaults loaded")

    def apply_detector_config(self) -> bool:
        """Apply detector settings from UI to service.

        Returns:
            True if settings applied successfully, False otherwise
        """
        if self._detector_type == "ml" and not self._detector_model_path:
            show_message_dialog(
                self._parent,
                "Detector Settings",
                "Select an ONNX model path before enabling ML detection.",
                tone="warning",
            )
            return False

        cfg = self._get_config().detector
        filter_cfg = FilterConfig(
            min_area=self._get_min_area(),
            max_area=cfg.filters.max_area,
            min_circularity=self._get_min_circ(),
            max_circularity=cfg.filters.max_circularity,
            min_velocity=cfg.filters.min_velocity,
            max_velocity=cfg.filters.max_velocity,
        )
        detector_cfg = CvDetectorConfig(
            frame_diff_threshold=self._get_frame_diff(),
            bg_diff_threshold=self._get_bg_diff(),
            bg_alpha=self._get_bg_alpha(),
            edge_threshold=self._get_edge_thresh(),
            blob_threshold=self._get_blob_thresh(),
            runtime_budget_ms=cfg.runtime_budget_ms,
            min_consecutive=cfg.min_consecutive,
            filters=filter_cfg,
        )
        mode = Mode(self._get_detector_mode())

        ml_settings = {
            "detector_type": self._detector_type,
            "model_path": self._detector_model_path or None,
            "model_input_size": self._detector_model_input_size,
            "model_conf_threshold": self._detector_model_conf_threshold,
            "model_class_id": self._detector_model_class_id,
            "model_format": self._detector_model_format,
            "threading_mode": self._detection_threading,
            "worker_count": self._detection_workers,
        }

        self._apply_detector_to_service(detector_cfg, mode, ml_settings)
        self._status_label.setText("Detector settings applied.")
        logger.info("Detector settings applied")
        return True

    def set_ball_type(self, ball_type: str) -> None:
        """Set ball type in service."""
        self._apply_ball_type_to_service(ball_type)
        logger.debug(f"Ball type set: {ball_type}")

    def set_batter_height(self, value: float) -> None:
        """Set batter height and update plate map."""
        self._apply_batter_height_to_service(value)
        self._update_plate_map_zone()
        logger.debug(f"Batter height set: {value}")

    def set_strike_ratios(self) -> None:
        """Set strike zone ratios from UI and update plate map."""
        self._apply_strike_ratios_to_service(
            self._get_top_ratio(),
            self._get_bottom_ratio(),
        )
        self._update_plate_map_zone()
        logger.debug("Strike ratios updated")

    def save_strike_zone(self) -> None:
        """Save strike zone settings to config file."""
        config_path = self._get_config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("strike_zone", {})
        data["strike_zone"]["batter_height_in"] = float(self._get_batter_height())
        data["strike_zone"]["top_ratio"] = float(self._get_top_ratio())
        data["strike_zone"]["bottom_ratio"] = float(self._get_bottom_ratio())
        data.setdefault("ball", {})
        data["ball"]["type"] = self._get_ball_type()
        config_path.write_text(yaml.safe_dump(data, sort_keys=False))
        self._status_label.setText("Strike zone saved.")
        self._update_plate_map_zone()
        logger.info("Strike zone saved")

    def update_detector_settings(self, values: dict) -> None:
        """Update detector settings from dialog values.

        Args:
            values: Dictionary of detector settings from dialog
        """
        self._set_detector_mode(values["mode"])
        self._set_frame_diff(values["frame_diff"])
        self._set_bg_diff(values["bg_diff"])
        self._set_bg_alpha(values["bg_alpha"])
        self._set_edge_thresh(values["edge_thresh"])
        self._set_blob_thresh(values["blob_thresh"])
        self._set_min_area(values["min_area"])
        self._set_min_circ(values["min_circ"])
        self._detection_threading = values.get("threading_mode", "sync")
        self._detection_workers = values.get("worker_count", 1)
        self._detector_type = values.get("detector_type", "classical")
        self._detector_model_path = values.get("model_path", "")
        self._detector_model_input_size = values.get("model_input_size", (640, 640))
        self._detector_model_conf_threshold = values.get("model_conf_threshold", 0.5)
        self._detector_model_class_id = values.get("model_class_id", 0)
        self._detector_model_format = values.get("model_format", "onnx")
        logger.debug("Detector settings updated from dialog")

    def update_strike_settings(
        self,
        ball_type: str,
        height: float,
        top_ratio: float,
        bottom_ratio: float,
    ) -> None:
        """Update strike zone settings from dialog values.

        Args:
            ball_type: Ball type string
            height: Batter height in inches
            top_ratio: Top strike zone ratio
            bottom_ratio: Bottom strike zone ratio
        """
        self._set_ball_type_widget(ball_type)
        self._set_batter_height_widget(height)
        self._set_top_ratio_widget(top_ratio)
        self._set_bottom_ratio_widget(bottom_ratio)
        logger.debug("Strike settings updated from dialog")

    def get_detector_dialog_values(self) -> dict:
        """Get current detector values for dialog.

        Returns:
            Dictionary of current detector settings
        """
        return {
            "mode": self._get_detector_mode(),
            "frame_diff": self._get_frame_diff(),
            "bg_diff": self._get_bg_diff(),
            "bg_alpha": self._get_bg_alpha(),
            "edge_thresh": self._get_edge_thresh(),
            "blob_thresh": self._get_blob_thresh(),
            "min_area": self._get_min_area(),
            "min_circ": self._get_min_circ(),
            "threading_mode": self._detection_threading,
            "worker_count": self._detection_workers,
            "detector_type": self._detector_type,
            "model_path": self._detector_model_path,
            "model_input_size": self._detector_model_input_size,
            "model_conf_threshold": self._detector_model_conf_threshold,
            "model_class_id": self._detector_model_class_id,
            "model_format": self._detector_model_format,
        }

    def get_strike_dialog_values(self) -> dict:
        """Get current strike zone values for dialog.

        Returns:
            Dictionary of current strike zone settings
        """
        return {
            "ball_type": self._get_ball_type(),
            "batter_height": self._get_batter_height(),
            "top_ratio": self._get_top_ratio(),
            "bottom_ratio": self._get_bottom_ratio(),
        }

    @property
    def detector_type(self) -> str:
        """Get detector type."""
        return self._detector_type

    @property
    def detector_model_path(self) -> str:
        """Get detector model path."""
        return self._detector_model_path

    @property
    def detection_threading(self) -> str:
        """Get detection threading mode."""
        return self._detection_threading

    @property
    def detection_workers(self) -> int:
        """Get detection worker count."""
        return self._detection_workers

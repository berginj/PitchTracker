"""Unit tests for SettingsManager controller.

Tests the extracted SettingsManager class from MainWindow refactoring.
Covers detector, strike zone, and recording settings.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from ui.controllers.settings_manager import SettingsManager


class TestSettingsManagerInit:
    """Tests for SettingsManager initialization."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies for SettingsManager."""
        config = Mock()
        config.detector.type = "classical"
        config.detector.mode = "MODE_A"
        config.detector.model_path = ""
        config.detector.model_input_size = [640, 640]
        config.detector.model_conf_threshold = 0.25
        config.detector.model_class_id = 0
        config.detector.model_format = "onnx"
        config.detector.frame_diff_threshold = 30
        config.detector.bg_diff_threshold = 40
        config.detector.bg_alpha = 0.01
        config.detector.edge_threshold = 100
        config.detector.blob_threshold = 127
        config.detector.runtime_budget_ms = 10
        config.detector.min_consecutive = 2
        config.detector.filters.min_area = 10
        config.detector.filters.max_area = 1000
        config.detector.filters.min_circularity = 0.5
        config.detector.filters.max_circularity = 1.0
        config.detector.filters.min_velocity = 0.0
        config.detector.filters.max_velocity = 200.0

        return {
            "parent": Mock(),
            "status_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_config_path": Mock(return_value=tmp_path / "config.yaml"),
            # Detector getters
            "get_detector_mode": Mock(return_value="MODE_A"),
            "get_frame_diff": Mock(return_value=30.0),
            "get_bg_diff": Mock(return_value=40.0),
            "get_bg_alpha": Mock(return_value=0.01),
            "get_edge_thresh": Mock(return_value=100.0),
            "get_blob_thresh": Mock(return_value=127.0),
            "get_min_area": Mock(return_value=10),
            "get_min_circ": Mock(return_value=0.5),
            # Detector setters
            "set_detector_mode": Mock(),
            "set_frame_diff": Mock(),
            "set_bg_diff": Mock(),
            "set_bg_alpha": Mock(),
            "set_edge_thresh": Mock(),
            "set_blob_thresh": Mock(),
            "set_min_area": Mock(),
            "set_min_circ": Mock(),
            # Strike zone getters
            "get_ball_type": Mock(return_value="baseball"),
            "get_batter_height": Mock(return_value=72.0),
            "get_top_ratio": Mock(return_value=0.55),
            "get_bottom_ratio": Mock(return_value=0.28),
            # Strike zone setters
            "set_ball_type": Mock(),
            "set_batter_height": Mock(),
            "set_top_ratio": Mock(),
            "set_bottom_ratio": Mock(),
            # Service callbacks
            "apply_detector_to_service": Mock(),
            "apply_ball_type_to_service": Mock(),
            "apply_batter_height_to_service": Mock(),
            "apply_strike_ratios_to_service": Mock(),
            "update_plate_map_zone": Mock(),
        }

    def test_initialization(self, mock_deps):
        """SettingsManager should initialize with provided dependencies."""
        sm = SettingsManager(**mock_deps)
        assert sm.detector_type == "classical"
        assert sm.detection_threading == "sync"


class TestLoadDetectorDefaults:
    """Tests for loading detector defaults."""

    @pytest.fixture
    def settings_manager(self, tmp_path):
        """Create SettingsManager with mocked dependencies."""
        config = Mock()
        config.detector.type = "ml"
        config.detector.mode = "MODE_B"
        config.detector.model_path = "/path/to/model.onnx"
        config.detector.model_input_size = [320, 320]
        config.detector.model_conf_threshold = 0.5
        config.detector.model_class_id = 1
        config.detector.model_format = "yolo_v5"
        config.detector.frame_diff_threshold = 25
        config.detector.bg_diff_threshold = 35
        config.detector.bg_alpha = 0.02
        config.detector.edge_threshold = 80
        config.detector.blob_threshold = 100
        config.detector.filters.min_area = 20
        config.detector.filters.min_circularity = 0.6

        set_mode = Mock()
        set_frame_diff = Mock()

        sm = SettingsManager(
            parent=Mock(),
            status_label=Mock(),
            get_config=Mock(return_value=config),
            get_config_path=Mock(return_value=tmp_path / "config.yaml"),
            get_detector_mode=Mock(return_value="MODE_A"),
            get_frame_diff=Mock(return_value=30.0),
            get_bg_diff=Mock(return_value=40.0),
            get_bg_alpha=Mock(return_value=0.01),
            get_edge_thresh=Mock(return_value=100.0),
            get_blob_thresh=Mock(return_value=127.0),
            get_min_area=Mock(return_value=10),
            get_min_circ=Mock(return_value=0.5),
            set_detector_mode=set_mode,
            set_frame_diff=set_frame_diff,
            set_bg_diff=Mock(),
            set_bg_alpha=Mock(),
            set_edge_thresh=Mock(),
            set_blob_thresh=Mock(),
            set_min_area=Mock(),
            set_min_circ=Mock(),
            get_ball_type=Mock(return_value="baseball"),
            get_batter_height=Mock(return_value=72.0),
            get_top_ratio=Mock(return_value=0.55),
            get_bottom_ratio=Mock(return_value=0.28),
            set_ball_type=Mock(),
            set_batter_height=Mock(),
            set_top_ratio=Mock(),
            set_bottom_ratio=Mock(),
            apply_detector_to_service=Mock(),
            apply_ball_type_to_service=Mock(),
            apply_batter_height_to_service=Mock(),
            apply_strike_ratios_to_service=Mock(),
            update_plate_map_zone=Mock(),
        )
        sm._set_detector_mode = set_mode
        sm._set_frame_diff = set_frame_diff
        return sm

    def test_load_detector_defaults(self, settings_manager):
        """load_detector_defaults should load config into widgets."""
        settings_manager.load_detector_defaults()

        assert settings_manager.detector_type == "ml"
        assert settings_manager.detector_model_path == "/path/to/model.onnx"
        settings_manager._set_detector_mode.assert_called_with("MODE_B")
        settings_manager._set_frame_diff.assert_called_with(25)


class TestApplyDetectorConfig:
    """Tests for applying detector config."""

    @pytest.fixture
    def settings_manager(self, tmp_path):
        """Create SettingsManager with mocked dependencies."""
        config = Mock()
        config.detector.filters.max_area = 1000
        config.detector.filters.max_circularity = 1.0
        config.detector.filters.min_velocity = 0.0
        config.detector.filters.max_velocity = 200.0
        config.detector.runtime_budget_ms = 10
        config.detector.min_consecutive = 2

        apply_to_service = Mock()

        return SettingsManager(
            parent=Mock(),
            status_label=Mock(),
            get_config=Mock(return_value=config),
            get_config_path=Mock(return_value=tmp_path / "config.yaml"),
            get_detector_mode=Mock(return_value="MODE_A"),
            get_frame_diff=Mock(return_value=30.0),
            get_bg_diff=Mock(return_value=40.0),
            get_bg_alpha=Mock(return_value=0.01),
            get_edge_thresh=Mock(return_value=100.0),
            get_blob_thresh=Mock(return_value=127.0),
            get_min_area=Mock(return_value=10),
            get_min_circ=Mock(return_value=0.5),
            set_detector_mode=Mock(),
            set_frame_diff=Mock(),
            set_bg_diff=Mock(),
            set_bg_alpha=Mock(),
            set_edge_thresh=Mock(),
            set_blob_thresh=Mock(),
            set_min_area=Mock(),
            set_min_circ=Mock(),
            get_ball_type=Mock(return_value="baseball"),
            get_batter_height=Mock(return_value=72.0),
            get_top_ratio=Mock(return_value=0.55),
            get_bottom_ratio=Mock(return_value=0.28),
            set_ball_type=Mock(),
            set_batter_height=Mock(),
            set_top_ratio=Mock(),
            set_bottom_ratio=Mock(),
            apply_detector_to_service=apply_to_service,
            apply_ball_type_to_service=Mock(),
            apply_batter_height_to_service=Mock(),
            apply_strike_ratios_to_service=Mock(),
            update_plate_map_zone=Mock(),
        )

    def test_apply_detector_config_classical(self, settings_manager):
        """apply_detector_config should apply settings to service."""
        result = settings_manager.apply_detector_config()

        assert result is True
        settings_manager._apply_detector_to_service.assert_called_once()
        settings_manager._status_label.setText.assert_called_with(
            "Detector settings applied."
        )

    @patch("ui.controllers.settings_manager.QtWidgets.QMessageBox")
    def test_apply_detector_config_ml_no_path(self, mock_msgbox, settings_manager):
        """apply_detector_config should fail if ML mode without model path."""
        settings_manager._detector_type = "ml"
        settings_manager._detector_model_path = ""

        result = settings_manager.apply_detector_config()

        assert result is False
        mock_msgbox.warning.assert_called_once()


class TestStrikeZoneSettings:
    """Tests for strike zone settings."""

    @pytest.fixture
    def settings_manager(self, tmp_path):
        """Create SettingsManager with mocked dependencies."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("strike_zone: {}\nball: {}")

        config = Mock()

        return SettingsManager(
            parent=Mock(),
            status_label=Mock(),
            get_config=Mock(return_value=config),
            get_config_path=Mock(return_value=config_path),
            get_detector_mode=Mock(return_value="MODE_A"),
            get_frame_diff=Mock(return_value=30.0),
            get_bg_diff=Mock(return_value=40.0),
            get_bg_alpha=Mock(return_value=0.01),
            get_edge_thresh=Mock(return_value=100.0),
            get_blob_thresh=Mock(return_value=127.0),
            get_min_area=Mock(return_value=10),
            get_min_circ=Mock(return_value=0.5),
            set_detector_mode=Mock(),
            set_frame_diff=Mock(),
            set_bg_diff=Mock(),
            set_bg_alpha=Mock(),
            set_edge_thresh=Mock(),
            set_blob_thresh=Mock(),
            set_min_area=Mock(),
            set_min_circ=Mock(),
            get_ball_type=Mock(return_value="baseball"),
            get_batter_height=Mock(return_value=72.0),
            get_top_ratio=Mock(return_value=0.55),
            get_bottom_ratio=Mock(return_value=0.28),
            set_ball_type=Mock(),
            set_batter_height=Mock(),
            set_top_ratio=Mock(),
            set_bottom_ratio=Mock(),
            apply_detector_to_service=Mock(),
            apply_ball_type_to_service=Mock(),
            apply_batter_height_to_service=Mock(),
            apply_strike_ratios_to_service=Mock(),
            update_plate_map_zone=Mock(),
        )

    def test_set_ball_type(self, settings_manager):
        """set_ball_type should call service."""
        settings_manager.set_ball_type("softball")
        settings_manager._apply_ball_type_to_service.assert_called_with("softball")

    def test_set_batter_height(self, settings_manager):
        """set_batter_height should call service and update plate map."""
        settings_manager.set_batter_height(68.0)
        settings_manager._apply_batter_height_to_service.assert_called_with(68.0)
        settings_manager._update_plate_map_zone.assert_called_once()

    def test_set_strike_ratios(self, settings_manager):
        """set_strike_ratios should call service and update plate map."""
        settings_manager.set_strike_ratios()
        settings_manager._apply_strike_ratios_to_service.assert_called_with(0.55, 0.28)
        settings_manager._update_plate_map_zone.assert_called_once()

    def test_save_strike_zone(self, settings_manager):
        """save_strike_zone should save to config file."""
        settings_manager.save_strike_zone()

        settings_manager._status_label.setText.assert_called_with("Strike zone saved.")
        settings_manager._update_plate_map_zone.assert_called_once()


class TestDialogValues:
    """Tests for dialog value accessors."""

    @pytest.fixture
    def settings_manager(self, tmp_path):
        """Create SettingsManager with mocked dependencies."""
        return SettingsManager(
            parent=Mock(),
            status_label=Mock(),
            get_config=Mock(),
            get_config_path=Mock(return_value=tmp_path / "config.yaml"),
            get_detector_mode=Mock(return_value="MODE_B"),
            get_frame_diff=Mock(return_value=25.0),
            get_bg_diff=Mock(return_value=35.0),
            get_bg_alpha=Mock(return_value=0.02),
            get_edge_thresh=Mock(return_value=80.0),
            get_blob_thresh=Mock(return_value=100.0),
            get_min_area=Mock(return_value=15),
            get_min_circ=Mock(return_value=0.6),
            set_detector_mode=Mock(),
            set_frame_diff=Mock(),
            set_bg_diff=Mock(),
            set_bg_alpha=Mock(),
            set_edge_thresh=Mock(),
            set_blob_thresh=Mock(),
            set_min_area=Mock(),
            set_min_circ=Mock(),
            get_ball_type=Mock(return_value="softball"),
            get_batter_height=Mock(return_value=66.0),
            get_top_ratio=Mock(return_value=0.52),
            get_bottom_ratio=Mock(return_value=0.30),
            set_ball_type=Mock(),
            set_batter_height=Mock(),
            set_top_ratio=Mock(),
            set_bottom_ratio=Mock(),
            apply_detector_to_service=Mock(),
            apply_ball_type_to_service=Mock(),
            apply_batter_height_to_service=Mock(),
            apply_strike_ratios_to_service=Mock(),
            update_plate_map_zone=Mock(),
        )

    def test_get_detector_dialog_values(self, settings_manager):
        """get_detector_dialog_values should return current settings."""
        values = settings_manager.get_detector_dialog_values()

        assert values["mode"] == "MODE_B"
        assert values["frame_diff"] == 25.0
        assert values["min_area"] == 15
        assert values["detector_type"] == "classical"

    def test_get_strike_dialog_values(self, settings_manager):
        """get_strike_dialog_values should return current settings."""
        values = settings_manager.get_strike_dialog_values()

        assert values["ball_type"] == "softball"
        assert values["batter_height"] == 66.0
        assert values["top_ratio"] == 0.52
        assert values["bottom_ratio"] == 0.30

    def test_update_detector_settings(self, settings_manager):
        """update_detector_settings should update widgets and state."""
        values = {
            "mode": "MODE_A",
            "frame_diff": 30.0,
            "bg_diff": 40.0,
            "bg_alpha": 0.01,
            "edge_thresh": 100.0,
            "blob_thresh": 127.0,
            "min_area": 10,
            "min_circ": 0.5,
            "threading_mode": "per_camera",
            "worker_count": 2,
            "detector_type": "ml",
            "model_path": "/path/model.onnx",
            "model_input_size": (640, 640),
            "model_conf_threshold": 0.3,
            "model_class_id": 0,
            "model_format": "onnx",
        }

        settings_manager.update_detector_settings(values)

        settings_manager._set_detector_mode.assert_called_with("MODE_A")
        settings_manager._set_frame_diff.assert_called_with(30.0)
        assert settings_manager._detector_type == "ml"
        assert settings_manager._detection_threading == "per_camera"

    def test_update_strike_settings(self, settings_manager):
        """update_strike_settings should update widgets."""
        settings_manager.update_strike_settings("baseball", 72.0, 0.55, 0.28)

        settings_manager._set_ball_type_widget.assert_called_with("baseball")
        settings_manager._set_batter_height_widget.assert_called_with(72.0)
        settings_manager._set_top_ratio_widget.assert_called_with(0.55)
        settings_manager._set_bottom_ratio_widget.assert_called_with(0.28)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

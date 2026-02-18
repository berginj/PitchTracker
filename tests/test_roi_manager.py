"""Unit tests for RoiManager controller.

Tests the extracted RoiManager class from MainWindow refactoring.
Covers ROI drawing, saving, and loading workflows.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from ui.controllers.roi_manager import RoiManager


class TestRoiManagerInit:
    """Tests for RoiManager initialization."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies for RoiManager."""
        return {
            "roi_path": tmp_path / "rois.json",
            "lane_path": tmp_path / "lane_rois.json",
            "left_view": Mock(),
            "right_view": Mock(),
            "status_label": Mock(),
            "get_camera_serials": Mock(return_value=("left_cam", "right_cam")),
        }

    def test_initialization(self, mock_deps):
        """RoiManager should initialize with provided dependencies."""
        rm = RoiManager(**mock_deps)
        assert rm._roi_path == mock_deps["roi_path"]
        assert rm._lane_path == mock_deps["lane_path"]
        assert rm.roi_mode is None
        assert rm.lane_rect is None
        assert rm.plate_rect is None
        assert rm.lane_rect_right is None
        assert rm.active_rect is None


class TestSetRoiMode:
    """Tests for ROI mode setting."""

    @pytest.fixture
    def roi_manager(self, tmp_path):
        """Create RoiManager with mocked dependencies."""
        return RoiManager(
            roi_path=tmp_path / "rois.json",
            lane_path=tmp_path / "lane_rois.json",
            left_view=Mock(),
            right_view=Mock(),
            status_label=Mock(),
            get_camera_serials=Mock(return_value=("left", "right")),
        )

    def test_set_mode_lane(self, roi_manager):
        """Setting lane mode should enable left view drawing."""
        roi_manager.set_roi_mode("lane")

        assert roi_manager.roi_mode == "lane"
        roi_manager._left_view.set_mode.assert_called_with("lane")
        roi_manager._right_view.set_mode.assert_called_with(None)

    def test_set_mode_plate(self, roi_manager):
        """Setting plate mode should enable left view drawing."""
        roi_manager.set_roi_mode("plate")

        assert roi_manager.roi_mode == "plate"
        roi_manager._left_view.set_mode.assert_called_with("plate")
        roi_manager._right_view.set_mode.assert_called_with(None)

    def test_set_mode_lane_right(self, roi_manager):
        """Setting lane_right mode should enable right view drawing."""
        roi_manager.set_roi_mode("lane_right")

        assert roi_manager.roi_mode == "lane_right"
        roi_manager._left_view.set_mode.assert_called_with(None)
        roi_manager._right_view.set_mode.assert_called_with("lane_right")


class TestRectUpdate:
    """Tests for rectangle update handling."""

    @pytest.fixture
    def roi_manager(self, tmp_path):
        """Create RoiManager with mocked dependencies."""
        left_view = Mock()
        left_view.image_size.return_value = (640, 480)
        right_view = Mock()
        right_view.image_size.return_value = (640, 480)
        return RoiManager(
            roi_path=tmp_path / "rois.json",
            lane_path=tmp_path / "lane_rois.json",
            left_view=left_view,
            right_view=right_view,
            status_label=Mock(),
            get_camera_serials=Mock(return_value=("left", "right")),
        )

    def test_on_rect_update_lane_final(self, roi_manager):
        """Final lane rect update should set lane_rect."""
        roi_manager.set_roi_mode("lane")
        roi_manager.on_rect_update((100, 100, 300, 200), final=True)

        assert roi_manager.lane_rect == (100, 100, 300, 200)
        assert roi_manager.active_rect is None

    def test_on_rect_update_plate_final(self, roi_manager):
        """Final plate rect update should set plate_rect."""
        roi_manager.set_roi_mode("plate")
        roi_manager.on_rect_update((50, 50, 150, 100), final=True)

        assert roi_manager.plate_rect == (50, 50, 150, 100)
        assert roi_manager.active_rect is None

    def test_on_rect_update_not_final(self, roi_manager):
        """Non-final rect update should set active_rect."""
        roi_manager.set_roi_mode("lane")
        roi_manager.on_rect_update((100, 100, 200, 150), final=False)

        assert roi_manager.active_rect == (100, 100, 200, 150)
        assert roi_manager.lane_rect is None

    def test_on_right_rect_update_final(self, roi_manager):
        """Final right rect update should set lane_rect_right."""
        roi_manager.set_roi_mode("lane_right")
        roi_manager.on_right_rect_update((100, 100, 300, 200), final=True)

        assert roi_manager.lane_rect_right == (100, 100, 300, 200)
        assert roi_manager.active_rect is None


class TestClearRois:
    """Tests for clearing ROIs."""

    @pytest.fixture
    def roi_manager(self, tmp_path):
        """Create RoiManager with mocked dependencies."""
        left_view = Mock()
        left_view.image_size.return_value = (640, 480)
        return RoiManager(
            roi_path=tmp_path / "rois.json",
            lane_path=tmp_path / "lane_rois.json",
            left_view=left_view,
            right_view=Mock(),
            status_label=Mock(),
            get_camera_serials=Mock(return_value=("left", "right")),
        )

    def test_clear_lane(self, roi_manager):
        """clear_lane should clear both lane rectangles."""
        roi_manager.set_roi_mode("lane")
        roi_manager.on_rect_update((100, 100, 300, 200), final=True)
        roi_manager.lane_rect_right = (100, 100, 300, 200)

        roi_manager.clear_lane()

        assert roi_manager.lane_rect is None
        assert roi_manager.lane_rect_right is None

    def test_clear_plate(self, roi_manager):
        """clear_plate should clear plate rectangle."""
        roi_manager.set_roi_mode("plate")
        roi_manager.on_rect_update((50, 50, 150, 100), final=True)

        roi_manager.clear_plate()

        assert roi_manager.plate_rect is None


class TestSaveLoadRois:
    """Tests for ROI persistence."""

    @pytest.fixture
    def roi_manager(self, tmp_path):
        """Create RoiManager with mocked dependencies."""
        left_view = Mock()
        left_view.image_size.return_value = (640, 480)
        return RoiManager(
            roi_path=tmp_path / "rois.json",
            lane_path=tmp_path / "lane_rois.json",
            left_view=left_view,
            right_view=Mock(),
            status_label=Mock(),
            get_camera_serials=Mock(return_value=("left_serial", "right_serial")),
        )

    @patch("ui.controllers.roi_manager.save_lane_rois")
    @patch("ui.controllers.roi_manager.save_rois")
    def test_save_rois(self, mock_save_rois, mock_save_lane, roi_manager):
        """save_rois should save ROIs to files."""
        roi_manager.set_roi_mode("lane")
        roi_manager.on_rect_update((100, 100, 300, 200), final=True)

        roi_manager.save_rois()

        mock_save_rois.assert_called_once()
        mock_save_lane.assert_called_once()
        roi_manager._status_label.setText.assert_called_with("ROIs saved.")

    @patch("ui.controllers.roi_manager.load_lane_rois")
    @patch("ui.controllers.roi_manager.load_rois")
    def test_load_rois(self, mock_load_rois, mock_load_lane, roi_manager):
        """load_rois should load ROIs from files."""
        mock_load_rois.return_value = {
            "lane": [(100, 100), (300, 100), (300, 200), (100, 200)],
            "plate": [(50, 50), (150, 50), (150, 100), (50, 100)],
        }
        mock_load_lane.return_value = {}

        roi_manager.load_rois()

        mock_load_rois.assert_called_once()
        mock_load_lane.assert_called_once()
        # ROIs should be loaded
        assert roi_manager.lane_rect is not None or roi_manager.plate_rect is not None

    @patch("ui.controllers.roi_manager.load_lane_rois")
    @patch("ui.controllers.roi_manager.load_rois")
    def test_load_rois_empty(self, mock_load_rois, mock_load_lane, roi_manager):
        """load_rois should handle empty ROI files."""
        mock_load_rois.return_value = {}
        mock_load_lane.return_value = {}

        roi_manager.load_rois()

        assert roi_manager.lane_rect is None
        assert roi_manager.plate_rect is None


class TestProposeRightLane:
    """Tests for proposing right lane ROI."""

    @pytest.fixture
    def roi_manager(self, tmp_path):
        """Create RoiManager with mocked dependencies."""
        left_view = Mock()
        left_view.image_size.return_value = (640, 480)
        return RoiManager(
            roi_path=tmp_path / "rois.json",
            lane_path=tmp_path / "lane_rois.json",
            left_view=left_view,
            right_view=Mock(),
            status_label=Mock(),
            get_camera_serials=Mock(return_value=("left", "right")),
        )

    @patch("ui.controllers.roi_manager.QtWidgets.QMessageBox")
    def test_propose_right_lane_no_left_lane(self, mock_msgbox, roi_manager):
        """propose_right_lane should fail without left lane."""
        parent = Mock()

        result = roi_manager.propose_right_lane(parent, (640, 480), (640, 480))

        assert result is False
        mock_msgbox.information.assert_called_once()

    @patch("ui.controllers.roi_manager.QtWidgets.QMessageBox")
    def test_propose_right_lane_no_frames(self, mock_msgbox, roi_manager):
        """propose_right_lane should fail without frame data."""
        parent = Mock()
        roi_manager.set_roi_mode("lane")
        roi_manager.on_rect_update((100, 100, 300, 200), final=True)

        result = roi_manager.propose_right_lane(parent, None, None)

        assert result is False
        mock_msgbox.warning.assert_called_once()

    def test_propose_right_lane_success(self, roi_manager):
        """propose_right_lane should calculate right lane from left."""
        parent = Mock()
        roi_manager.set_roi_mode("lane")
        roi_manager.on_rect_update((100, 100, 300, 200), final=True)

        result = roi_manager.propose_right_lane(parent, (640, 480), (640, 480))

        assert result is True
        assert roi_manager.lane_rect_right is not None


class TestLaneRectRightSetter:
    """Tests for lane_rect_right property setter."""

    @pytest.fixture
    def roi_manager(self, tmp_path):
        """Create RoiManager with mocked dependencies."""
        return RoiManager(
            roi_path=tmp_path / "rois.json",
            lane_path=tmp_path / "lane_rois.json",
            left_view=Mock(),
            right_view=Mock(),
            status_label=Mock(),
            get_camera_serials=Mock(return_value=("left", "right")),
        )

    def test_set_lane_rect_right(self, roi_manager):
        """Setting lane_rect_right should update the value."""
        roi_manager.lane_rect_right = (100, 100, 300, 200)
        assert roi_manager.lane_rect_right == (100, 100, 300, 200)

    def test_set_lane_rect_right_none(self, roi_manager):
        """Setting lane_rect_right to None should clear it."""
        roi_manager.lane_rect_right = (100, 100, 300, 200)
        roi_manager.lane_rect_right = None
        assert roi_manager.lane_rect_right is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

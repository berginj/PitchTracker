"""Unit tests for CalibrationOverlayController.

Tests the extracted CalibrationOverlayController class from MainWindow refactoring.
Covers checkerboard and fiducial detection for calibration overlays.
"""

from __future__ import annotations

from unittest.mock import Mock, patch, MagicMock
import numpy as np

import pytest

from ui.controllers.calibration_overlay import CalibrationOverlayController


class TestCalibrationOverlayControllerInit:
    """Tests for CalibrationOverlayController initialization."""

    def test_initialization_defaults(self):
        """CalibrationOverlayController should initialize with defaults."""
        co = CalibrationOverlayController()

        assert co.show_target is False
        assert co.target_found is False
        assert co.target_corners is None
        assert co.show_fiducials is False
        assert co.fiducial_detections == []
        assert co.fiducial_error is None
        assert co.fiducial_ids == {"plate": 0, "rubber": 1}

    def test_initialization_custom(self):
        """CalibrationOverlayController should accept custom parameters."""
        co = CalibrationOverlayController(
            target_pattern=(7, 5),
            target_stride=10,
            fiducial_stride=3,
            fiducial_ids={"a": 1, "b": 2},
        )

        assert co._target_pattern == (7, 5)
        assert co._target_stride == 10
        assert co._fiducial_stride == 3
        assert co.fiducial_ids == {"a": 1, "b": 2}


class TestTargetOverlay:
    """Tests for target (checkerboard) overlay."""

    @pytest.fixture
    def controller(self):
        """Create CalibrationOverlayController."""
        return CalibrationOverlayController(
            target_stride=1,  # Process every frame for testing
        )

    def test_set_target_overlay_enable(self, controller):
        """set_target_overlay should enable detection and reset state."""
        controller.set_target_overlay(True)

        assert controller.show_target is True
        assert controller.target_found is False
        assert controller.target_corners is None

    def test_set_target_overlay_disable(self, controller):
        """set_target_overlay should disable detection."""
        controller.set_target_overlay(True)
        controller.set_target_overlay(False)

        assert controller.show_target is False

    @patch("ui.controllers.calibration_overlay.cv2.findChessboardCorners")
    def test_process_target_detection_found(self, mock_find, controller):
        """process_target_detection should return corners when found."""
        # Mock successful detection
        mock_corners = np.array([[[10.0, 20.0]], [[30.0, 40.0]]])
        mock_find.return_value = (True, mock_corners)

        controller.set_target_overlay(True)
        frame = np.zeros((100, 100), dtype=np.uint8)

        result = controller.process_target_detection(frame)

        assert result is not None
        assert len(result) == 2
        assert result[0] == (10.0, 20.0)
        assert result[1] == (30.0, 40.0)
        assert controller.target_found is True

    @patch("ui.controllers.calibration_overlay.cv2.findChessboardCorners")
    def test_process_target_detection_not_found(self, mock_find, controller):
        """process_target_detection should return None when not found."""
        mock_find.return_value = (False, None)

        controller.set_target_overlay(True)
        frame = np.zeros((100, 100), dtype=np.uint8)

        result = controller.process_target_detection(frame)

        assert result is None
        assert controller.target_found is False
        assert controller.target_corners is None

    def test_process_target_detection_disabled(self, controller):
        """process_target_detection should return None when disabled."""
        frame = np.zeros((100, 100), dtype=np.uint8)

        result = controller.process_target_detection(frame)

        assert result is None


class TestFiducialOverlay:
    """Tests for fiducial (AprilTag) overlay."""

    @pytest.fixture
    def controller(self):
        """Create CalibrationOverlayController."""
        return CalibrationOverlayController(
            fiducial_stride=1,  # Process every frame for testing
        )

    def test_set_fiducial_overlay_enable(self, controller):
        """set_fiducial_overlay should enable detection and reset state."""
        controller.set_fiducial_overlay(True)

        assert controller.show_fiducials is True
        assert controller.fiducial_detections == []
        assert controller.fiducial_error is None

    def test_set_fiducial_overlay_disable(self, controller):
        """set_fiducial_overlay should disable detection."""
        controller.set_fiducial_overlay(True)
        controller.set_fiducial_overlay(False)

        assert controller.show_fiducials is False

    @patch("ui.controllers.calibration_overlay.detect_apriltags")
    def test_process_fiducial_detection_found(self, mock_detect, controller):
        """process_fiducial_detection should return detections when found."""
        mock_detection = Mock()
        mock_detect.return_value = ([mock_detection], None)

        controller.set_fiducial_overlay(True)
        frame = np.zeros((100, 100), dtype=np.uint8)

        result = controller.process_fiducial_detection(frame)

        assert result is not None
        assert len(result) == 1
        assert controller.fiducial_error is None

    @patch("ui.controllers.calibration_overlay.detect_apriltags")
    def test_process_fiducial_detection_error(self, mock_detect, controller):
        """process_fiducial_detection should capture errors."""
        mock_detect.return_value = ([], "Detection error")

        controller.set_fiducial_overlay(True)
        frame = np.zeros((100, 100), dtype=np.uint8)

        result = controller.process_fiducial_detection(frame)

        assert result == []
        assert controller.fiducial_error == "Detection error"

    def test_process_fiducial_detection_disabled(self, controller):
        """process_fiducial_detection should return None when disabled."""
        frame = np.zeros((100, 100), dtype=np.uint8)

        result = controller.process_fiducial_detection(frame)

        assert result is None


class TestProcessFrame:
    """Tests for combined frame processing."""

    @pytest.fixture
    def controller(self):
        """Create CalibrationOverlayController."""
        return CalibrationOverlayController(
            target_stride=1,
            fiducial_stride=1,
        )

    @patch("ui.controllers.calibration_overlay.detect_apriltags")
    @patch("ui.controllers.calibration_overlay.cv2.findChessboardCorners")
    def test_process_frame_both_enabled(self, mock_checkerboard, mock_fiducial, controller):
        """process_frame should process both overlays when enabled."""
        mock_corners = np.array([[[10.0, 20.0]]])
        mock_checkerboard.return_value = (True, mock_corners)

        mock_detection = Mock()
        mock_fiducial.return_value = ([mock_detection], None)

        controller.set_target_overlay(True)
        controller.set_fiducial_overlay(True)
        frame = np.zeros((100, 100), dtype=np.uint8)

        checkerboard, fiducials = controller.process_frame(frame)

        assert checkerboard is not None
        assert fiducials is not None

    def test_process_frame_both_disabled(self, controller):
        """process_frame should return None for both when disabled."""
        frame = np.zeros((100, 100), dtype=np.uint8)

        checkerboard, fiducials = controller.process_frame(frame)

        assert checkerboard is None
        assert fiducials is None


class TestGrayscaleConversion:
    """Tests for grayscale conversion."""

    @pytest.fixture
    def controller(self):
        """Create CalibrationOverlayController."""
        return CalibrationOverlayController()

    def test_to_grayscale_already_gray(self, controller):
        """_to_grayscale should return grayscale images unchanged."""
        gray = np.zeros((100, 100), dtype=np.uint8)

        result = controller._to_grayscale(gray)

        assert result.shape == (100, 100)

    @patch("ui.controllers.calibration_overlay.cv2.cvtColor")
    def test_to_grayscale_color(self, mock_cvt, controller):
        """_to_grayscale should convert color images."""
        color = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cvt.return_value = np.zeros((100, 100), dtype=np.uint8)

        result = controller._to_grayscale(color)

        mock_cvt.assert_called_once()
        assert result.shape == (100, 100)


class TestFrameStriding:
    """Tests for frame stride behavior."""

    def test_target_stride(self):
        """Target detection should only process every N frames."""
        controller = CalibrationOverlayController(target_stride=3)
        controller.set_target_overlay(True)

        with patch("ui.controllers.calibration_overlay.cv2.findChessboardCorners") as mock_find:
            mock_find.return_value = (False, None)
            frame = np.zeros((10, 10), dtype=np.uint8)

            # Process 5 frames - should only call detection on frames 3 and 6
            for i in range(6):
                controller.process_target_detection(frame)

            # Called on frame 3 (index 2) and frame 6 (index 5)
            assert mock_find.call_count == 2

    def test_fiducial_stride(self):
        """Fiducial detection should only process every N frames."""
        controller = CalibrationOverlayController(fiducial_stride=2)
        controller.set_fiducial_overlay(True)

        with patch("ui.controllers.calibration_overlay.detect_apriltags") as mock_detect:
            mock_detect.return_value = ([], None)
            frame = np.zeros((10, 10), dtype=np.uint8)

            # Process 4 frames - should call detection on frames 2 and 4
            for i in range(4):
                controller.process_fiducial_detection(frame)

            assert mock_detect.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

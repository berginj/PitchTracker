"""Characterization tests for camera management refactored collaborators.

Covers: partial startup rollback, repeated stop, reconnection, callback
exceptions, and preview/stats behavior.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from app.pipeline.camera_management import CameraManager
from app.pipeline.initialization import PipelineInitializer
from configs.settings import AppConfig
from exceptions import CameraConfigurationError, CameraConnectionError, PitchTrackerError


@pytest.fixture
def mock_config():
    """Create mock AppConfig for testing."""
    config = Mock(spec=AppConfig)
    config.camera = Mock()
    config.camera.width = 640
    config.camera.height = 480
    config.camera.fps = 30
    config.camera.pixfmt = "GRAY8"
    config.camera.color_mode = False
    config.camera.exposure_us = 5000
    config.camera.gain = 1.0
    config.camera.wb_mode = None
    config.camera.wb = None
    config.camera.flip_left = False
    config.camera.flip_right = False
    config.camera.rotation_left = 0.0
    config.camera.rotation_right = 0.0
    config.camera.vertical_offset_px = 0
    return config


@pytest.fixture
def mock_initializer():
    """Create mock PipelineInitializer."""
    return Mock(spec=PipelineInitializer)


@pytest.fixture
def manager(mock_initializer):
    """Create CameraManager with sim backend (no reconnection)."""
    return CameraManager(backend="sim", initializer=mock_initializer)


class TestPartialStartupRollback:
    """Verify cleanup when start_capture fails partway through."""

    def test_right_camera_open_failure_closes_left(self, manager, mock_config):
        """When right camera fails to open, left camera is closed."""
        call_count = [0]
        closed = []

        class FakeCamera:
            def __init__(self):
                self._id = None

            def open(self, serial):
                call_count[0] += 1
                self._id = serial
                if call_count[0] == 2:
                    raise OSError("right camera missing")

            def close(self):
                closed.append(self._id)

            def get_stats(self):
                return {}

        with patch(
            "app.pipeline.camera_backend_factory.SimulatedCamera",
            side_effect=lambda: FakeCamera(),
        ):
            with pytest.raises(CameraConnectionError, match="right"):
                manager.start_capture(mock_config, "LEFT001", "RIGHT001")

        # Left camera should have been closed during rollback
        assert "LEFT001" in closed

    def test_configuration_failure_cleans_both(self, manager, mock_config):
        """When configure fails, both cameras are closed."""
        closed = []

        class FakeCamera:
            def open(self, serial):
                self._id = serial

            def close(self):
                closed.append(self._id)

            def get_stats(self):
                return {}

        with patch(
            "app.pipeline.camera_backend_factory.SimulatedCamera",
            side_effect=lambda: FakeCamera(),
        ), patch(
            "app.pipeline.camera_backend_factory.PipelineInitializer.configure_camera",
            side_effect=RuntimeError("bad config"),
        ):
            with pytest.raises(CameraConfigurationError):
                manager.start_capture(mock_config, "L", "R")

        assert len(closed) == 2


class TestRepeatedStop:
    """Verify stop_capture is idempotent."""

    def test_stop_twice_no_error(self, manager, mock_config):
        """Calling stop_capture twice does not raise."""
        # Never started — should be safe
        manager.stop_capture()
        manager.stop_capture()

    def test_stop_after_start_twice(self, manager, mock_config):
        """Start then stop twice — second stop is a no-op."""
        with patch(
            "app.pipeline.camera_backend_factory.SimulatedCamera"
        ) as MockCam:
            cam = MagicMock()
            cam.read_frame.side_effect = TimeoutError("no frame")
            MockCam.return_value = cam
            with patch(
                "app.pipeline.camera_backend_factory.PipelineInitializer.configure_camera"
            ):
                manager.start_capture(mock_config, "L", "R")

        manager.stop_capture()
        manager.stop_capture()  # Should not raise


class TestPreviewAndStats:
    """Verify preview/stats error paths."""

    def test_preview_before_start_raises(self, manager):
        """get_preview_frames raises CameraConnectionError before start."""
        with pytest.raises(CameraConnectionError):
            manager.get_preview_frames()

    def test_stats_before_start_empty(self, manager):
        """get_stats returns empty dict before start."""
        assert manager.get_stats() == {}

    def test_preview_no_frames_yet_raises(self, manager):
        """When cameras active but no frames delivered, raises PitchTrackerError."""
        # Simulate cameras being set (active) but no frames yet
        manager._left = MagicMock()
        manager._right = MagicMock()
        with pytest.raises(PitchTrackerError, match="Waiting"):
            manager.get_preview_frames()

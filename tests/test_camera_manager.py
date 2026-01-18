"""Tests for CameraManager error handling and frame validation.

Validates that camera failures are detected and handled gracefully,
with proper error reporting and health monitoring.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from app.pipeline.camera_management import CameraManager
from app.pipeline.initialization import PipelineInitializer
from configs.settings import AppConfig
from contracts import Frame
from exceptions import CameraConnectionError


@pytest.fixture
def mock_config():
    """Create mock AppConfig for testing."""
    config = Mock(spec=AppConfig)
    config.camera = Mock()
    config.camera.width = 640
    config.camera.height = 480
    config.camera.fps = 30
    config.camera.pixfmt = "GRAY8"
    config.camera.exposure_us = 5000
    config.camera.gain = 1.0
    config.camera.wb_mode = None
    config.camera.wb = None
    return config


@pytest.fixture
def mock_initializer():
    """Create mock PipelineInitializer."""
    initializer = Mock(spec=PipelineInitializer)
    return initializer


@pytest.fixture
def camera_manager(mock_initializer):
    """Create CameraManager with mocked backend."""
    return CameraManager(backend="sim", initializer=mock_initializer)


class TestCameraManagerInitialization:
    """Test CameraManager initialization and state."""

    def test_initial_state(self, camera_manager):
        """Manager should start in non-capturing state."""
        assert not camera_manager.is_capturing()

        left_id, right_id = camera_manager.get_camera_ids()
        assert left_id is None
        assert right_id is None

    def test_callbacks_can_be_set(self, camera_manager):
        """Frame and error callbacks should be settable."""
        frame_callback = Mock()
        error_callback = Mock()

        camera_manager.set_frame_callback(frame_callback)
        camera_manager.set_error_callback(error_callback)

        # Callbacks stored (no exception raised)
        assert True


class TestCameraManagerStartCapture:
    """Test camera capture startup."""

    def test_start_capture_opens_cameras(self, camera_manager, mock_config, mock_initializer):
        """start_capture should open and configure both cameras."""
        with patch.object(camera_manager, "_build_camera") as mock_build:
            mock_left = MagicMock()
            mock_right = MagicMock()
            mock_build.side_effect = [mock_left, mock_right]

            camera_manager.start_capture(mock_config, "left_serial", "right_serial")

            # Should have opened both cameras
            mock_left.open.assert_called_once_with("left_serial")
            mock_right.open.assert_called_once_with("right_serial")

            # Should be capturing
            assert camera_manager.is_capturing()

    def test_start_capture_configures_cameras(
        self, camera_manager, mock_config, mock_initializer
    ):
        """start_capture should configure cameras via initializer."""
        with patch.object(camera_manager, "_build_camera") as mock_build:
            mock_left = MagicMock()
            mock_right = MagicMock()
            mock_build.side_effect = [mock_left, mock_right]

            with patch.object(
                PipelineInitializer, "configure_camera"
            ) as mock_configure:
                camera_manager.start_capture(
                    mock_config, "left_serial", "right_serial"
                )

                # Should have configured both cameras
                assert mock_configure.call_count == 2

    def test_start_capture_starts_threads(self, camera_manager, mock_config):
        """start_capture should start capture threads."""
        with patch.object(camera_manager, "_build_camera") as mock_build:
            mock_left = Mock()
            mock_right = Mock()
            mock_build.side_effect = [mock_left, mock_right]

            # Mock methods
            mock_left.open = Mock()
            mock_right.open = Mock()
            mock_left.close = Mock()
            mock_right.close = Mock()

            # Mock frame reading to prevent blocking
            mock_left.read_frame = Mock(side_effect=TimeoutError())
            mock_right.read_frame = Mock(side_effect=TimeoutError())

            camera_manager.start_capture(mock_config, "left_serial", "right_serial")

            # Threads should be created
            assert camera_manager._left_thread is not None
            assert camera_manager._right_thread is not None
            assert camera_manager._left_thread.is_alive()
            assert camera_manager._right_thread.is_alive()

            # Cleanup
            camera_manager.stop_capture()

    def test_start_capture_failure_cleans_up(
        self, camera_manager, mock_config, mock_initializer
    ):
        """Failed start_capture should clean up cameras."""
        with patch.object(camera_manager, "_build_camera") as mock_build:
            mock_left = MagicMock()
            mock_right = MagicMock()
            mock_build.side_effect = [mock_left, mock_right]

            # Make right camera fail to open
            mock_right.open.side_effect = CameraConnectionError(
                "Failed", camera_id="right"
            )

            with pytest.raises(CameraConnectionError):
                camera_manager.start_capture(
                    mock_config, "left_serial", "right_serial"
                )

            # Should have closed left camera during cleanup
            mock_left.close.assert_called()


class TestCameraManagerStopCapture:
    """Test camera capture shutdown."""

    def test_stop_capture_stops_threads(self, camera_manager, mock_config):
        """stop_capture should stop capture threads."""
        with patch.object(camera_manager, "_build_camera") as mock_build:
            mock_left = Mock()
            mock_right = Mock()
            mock_build.side_effect = [mock_left, mock_right]

            # Mock methods
            mock_left.open = Mock()
            mock_right.open = Mock()
            mock_left.close = Mock()
            mock_right.close = Mock()
            mock_left.read_frame = Mock(side_effect=TimeoutError())
            mock_right.read_frame = Mock(side_effect=TimeoutError())

            camera_manager.start_capture(mock_config, "left_serial", "right_serial")
            assert camera_manager.is_capturing()

            camera_manager.stop_capture()
            assert not camera_manager.is_capturing()

            # Threads should be stopped
            time.sleep(0.2)  # Give threads time to exit
            if camera_manager._left_thread:
                assert not camera_manager._left_thread.is_alive()
            if camera_manager._right_thread:
                assert not camera_manager._right_thread.is_alive()

    def test_stop_capture_closes_cameras(self, camera_manager, mock_config):
        """stop_capture should close cameras."""
        with patch.object(camera_manager, "_build_camera") as mock_build:
            mock_left = Mock()
            mock_right = Mock()
            mock_build.side_effect = [mock_left, mock_right]

            mock_left.open = Mock()
            mock_right.open = Mock()
            mock_left.close = Mock()
            mock_right.close = Mock()
            mock_left.read_frame = Mock(side_effect=TimeoutError())
            mock_right.read_frame = Mock(side_effect=TimeoutError())

            camera_manager.start_capture(mock_config, "left_serial", "right_serial")
            camera_manager.stop_capture()

            # Should have closed both cameras
            mock_left.close.assert_called()
            mock_right.close.assert_called()

    def test_stop_capture_is_idempotent(self, camera_manager):
        """stop_capture should be safe to call multiple times."""
        # Should not raise even if never started
        camera_manager.stop_capture()
        camera_manager.stop_capture()


class TestFrameValidation:
    """Test frame validation logic."""

    def test_validate_frame_accepts_valid_frame(self, camera_manager):
        """Valid frames should pass validation."""
        frame = Frame(
            camera_id="test",
            frame_index=1,
            t_capture_monotonic_ns=time.monotonic_ns(),
            image=np.ones((480, 640), dtype=np.uint8),
            width=640,
            height=480,
            pixfmt="GRAY8",
        )

        assert camera_manager._validate_frame("test", frame)

    def test_validate_frame_rejects_none_frame(self, camera_manager):
        """None frames should be rejected."""
        assert not camera_manager._validate_frame("test", None)

    def test_validate_frame_rejects_none_image(self, camera_manager):
        """Frames with None image should be rejected."""
        frame = Frame(
            camera_id="test",
            frame_index=1,
            t_capture_monotonic_ns=time.monotonic_ns(),
            image=None,
            width=640,
            height=480,
            pixfmt="GRAY8",
        )

        assert not camera_manager._validate_frame("test", frame)

    def test_validate_frame_rejects_invalid_dimensions(self, camera_manager):
        """Frames with invalid dimensions should be rejected."""
        frame = Frame(
            camera_id="test",
            frame_index=1,
            t_capture_monotonic_ns=time.monotonic_ns(),
            image=np.ones((480, 640), dtype=np.uint8),
            width=0,  # Invalid
            height=480,
            pixfmt="GRAY8",
        )

        assert not camera_manager._validate_frame("test", frame)

    def test_validate_frame_rejects_all_zero_image(self, camera_manager):
        """All-zero frames should be rejected (common failure mode)."""
        frame = Frame(
            camera_id="test",
            frame_index=1,
            t_capture_monotonic_ns=time.monotonic_ns(),
            image=np.zeros((480, 640), dtype=np.uint8),  # All black
            width=640,
            height=480,
            pixfmt="GRAY8",
        )

        assert not camera_manager._validate_frame("test", frame)


class TestFrameCallback:
    """Test frame capture callback."""

    def test_callback_invoked_on_frame(self, camera_manager, mock_config):
        """Frame callback should be invoked for each frame."""
        with patch.object(camera_manager, "_build_camera") as mock_build:
            mock_cam = Mock()
            mock_build.return_value = mock_cam

            # Mock methods
            mock_cam.open = Mock()
            mock_cam.close = Mock()

            # Create valid frame
            test_frame = Frame(
                camera_id="test",
                frame_index=1,
                t_capture_monotonic_ns=time.monotonic_ns(),
                image=np.ones((480, 640), dtype=np.uint8),
                width=640,
                height=480,
                pixfmt="GRAY8",
            )

            # Return frame once, then timeout to stop loop
            call_count = {"count": 0}

            def read_side_effect(*args, **kwargs):
                call_count["count"] += 1
                if call_count["count"] == 1:
                    return test_frame
                raise TimeoutError()

            mock_cam.read_frame = Mock(side_effect=read_side_effect)

            # Set callback
            callback = Mock()
            camera_manager.set_frame_callback(callback)

            # Start capture (will call callback)
            camera_manager.start_capture(mock_config, "test", "test")

            # Give thread time to process frame
            time.sleep(0.2)

            # Callback should have been invoked
            callback.assert_called()

            # Cleanup
            camera_manager.stop_capture()


class TestErrorHandling:
    """Test error detection and reporting."""

    def test_consecutive_failures_trigger_error(self, camera_manager, mock_config):
        """Consecutive frame read failures should trigger error callback."""
        with patch.object(camera_manager, "_build_camera") as mock_build:
            mock_cam = Mock()
            mock_build.return_value = mock_cam

            # Mock methods
            mock_cam.open = Mock()
            mock_cam.close = Mock()

            # Always fail
            mock_cam.read_frame = Mock(side_effect=Exception("Camera error"))

            # Set error callback
            error_callback = Mock()
            camera_manager.set_error_callback(error_callback)

            # Start capture
            camera_manager.start_capture(mock_config, "test", "test")

            # Give thread time to accumulate failures (10 failures max)
            time.sleep(1.0)

            # Error callback should have been invoked
            error_callback.assert_called()
            args = error_callback.call_args[0]
            assert "failed" in args[1].lower()

            # Cleanup
            camera_manager.stop_capture()

    def test_timeout_errors_not_counted_as_failures(self, camera_manager, mock_config):
        """TimeoutError should not count as consecutive failure."""
        with patch.object(camera_manager, "_build_camera") as mock_build:
            mock_cam = Mock()
            mock_build.return_value = mock_cam

            # Mock methods
            mock_cam.open = Mock()
            mock_cam.close = Mock()

            # Always timeout (expected behavior)
            mock_cam.read_frame = Mock(side_effect=TimeoutError())

            # Set error callback
            error_callback = Mock()
            camera_manager.set_error_callback(error_callback)

            # Start capture
            camera_manager.start_capture(mock_config, "test", "test")

            # Give thread time to process timeouts
            time.sleep(0.5)

            # Error callback should NOT have been invoked for timeouts
            error_callback.assert_not_called()

            # Cleanup
            camera_manager.stop_capture()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

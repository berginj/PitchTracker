"""Characterization tests for CameraLifecycleManager reconnection logic."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, Mock

import pytest

from app.pipeline.camera_lifecycle import CameraLifecycleManager
from app.pipeline.camera_backend_factory import CameraBackendFactory
from app.pipeline.camera_frame_router import CameraFrameRouter
from configs.settings import AppConfig


@pytest.fixture
def mock_config():
    config = Mock(spec=AppConfig)
    config.camera = Mock()
    return config


@pytest.fixture
def lifecycle_parts():
    """Create lifecycle manager with mocked collaborators."""
    factory = MagicMock(spec=CameraBackendFactory)
    factory.backend = "sim"
    router = CameraFrameRouter()
    lock = threading.Lock()
    lifecycle = CameraLifecycleManager(factory, router, lock)
    return lifecycle, factory, router


class TestReconnection:
    """Test reconnection flow through lifecycle manager."""

    def test_reconnect_success(self, lifecycle_parts, mock_config):
        """Successful reconnection updates camera ref and starts thread."""
        lifecycle, factory, router = lifecycle_parts

        new_cam = MagicMock()
        build_fn = MagicMock(return_value=new_cam)

        left_ref = [None]
        right_ref = [None]

        lifecycle.initialize(
            config=mock_config,
            left_id="L001",
            right_id="R001",
            left_ref_setter=lambda c: left_ref.__setitem__(0, c),
            right_ref_setter=lambda c: right_ref.__setitem__(0, c),
            build_camera_fn=build_fn,
        )

        # Simulate calling reconnect for left
        result = lifecycle._try_reconnect_camera("left")
        assert result is True
        assert left_ref[0] is new_cam
        build_fn.assert_called_once()
        factory.open_camera.assert_called_once_with(new_cam, "L001", "left")
        factory.configure_camera.assert_called_once_with(new_cam, mock_config, True)

    def test_reconnect_failure_returns_false(self, lifecycle_parts, mock_config):
        """Failed reconnection returns False and cleans up."""
        lifecycle, factory, router = lifecycle_parts

        factory.open_camera.side_effect = OSError("no camera")
        build_fn = MagicMock(return_value=MagicMock())

        lifecycle.initialize(
            config=mock_config,
            left_id="L001",
            right_id="R001",
            left_ref_setter=lambda c: None,
            right_ref_setter=lambda c: None,
            build_camera_fn=build_fn,
        )

        result = lifecycle._try_reconnect_camera("left")
        assert result is False

    def test_reconnect_missing_serial_returns_false(self, lifecycle_parts, mock_config):
        """Reconnect with missing serial returns False immediately."""
        lifecycle, factory, router = lifecycle_parts

        lifecycle.initialize(
            config=mock_config,
            left_id="",
            right_id="R001",
            left_ref_setter=lambda c: None,
            right_ref_setter=lambda c: None,
        )

        result = lifecycle._try_reconnect_camera("left")
        assert result is False

    def test_reconnect_closes_old_camera_before_open(self, lifecycle_parts, mock_config):
        """Old camera device is closed before factory opens replacement."""
        lifecycle, factory, router = lifecycle_parts

        call_order = []

        old_cam = MagicMock()
        old_cam.close.side_effect = lambda: call_order.append("old_close")

        new_cam = MagicMock()
        build_fn = MagicMock(return_value=new_cam)
        factory.open_camera.side_effect = lambda *a, **kw: call_order.append("open_new")
        factory.configure_camera.side_effect = lambda *a, **kw: call_order.append("configure_new")

        def get_camera(camera_id):
            if camera_id == "left":
                return old_cam
            return None

        lifecycle.initialize(
            config=mock_config,
            left_id="L001",
            right_id="R001",
            left_ref_setter=lambda c: None,
            right_ref_setter=lambda c: None,
            build_camera_fn=build_fn,
            get_camera_fn=get_camera,
        )

        result = lifecycle._try_reconnect_camera("left")
        assert result is True
        old_cam.close.assert_called_once()
        # Close must happen before open
        assert call_order.index("old_close") < call_order.index("open_new")

    def test_reconnect_closes_old_camera_on_failure_path(self, lifecycle_parts, mock_config):
        """Old camera is closed even when reconnection ultimately fails."""
        lifecycle, factory, router = lifecycle_parts

        old_cam = MagicMock()
        new_cam = MagicMock()
        build_fn = MagicMock(return_value=new_cam)
        factory.open_camera.side_effect = OSError("USB gone")

        def get_camera(camera_id):
            return old_cam

        lifecycle.initialize(
            config=mock_config,
            left_id="L001",
            right_id="R001",
            left_ref_setter=lambda c: None,
            right_ref_setter=lambda c: None,
            build_camera_fn=build_fn,
            get_camera_fn=get_camera,
        )

        result = lifecycle._try_reconnect_camera("left")
        assert result is False
        # Old camera still closed exactly once
        old_cam.close.assert_called_once()

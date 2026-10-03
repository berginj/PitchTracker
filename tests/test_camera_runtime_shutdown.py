"""Fake-only coverage for retained camera reader and reconnect ownership."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from app.camera.reconnection import CameraReconnectionManager
from app.events.event_bus import EventBus
from app.pipeline.camera_frame_router import CameraFrameRouter
from app.pipeline.camera_lifecycle import CameraLifecycleManager
from app.pipeline.camera_management import CameraManager
from app.services.capture.implementation import CaptureServiceImpl
from contracts import Frame
from exceptions import CameraConnectionError


def _frame() -> Frame:
    return Frame("fake", 1, 1, np.ones((2, 2), dtype=np.uint8), 2, 2, "GRAY8")


def test_blocked_readers_remain_owned_and_devices_stay_open_until_retry(monkeypatch):
    manager = CameraManager("sim", Mock())
    release = threading.Event()
    started = [threading.Event(), threading.Event()]
    cameras = [Mock(), Mock()]
    for camera, entry in zip(cameras, started):
        def read(timeout_ms, entry=entry):
            entry.set()
            assert release.wait(2.0)
            return _frame()
        camera.read_frame.side_effect = read
    manager._left, manager._right = cameras
    router = manager._frame_router
    stop = router.stop
    monkeypatch.setattr(router, "stop", lambda: stop(timeout=0.01))
    router.start_threads(*cameras)
    assert all(entry.wait(0.5) for entry in started)
    old_thread = router.get_thread("left")
    try:
        with pytest.raises(CameraConnectionError, match="still stopping"):
            manager.stop_capture()
        assert router.get_thread("left") is old_thread
        assert old_thread.is_alive()
        for camera in cameras:
            camera.close.assert_not_called()
        with pytest.raises(CameraConnectionError, match="still stopping"):
            manager.start_capture(Mock(), "left", "right")
        with pytest.raises(CameraConnectionError, match="still stopping"):
            router.start_threads(*cameras)
        assert router.left_stop.is_set()
    finally:
        release.set()
        old_thread.join(0.5)
        router.get_thread("right").join(0.5)
        manager.stop_capture()
    assert router.get_thread("left") is None
    assert manager._left is None
    for camera in cameras:
        camera.close.assert_called_once()


def test_capture_stop_releases_callback_lock_and_retains_timeout_state():
    service = CaptureServiceImpl(EventBus(), "sim")
    service._capturing = True
    manager = Mock()
    service._camera_mgr = manager
    callback_exited = threading.Event()

    def stop():
        thread = threading.Thread(target=lambda: (
            service._on_frame_captured_internal("left", _frame()), callback_exited.set()
        ))
        thread.start()
        assert callback_exited.wait(0.5)
        thread.join()
        raise CameraConnectionError("injected reader still stopping")

    manager.stop_capture.side_effect = stop
    with pytest.raises(CameraConnectionError, match="injected"):
        service.stop_capture()
    assert service.is_capturing()
    with pytest.raises(CameraConnectionError, match="still stopping"):
        service.start_capture(Mock(), "left", "right")
    manager.start_capture.assert_not_called()
    manager.stop_capture.side_effect = None
    service.stop_capture()
    assert not service.is_capturing()
    service.start_capture(Mock(), "left", "right")
    service.stop_capture()


def test_reconnect_refuses_to_close_old_camera_while_reader_is_alive():
    router = CameraFrameRouter()
    router._capture_running = True
    reader = Mock()
    reader.is_alive.return_value = True
    router.set_thread("left", reader)
    old_camera = Mock()
    factory = Mock()
    lifecycle = CameraLifecycleManager(factory, router, threading.Lock())
    lifecycle.initialize(Mock(), "left", "right", Mock(), Mock(), get_camera_fn=lambda _: old_camera)
    assert lifecycle._try_reconnect_camera("left") is False
    old_camera.close.assert_not_called()
    factory.build_camera.assert_not_called()
    assert router.get_thread("left") is reader
    assert router.left_stop.is_set()
    assert lifecycle.shutdown(timeout=0.01)


@pytest.mark.parametrize("blocked_stage", ["open_camera", "configure_camera"])
def test_late_reconnect_is_rejected_and_cleaned_after_shutdown(blocked_stage):
    router = CameraFrameRouter()
    router._capture_running = True
    router.start_single_thread = Mock()
    replacement = Mock()
    factory = Mock()
    factory.build_camera.return_value = replacement
    started = threading.Event()
    release = threading.Event()

    def block(*args):
        started.set()
        assert release.wait(2.0)

    getattr(factory, blocked_stage).side_effect = block
    setter = Mock()
    lifecycle = CameraLifecycleManager(factory, router, threading.Lock())
    lifecycle.initialize(Mock(), "left", "right", setter, Mock())
    outcome = []
    thread = threading.Thread(target=lambda: outcome.append(lifecycle._try_reconnect_camera("left")))
    thread.start()
    assert started.wait(0.5)
    try:
        assert not lifecycle.shutdown(timeout=0.01)
        router.request_stop()
        with pytest.raises(CameraConnectionError, match="still stopping"):
            lifecycle.initialize(Mock(), "left", "right", setter, Mock())
    finally:
        release.set()
        thread.join(0.5)
    assert outcome == [False]
    setter.assert_not_called()
    router.start_single_thread.assert_not_called()
    replacement.close.assert_called_once()
    assert router.left_stop.is_set()
    assert lifecycle.shutdown(timeout=0.01)


def test_unregister_interrupts_backoff_before_opening_camera():
    manager = CameraReconnectionManager(base_delay=30.0)
    callback = Mock(return_value=True)
    manager.set_reconnect_callback(callback)
    manager.register_camera("left")
    manager.report_disconnection("left")
    manager.unregister_camera("left")
    assert manager.wait_stopped(0.5)
    callback.assert_not_called()
    assert manager.get_camera_state("left") is None


def test_unregister_retains_blocked_reconnect_and_does_not_restore_state():
    manager = CameraReconnectionManager(base_delay=0.0)
    started = threading.Event()
    release = threading.Event()

    def reconnect(camera_id):
        started.set()
        assert release.wait(2.0)
        return True

    manager.set_reconnect_callback(reconnect)
    manager.register_camera("left")
    manager.report_disconnection("left")
    assert started.wait(0.5)
    manager.unregister_camera("left")
    try:
        assert not manager.wait_stopped(0.01)
        assert manager._reconnect_threads["left"].is_alive()
        with pytest.raises(CameraConnectionError, match="still stopping"):
            manager.register_camera("left")
    finally:
        release.set()
        assert manager.wait_stopped(0.5)
    assert manager.get_camera_state("left") is None
    manager.register_camera("left")
    manager.unregister_camera("left")


def test_simulator_skips_physical_camera_cache_warming(monkeypatch):
    from ui.coaching.session_controller import SessionController

    controller = SessionController.__new__(SessionController)
    controller._host = SimpleNamespace(_backend="sim")
    launch = Mock()
    monkeypatch.setattr("ui.coaching.session_controller.threading.Thread", launch)
    controller.warm_camera_cache_async()
    launch.assert_not_called()


def test_failed_native_close_remains_owned_until_successful_stop_retry():
    manager = CameraManager("sim", Mock())
    camera = Mock()
    camera.close.side_effect = [OSError("injected close failure"), None]
    manager._left = camera
    with pytest.raises(CameraConnectionError, match="close failed"):
        manager.stop_capture()
    assert manager._left is camera
    with pytest.raises(CameraConnectionError, match="still stopping"):
        manager.start_capture(Mock(), "left", "right")
    manager.stop_capture()
    assert manager._left is None
    assert camera.close.call_count == 2


def test_rejected_replacement_close_failure_is_retained_for_shutdown_retry():
    router = CameraFrameRouter()
    router._capture_running = True
    replacement = Mock()
    replacement.close.side_effect = [OSError("injected close failure"), None]
    factory = Mock()
    factory.build_camera.return_value = replacement
    lifecycle = CameraLifecycleManager(factory, router, threading.Lock())
    lifecycle.initialize(Mock(), "left", "right", Mock(), Mock())
    # Cancel between native open completion and configuration/publication.
    factory.open_camera.side_effect = lambda *args: lifecycle._cancel.set()
    assert lifecycle._try_reconnect_camera("left") is False
    assert lifecycle._rejected_cameras == [replacement]
    assert lifecycle.shutdown(timeout=0.01)
    assert lifecycle._rejected_cameras == []
    assert replacement.close.call_count == 2

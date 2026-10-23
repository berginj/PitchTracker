"""Camera ownership for diagnostic setup; no measurement readiness is granted."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
from typing import Iterator

from app.pipeline.initialization import PipelineInitializer
from capture.camera_device import CameraDevice
from contracts.setup_capture import SetupCaptureRequest
from configs.settings import load_config
from exceptions import CameraConnectionError
from log_config.logger import get_logger

logger = get_logger(__name__)


def setup_camera_type(backend: str) -> type[CameraDevice]:
    """Select only supported setup backends; acquisition remains explicit."""
    if backend == "sim":
        from capture.simulated_camera import SimulatedCamera
        return SimulatedCamera
    if backend == "opencv":
        from capture.opencv_backend import OpenCVCamera
        return OpenCVCamera
    if backend == "uvc":
        from capture.uvc_backend import UvcCamera
        return UvcCamera
    raise ValueError("Unsupported setup camera backend")


@contextmanager
def open_setup_pair(request: SetupCaptureRequest) -> Iterator[tuple[CameraDevice, CameraDevice]]:
    """Use the one-shot setup configuration path, including invalid diagnostic images."""
    if hashlib.sha256(request.config_path.read_bytes()).hexdigest() != request.config_sha256:
        raise ValueError("Focus configuration changed before camera acquisition")
    config = load_config(request.config_path)
    camera_type = setup_camera_type(request.backend)
    left, right = camera_type(), camera_type()
    if request.backend == "uvc":
        from capture.device_discovery import list_uvc_devices
        from capture.uvc_backend import UvcCamera
        devices = list_uvc_devices()
        for camera in (left, right):
            if isinstance(camera, UvcCamera):
                camera.set_discovered_devices(devices)
    try:
        left.open(request.left_camera_id)
        right.open(request.right_camera_id)
        PipelineInitializer.configure_camera(left, config, is_left=True)
        PipelineInitializer.configure_camera(right, config, is_left=False)
        yield left, right
    finally:
        errors = []
        for camera in (left, right):
            try:
                camera.close()
            except Exception as exc:
                logger.exception("Diagnostic setup camera close failed")
                errors.append(exc)
        if errors:
            raise CameraConnectionError("Diagnostic camera cleanup failed") from errors[0]

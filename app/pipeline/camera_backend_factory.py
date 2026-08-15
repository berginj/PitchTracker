"""Camera backend construction and configuration."""

from __future__ import annotations

import logging

from capture import CameraDevice, SimulatedCamera, UvcCamera
from capture.opencv_backend import OpenCVCamera
from configs.settings import AppConfig
from exceptions import (
    CameraConfigurationError,
    CameraConnectionError,
)

from app.events import publish_error, ErrorCategory, ErrorSeverity

from .initialization import PipelineInitializer

logger = logging.getLogger(__name__)


class CameraBackendFactory:
    """Builds and configures camera devices based on backend type."""

    def __init__(self, backend: str):
        """Initialize factory.

        Args:
            backend: Camera backend ("uvc", "opencv", or "sim")
        """
        self._backend = backend

    @property
    def backend(self) -> str:
        """Return configured backend name."""
        return self._backend

    def build_camera(self) -> CameraDevice:
        """Build camera instance based on backend.

        Returns:
            CameraDevice instance
        """
        if self._backend == "opencv":
            return OpenCVCamera()
        if self._backend == "sim":
            return SimulatedCamera()
        return UvcCamera()

    def open_camera(
        self, camera: CameraDevice, serial: str, label: str
    ) -> None:
        """Open a camera device by serial.

        Args:
            camera: Camera device to open
            serial: Camera serial number
            label: Camera label for error messages ("left" or "right")

        Raises:
            CameraConnectionError: If camera fails to open
        """
        try:
            logger.debug(f"Opening {label} camera: {serial}")
            camera.open(serial)
        except Exception as exc:
            logger.error(f"Failed to open {label} camera {serial}: {exc}")
            publish_error(
                category=ErrorCategory.CAMERA,
                severity=ErrorSeverity.CRITICAL,
                message=f"Failed to open {label} camera: {exc}",
                source="CameraBackendFactory.open_camera",
                exception=exc,
                camera_id=label,
                serial=serial,
            )
            error_msg = (
                f"Failed to open {label} camera (serial: {serial})\n\n"
                f"Error: {exc}\n\n"
                f"Possible solutions:\n"
                f"  • Check that the camera is plugged in\n"
                f"  • Try a different USB port (preferably USB 3.0)\n"
                f"  • Close other applications using the camera\n"
                f"  • Verify the camera serial/index is correct\n"
                f"  • Check Windows Device Manager for camera status"
            )
            raise CameraConnectionError(error_msg) from exc

    def configure_camera(
        self, camera: CameraDevice, config: AppConfig, is_left: bool
    ) -> None:
        """Configure a camera device.

        Args:
            camera: Camera device to configure
            config: Application configuration
            is_left: Whether this is the left camera

        Raises:
            CameraConfigurationError: If configuration fails
        """
        label = "left" if is_left else "right"
        try:
            logger.debug(f"Configuring {label} camera")
            PipelineInitializer.configure_camera(camera, config, is_left=is_left)
            if self._backend == "uvc":
                PipelineInitializer.verify_camera_configuration(camera, config)
        except Exception as exc:
            logger.error(f"Failed to configure {label} camera: {exc}")
            raise CameraConfigurationError(
                f"Failed to configure {label} camera: {exc}"
            ) from exc

    def open_and_configure(
        self,
        serial: str,
        config: AppConfig,
        is_left: bool,
    ) -> CameraDevice:
        """Build, open, and configure a camera in one step.

        Used by reconnection logic.

        Args:
            serial: Camera serial number
            config: Application configuration
            is_left: Whether this is the left camera

        Returns:
            Fully configured CameraDevice

        Raises:
            CameraConnectionError: If open fails
            CameraConfigurationError: If configuration fails
        """
        camera = self.build_camera()
        label = "left" if is_left else "right"
        try:
            self.open_camera(camera, serial, label)
            self.configure_camera(camera, config, is_left)
        except Exception:
            try:
                camera.close()
            except Exception as close_exc:
                logger.warning(f"Failed to close {label} camera after error: {close_exc}")
            raise
        return camera

"""UVC capture backend for Windows DirectShow devices."""

from __future__ import annotations

import json
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

import cv2

from contracts import Frame
from exceptions import (
    CameraConnectionError,
    CameraConfigurationError,
    CameraNotFoundError,
)
from log_config.logger import get_logger

from .camera_device import CameraDevice, CameraStats

logger = get_logger(__name__)


@dataclass
class _Stats:
    last_frame_ns: int = 0
    frames: int = 0
    dropped: int = 0
    fps_avg: float = 0.0
    fps_instant: float = 0.0


class UvcCamera(CameraDevice):
    def __init__(self) -> None:
        self._serial: Optional[str] = None
        self._friendly_name: Optional[str] = None
        self._capture: Optional[cv2.VideoCapture] = None
        self._stats = _Stats()
        self._deltas_ns: Deque[int] = deque(maxlen=240)
        self._width = 0
        self._height = 0
        self._fps = 0
        self._pixfmt = "GRAY8"

    def open(self, serial: str) -> None:
        """Open camera connection.

        Args:
            serial: Camera serial number or device index

        Raises:
            CameraNotFoundError: If camera is not found
            CameraConnectionError: If connection fails
        """
        try:
            logger.info(f"Opening camera with serial: {serial}")
            self._serial = serial
            target = self._resolve_device(serial)
            self._friendly_name = target

            if target.isdigit() and target == serial:
                self._capture = cv2.VideoCapture(int(serial), cv2.CAP_DSHOW)
            else:
                self._capture = cv2.VideoCapture(f"video={target}", cv2.CAP_DSHOW)

            if self._capture is None or not self._capture.isOpened():
                logger.error(f"Failed to open camera {serial}: capture object invalid")
                raise CameraConnectionError(
                    f"Failed to open camera for serial '{serial}'. "
                    "Check that the camera is connected and not in use by another application.",
                    camera_id=serial,
                )

            logger.info(f"Camera {serial} opened successfully: {self._friendly_name}")

        except CameraNotFoundError:
            raise
        except CameraConnectionError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error opening camera {serial}")
            raise CameraConnectionError(
                f"Unexpected error opening camera '{serial}': {e}",
                camera_id=serial,
            )

    def set_mode(self, width: int, height: int, fps: int, pixfmt: str) -> None:
        """Set camera capture mode.

        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            fps: Target frames per second
            pixfmt: Pixel format (GRAY8, RGB24, etc.)

        Raises:
            CameraConfigurationError: If mode setting fails
        """
        if self._capture is None:
            raise CameraConfigurationError(
                "Camera not opened. Call open() first.",
                camera_id=self._serial,
            )

        try:
            logger.debug(f"Setting camera mode: {width}x{height}@{fps}fps, format={pixfmt}")
            self._width = width
            self._height = height
            self._fps = fps
            self._pixfmt = pixfmt

            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self._capture.set(cv2.CAP_PROP_FPS, fps)

            # Verify settings were applied
            actual_width = self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self._capture.get(cv2.CAP_PROP_FPS)

            if (actual_width != width or actual_height != height):
                logger.warning(
                    f"Camera mode mismatch: requested {width}x{height}@{fps}fps, "
                    f"got {actual_width}x{actual_height}@{actual_fps}fps"
                )

            logger.info(f"Camera mode set successfully: {actual_width}x{actual_height}@{actual_fps}fps")

        except Exception as e:
            logger.error(f"Failed to set camera mode: {e}")
            raise CameraConfigurationError(
                f"Failed to set camera mode to {width}x{height}@{fps}fps: {e}",
                camera_id=self._serial,
            )

    def set_controls(
        self,
        exposure_us: int,
        gain: float,
        wb_mode: Optional[str],
        wb: Optional[int],
    ) -> None:
        if self._capture is None:
            raise RuntimeError("Camera not opened.")
        if exposure_us > 0:
            self._capture.set(cv2.CAP_PROP_EXPOSURE, float(exposure_us) / 1_000_000.0)
        self._capture.set(cv2.CAP_PROP_GAIN, gain)
        if wb_mode is None:
            self._capture.set(cv2.CAP_PROP_AUTO_WB, 0)
            if wb is not None:
                self._capture.set(cv2.CAP_PROP_WB_TEMPERATURE, wb)

    def read_frame(self, timeout_ms: int) -> Frame:
        """Read a frame from the camera.

        Args:
            timeout_ms: Read timeout in milliseconds (not used for OpenCV backend)

        Returns:
            Frame object with image data and metadata

        Raises:
            CameraConnectionError: If frame read fails (camera disconnected)
        """
        if self._capture is None:
            raise CameraConnectionError(
                "Camera not opened. Call open() first.",
                camera_id=self._serial,
            )

        ok, frame = self._capture.read()
        if not ok:
            self._stats.dropped += 1
            logger.warning(f"Failed to read frame from camera {self._serial}")
            raise CameraConnectionError(
                f"Failed to read frame from camera '{self._serial}'. Camera may be disconnected.",
                camera_id=self._serial,
            )
        if self._pixfmt == "GRAY8":
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        now_ns = time.monotonic_ns()
        if self._stats.last_frame_ns:
            delta_ns = now_ns - self._stats.last_frame_ns
            self._deltas_ns.append(delta_ns)
            delta_s = delta_ns / 1e9
            if delta_s > 0:
                self._stats.fps_instant = 1.0 / delta_s
                self._stats.fps_avg = (
                    (self._stats.fps_avg * self._stats.frames) + self._stats.fps_instant
                ) / (self._stats.frames + 1)
        self._stats.frames += 1
        self._stats.last_frame_ns = now_ns
        return Frame(
            camera_id=self._serial or "uvc",
            frame_index=self._stats.frames,
            t_capture_monotonic_ns=now_ns,
            image=frame,
            width=frame.shape[1],
            height=frame.shape[0],
            pixfmt=self._pixfmt,
        )

    def get_stats(self) -> CameraStats:
        jitter_p95_ms = 0.0
        if self._deltas_ns:
            samples = sorted(self._deltas_ns)
            index = int(0.95 * (len(samples) - 1))
            jitter_p95_ms = samples[index] / 1e6
        return CameraStats(
            fps_avg=self._stats.fps_avg,
            fps_instant=self._stats.fps_instant,
            jitter_p95_ms=jitter_p95_ms,
            dropped_frames=self._stats.dropped,
            queue_depth=0,
            capture_latency_ms=0.0,
        )

    def close(self) -> None:
        """Close camera connection and release resources."""
        if self._capture is not None:
            try:
                logger.info(f"Closing camera {self._serial}")
                self._capture.release()
                self._capture = None
                logger.debug(f"Camera {self._serial} closed successfully")
            except Exception as e:
                logger.error(f"Error closing camera {self._serial}: {e}")

    def _resolve_device(self, serial: str) -> str:
        """Resolve camera serial to device name.

        Args:
            serial: Camera serial number

        Returns:
            Device friendly name or index

        Raises:
            CameraNotFoundError: If camera is not found
        """
        try:
            devices = _list_camera_devices()
            matches = [
                dev for dev in devices if dev["serial"].lower() == serial.lower()
            ]

            if not matches:
                if serial.isdigit():
                    logger.debug(f"Using numeric index for camera: {serial}")
                    return serial

                available_serials = [dev['serial'] for dev in devices]
                logger.error(f"Camera not found: {serial}. Available: {available_serials}")
                raise CameraNotFoundError(
                    f"No camera found with serial '{serial}'. "
                    f"Available serials: {available_serials}",
                    camera_id=serial,
                )

            if len(matches) > 1:
                logger.error(f"Multiple cameras matched serial {serial}: {matches}")
                raise CameraNotFoundError(
                    f"Multiple cameras matched serial '{serial}': {matches}",
                    camera_id=serial,
                )

            friendly_name = matches[0]["friendly_name"]
            logger.debug(f"Resolved camera {serial} to {friendly_name}")
            return friendly_name

        except CameraNotFoundError:
            raise
        except Exception as e:
            logger.exception(f"Error resolving camera device {serial}")
            raise CameraNotFoundError(
                f"Error resolving camera device '{serial}': {e}",
                camera_id=serial,
            )


def _list_camera_devices() -> list[dict[str, str]]:
    devices = _query_pnp_devices("Camera")
    if not devices:
        devices = _query_pnp_devices("Image")
    output: list[dict[str, str]] = []
    for device in devices:
        if not device.get("present", True):
            continue
        if device.get("status") not in ("OK", None, ""):
            continue
        friendly = (device.get("FriendlyName") or "").strip()
        instance = (device.get("InstanceId") or "").strip()
        serial = (device.get("Serial") or "").strip()
        if not serial and instance:
            serial = instance.split("\\")[-1]
        if friendly:
            output.append(
                {
                    "friendly_name": friendly,
                    "instance_id": instance,
                    "serial": serial or friendly,
                }
            )
    return output


def _query_pnp_devices(device_class: str) -> list[dict[str, str]]:
    command = (
        "Get-PnpDevice -Class "
        + device_class
        + " | ForEach-Object { "
        + "$serial = (Get-PnpDeviceProperty -InstanceId $_.InstanceId "
        + "-KeyName 'DEVPKEY_Device_SerialNumber' -ErrorAction SilentlyContinue).Data; "
        + "[pscustomobject]@{FriendlyName=$_.FriendlyName;InstanceId=$_.InstanceId;Serial=$serial;Status=$_.Status;Present=$_.Present} "
        + "} | ConvertTo-Json"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    data = json.loads(result.stdout)
    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)]


def list_uvc_devices() -> list[dict[str, str]]:
    """Return UVC camera devices with friendly names and serials."""
    return _list_camera_devices()

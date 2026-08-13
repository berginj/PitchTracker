"""UVC capture backend for Windows DirectShow devices."""

from __future__ import annotations

import time
import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Sequence

import cv2
import numpy as np

from contracts import Frame
from exceptions import (
    CameraConnectionError,
    CameraConfigurationError,
    CameraNotFoundError,
)
from log_config.logger import get_logger

from .camera_device import CameraDevice, CameraStats
from .timeout_utils import RetryPolicy, retry_on_failure, run_with_timeout

logger = get_logger(__name__)


def _directshow_exposure_us(raw_value: float) -> float:
    if raw_value < 0:
        return float((2.0**raw_value) * 1_000_000.0)
    if 0.0 < raw_value < 1.0:
        return float(raw_value * 1_000_000.0)
    return float(raw_value)


def _relative_close(actual: float, expected: float, tolerance: float) -> bool:
    if expected == 0.0:
        return abs(actual) <= 1e-6
    return abs(actual - expected) / max(abs(expected), 1e-9) <= tolerance


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
        self._flip_180 = False
        self._rotation_correction = 0.0  # Degrees to rotate for alignment correction
        self._vertical_offset_px = 0
        self._discovered_devices: Optional[tuple[dict[str, str], ...]] = None

    def set_discovered_devices(self, devices: Sequence[dict[str, str]]) -> None:
        """Reuse one discovery snapshot while opening a stereo pair.

        OpenCV's DirectShow backend opens cameras by numeric index, while setup
        persists stable PnP hardware IDs. The setup worker supplies the exact
        discovery snapshot used to translate both IDs without repeating the
        comparatively slow PowerShell query for each camera.
        """
        self._discovered_devices = tuple(dict(device) for device in devices)

    @retry_on_failure(
        policy=RetryPolicy(
            max_attempts=3,
            base_delay=0.5,
            max_delay=2.0,
            retry_on=(CameraConnectionError,),
        )
    )
    def open(self, serial: str) -> None:
        """Open camera connection.

        Args:
            serial: Camera serial number or device index

        Raises:
            CameraNotFoundError: If camera is not found
            CameraConnectionError: If connection fails
        """
        try:
            # Ensure serial is a string (might be int from some code paths)
            serial_str = str(serial)
            logger.info(f"Opening UVC camera with serial: {serial_str}")
            self._serial = serial_str
            self._friendly_name = None
            target = self._resolve_device(serial_str)
            self._friendly_name = self._friendly_name or target

            def _open_camera():
                """Inner function for timeout wrapper."""
                if target.isdigit():
                    # Validate index before using it
                    index = int(target)
                    if index < 0:
                        raise ValueError(f"Camera index must be non-negative, got: {index}")
                    if index > 15:
                        logger.warning(
                            f"Camera index {index} is unusually high (>15). " "This may indicate an incorrect index."
                        )
                    capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                else:
                    capture = cv2.VideoCapture(f"video={target}", cv2.CAP_DSHOW)

                if capture is None or not capture.isOpened():
                    if capture is not None:
                        capture.release()
                    raise CameraConnectionError(
                        f"Failed to open camera for serial '{serial_str}'. "
                        "Check that the camera is connected and not in use by another application.",
                        camera_id=serial_str,
                    )
                return capture

            # Open camera with timeout
            self._capture = run_with_timeout(
                _open_camera,
                timeout_seconds=5.0,
                error_message=f"UVC camera {serial_str} open timed out",
            )

            logger.info(f"UVC camera {serial_str} opened successfully: {self._friendly_name}")

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

    def set_mode(
        self,
        width: int,
        height: int,
        fps: int,
        pixfmt: str,
        flip_180: bool = False,
        rotation_correction: float = 0.0,
        vertical_offset_px: int = 0,
    ) -> None:
        """Set camera capture mode.

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
            self._flip_180 = flip_180
            self._rotation_correction = rotation_correction
            self._vertical_offset_px = vertical_offset_px

            fourcc_name = {"YUYV": "YUY2", "YUY2": "YUY2", "MJPG": "MJPG"}.get(pixfmt.upper())
            if fourcc_name:
                self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc_name))
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self._capture.set(cv2.CAP_PROP_FPS, fps)

            # Verify settings were applied
            actual_width = self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self._capture.get(cv2.CAP_PROP_FPS)

            if actual_width != width or actual_height != height:
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
            raise CameraConnectionError("Camera not opened.")
        # DirectShow uses backend-specific exposure units, so retain both the
        # requested microseconds and raw readback instead of pretending they
        # are directly comparable.
        self._requested_controls = {
            "exposure_us": exposure_us,
            "gain": gain,
            "wb_mode": wb_mode,
            "wb": wb,
        }
        auto_exposure_set = self._capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        exposure_set = False
        if exposure_us > 0:
            exposure_seconds = float(exposure_us) / 1_000_000.0
            # OpenCV's DirectShow adapter uses log2(seconds) for exposure on
            # common UVC drivers. Preserve raw readback and verify the reverse
            # conversion instead of treating this as a universal camera unit.
            backend_exposure = math.log2(exposure_seconds)
            exposure_set = bool(self._capture.set(cv2.CAP_PROP_EXPOSURE, backend_exposure))
        gain_set = self._capture.set(cv2.CAP_PROP_GAIN, gain)
        color_capture = str(self._pixfmt).upper() != "GRAY8"
        resolved_wb = wb
        wb_source = "configured" if wb is not None else "not_applicable"
        auto_wb_sampled_while_enabled = False
        if color_capture and wb is None:
            auto_wb_raw = float(self._capture.get(cv2.CAP_PROP_AUTO_WB))
            if abs(auto_wb_raw) <= 0.1:
                self._capture.set(cv2.CAP_PROP_AUTO_WB, 1)
                auto_wb_raw = float(self._capture.get(cv2.CAP_PROP_AUTO_WB))
            if abs(auto_wb_raw) > 0.1:
                sampled_wb = float(self._capture.get(cv2.CAP_PROP_WB_TEMPERATURE))
                if math.isfinite(sampled_wb) and sampled_wb > 0:
                    resolved_wb = sampled_wb
                    wb_source = "auto_sampled_then_locked"
                    auto_wb_sampled_while_enabled = True
                else:
                    wb_source = "auto_sample_unavailable"

        wb_set = not color_capture
        auto_wb_set = False
        if wb_mode is None:
            auto_wb_set = bool(self._capture.set(cv2.CAP_PROP_AUTO_WB, 0))
            if resolved_wb is not None:
                wb_set = bool(self._capture.set(cv2.CAP_PROP_WB_TEMPERATURE, resolved_wb))
        autofocus_set = bool(self._capture.set(cv2.CAP_PROP_AUTOFOCUS, 0))

        self._auto_exposure_set = bool(auto_exposure_set)
        self._exposure_set = exposure_set
        self._gain_set = bool(gain_set)
        self._auto_wb_set = auto_wb_set
        self._wb_set = bool(wb_set)
        self._resolved_wb = resolved_wb
        self._wb_source = wb_source
        self._auto_wb_sampled_while_enabled = auto_wb_sampled_while_enabled
        self._autofocus_set = autofocus_set

    def get_mode(self):
        if self._capture is None:
            return None
        raw_fourcc = int(self._capture.get(cv2.CAP_PROP_FOURCC))
        fourcc = "".join(chr((raw_fourcc >> (8 * index)) & 0xFF) for index in range(4)).rstrip("\x00")
        return {
            "width": int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": float(self._capture.get(cv2.CAP_PROP_FPS)),
            "pixfmt": fourcc or self._pixfmt,
        }

    def get_controls(self):
        if self._capture is None:
            return None
        requested = dict(getattr(self, "_requested_controls", {}))
        exposure_raw = float(self._capture.get(cv2.CAP_PROP_EXPOSURE))
        exposure_readback_us = _directshow_exposure_us(exposure_raw)
        gain_readback = float(self._capture.get(cv2.CAP_PROP_GAIN))
        wb_readback = float(self._capture.get(cv2.CAP_PROP_WB_TEMPERATURE))
        auto_exposure_raw = float(self._capture.get(cv2.CAP_PROP_AUTO_EXPOSURE))
        auto_wb_raw = float(self._capture.get(cv2.CAP_PROP_AUTO_WB))
        autofocus_raw = float(self._capture.get(cv2.CAP_PROP_AUTOFOCUS))
        auto_exposure_disabled = bool(getattr(self, "_auto_exposure_set", False)) and (
            abs(auto_exposure_raw - 0.25) <= 0.1 or abs(auto_exposure_raw) <= 0.1
        )
        auto_wb_disabled = abs(auto_wb_raw) <= 0.1
        autofocus_disabled = abs(autofocus_raw) <= 0.1
        exposure_ok = bool(getattr(self, "_exposure_set", False)) and _relative_close(
            exposure_readback_us, float(requested.get("exposure_us") or 0.0), 0.25
        )
        gain_ok = bool(getattr(self, "_gain_set", False)) and _relative_close(
            gain_readback, float(requested.get("gain") or 0.0), 0.15
        )
        requested_wb = getattr(self, "_resolved_wb", requested.get("wb"))
        wb_source = str(getattr(self, "_wb_source", "configured" if requested_wb is not None else "not_applicable"))
        color_capture = str(self._pixfmt).upper() != "GRAY8"
        wb_ok = (requested_wb is None and not color_capture) or (
            requested_wb is not None
            and auto_wb_disabled
            and bool(getattr(self, "_wb_set", False))
            and _relative_close(wb_readback, float(requested_wb), 0.1)
        )
        readback_verified = (
            auto_exposure_disabled
            and auto_wb_disabled
            and autofocus_disabled
            and exposure_ok
            and gain_ok
            and wb_ok
        )
        return {
            **requested,
            "exposure_backend_raw": exposure_raw,
            "exposure_readback_us": exposure_readback_us,
            "actual_exposure_us": exposure_readback_us,
            "gain_readback": gain_readback,
            "actual_gain": gain_readback,
            "wb_readback": wb_readback,
            "actual_wb": wb_readback if requested_wb is not None else None,
            "resolved_wb": requested_wb,
            "wb_source": wb_source,
            "auto_wb_sampled_while_enabled": bool(
                getattr(self, "_auto_wb_sampled_while_enabled", False)
            ),
            "auto_exposure_readback_raw": auto_exposure_raw,
            "auto_white_balance_readback_raw": auto_wb_raw,
            "autofocus_readback_raw": autofocus_raw,
            "auto_exposure_disabled": auto_exposure_disabled,
            "auto_white_balance_disabled": auto_wb_disabled,
            "autofocus_disable_write_succeeded": bool(getattr(self, "_autofocus_set", False)),
            "autofocus_disabled": autofocus_disabled,
            "color_white_balance_verified": wb_ok if color_capture else None,
            "readback_verified": readback_verified,
            "readback_note": (
                "Verified using DirectShow log2(seconds) exposure semantics."
                if readback_verified
                else "Control write/readback mismatch; measurement setup must remain blocked."
            ),
        }

    def get_capability_observation(self):
        """Build typed capability observation from current UVC readback."""
        if self._capture is None:
            return None
        from capture.uvc_capability_observation import build_uvc_observation
        return build_uvc_observation(
            serial=self._serial or "",
            requested_width=self._width, requested_height=self._height,
            requested_fps=self._fps, requested_pixfmt=self._pixfmt,
            mode=self.get_mode() or {}, controls=self.get_controls() or {},
        )

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
        # Stamp capture time immediately after read() returns, BEFORE any image
        # post-processing (color convert, rotation, warp). This is host receive
        # time, NOT hardware acquisition time — DirectShow/MSMF buffering means
        # it can lag actual integration by up to a frame period. Stereo pairing
        # tolerance must account for this (see StereoConfig.pairing_tolerance_ms).
        now_ns = time.monotonic_ns()
        if not ok:
            self._stats.dropped += 1
            logger.warning(f"Failed to read frame from camera {self._serial}")
            raise CameraConnectionError(
                f"Failed to read frame from camera '{self._serial}'. Camera may be disconnected.",
                camera_id=self._serial,
            )
        if self._pixfmt == "GRAY8":
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Apply 180° rotation if camera mounted upside down
        if self._flip_180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)

        # Apply rotation correction for alignment (if configured)
        if abs(self._rotation_correction) > 0.1:  # Only rotate if >0.1 degrees
            h, w = frame.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, self._rotation_correction, 1.0)
            frame = cv2.warpAffine(frame, M, (w, h))

        if self._vertical_offset_px:
            h, w = frame.shape[:2]
            M = np.float32([[1, 0, 0], [0, 1, -self._vertical_offset_px]])
            frame = cv2.warpAffine(frame, M, (w, h))

        if self._stats.last_frame_ns:
            delta_ns = now_ns - self._stats.last_frame_ns
            self._deltas_ns.append(delta_ns)
            delta_s = delta_ns / 1e9
            if delta_s > 0:
                self._stats.fps_instant = 1.0 / delta_s
                self._stats.fps_avg = ((self._stats.fps_avg * self._stats.frames) + self._stats.fps_instant) / (
                    self._stats.frames + 1
                )
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
            intervals = np.asarray(self._deltas_ns, dtype=float) / 1e6
            deviations = np.abs(intervals - np.median(intervals))
            jitter_p95_ms = float(np.percentile(deviations, 95))
        return CameraStats(
            fps_avg=self._stats.fps_avg,
            fps_instant=self._stats.fps_instant,
            jitter_p95_ms=jitter_p95_ms,
            dropped_frames=self._stats.dropped,
            queue_depth=0,
            capture_latency_ms=0.0,
        )

    def close(self) -> None:
        """Close camera connection and release resources.

        Note:
            - Idempotent - safe to call multiple times
            - Uses timeout to prevent hanging on release
            - Adds small delay for DirectShow cleanup
        """
        if self._capture is None:
            logger.debug(f"Camera {self._serial}: Already closed")
            return

        logger.info(f"Closing UVC camera {self._serial}")

        try:

            def _release():
                if self._capture is not None:
                    self._capture.release()

            # Release with timeout to prevent hanging
            run_with_timeout(
                _release,
                timeout_seconds=2.0,
                error_message=f"Camera {self._serial} release timed out",
            )

            # Small delay to ensure DirectShow cleanup completes
            time.sleep(0.1)

            logger.info(f"Camera {self._serial}: Closed successfully")

        except Exception as e:
            logger.error(f"Camera {self._serial}: Error during close: {e}")

        finally:
            # Always clear capture reference
            self._capture = None

    def _resolve_device(self, serial: str) -> str:
        """Resolve camera serial to device name.

        Args:
            serial: Camera serial number

        Returns:
            Numeric DirectShow index corresponding to the stable PnP ID

        Raises:
            CameraNotFoundError: If camera is not found
        """
        try:
            if self._discovered_devices is None:
                from capture.device_discovery import list_uvc_devices

                devices = list_uvc_devices()
            else:
                devices = list(self._discovered_devices)
            matches = [
                (index, dev)
                for index, dev in enumerate(devices)
                if str(dev.get("serial") or "").lower() == serial.lower()
            ]

            if not matches:
                if serial.isdigit():
                    logger.debug(f"Using numeric index for camera: {serial}")
                    return serial

                available_serials = [dev["serial"] for dev in devices]
                logger.error(f"Camera not found: {serial}. Available: {available_serials}")
                raise CameraNotFoundError(
                    f"No camera found with serial '{serial}'. " f"Available serials: {available_serials}",
                    camera_id=serial,
                )

            if len(matches) > 1:
                logger.error(f"Multiple cameras matched serial {serial}: {matches}")
                raise CameraNotFoundError(
                    f"Multiple cameras matched serial '{serial}': {matches}",
                    camera_id=serial,
                )

            directshow_index, device = matches[0]
            friendly_name = str(device.get("friendly_name") or serial)
            self._friendly_name = friendly_name
            logger.debug(
                f"Resolved camera {serial} ({friendly_name}) to DirectShow index {directshow_index}"
            )
            return str(directshow_index)

        except CameraNotFoundError:
            raise
        except Exception as e:
            logger.exception(f"Error resolving camera device {serial}")
            raise CameraNotFoundError(
                f"Error resolving camera device '{serial}': {e}",
                camera_id=serial,
            )


def list_uvc_devices() -> list[dict[str, str]]:
    """Return UVC camera devices with friendly names and serials."""
    from capture.device_discovery import list_uvc_devices as _discover

    return _discover()

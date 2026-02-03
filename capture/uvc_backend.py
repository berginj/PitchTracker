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
from .timeout_utils import RetryPolicy, retry_on_failure, run_with_timeout

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
        self._flip_180 = False
        self._rotation_correction = 0.0  # Degrees to rotate for alignment correction

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

        Note:
            - Uses 5 second timeout to prevent hanging
            - Retries up to 3 times with exponential backoff
            - Logs all attempts for debugging
        """
        try:
            # Ensure serial is a string (might be int from some code paths)
            serial_str = str(serial)
            logger.info(f"Opening UVC camera with serial: {serial_str}")
            self._serial = serial_str
            target = self._resolve_device(serial_str)
            self._friendly_name = target

            def _open_camera():
                """Inner function for timeout wrapper."""
                if target.isdigit() and target == serial_str:
                    capture = cv2.VideoCapture(int(serial_str), cv2.CAP_DSHOW)
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

    def set_mode(self, width: int, height: int, fps: int, pixfmt: str, flip_180: bool = False, rotation_correction: float = 0.0) -> None:
        """Set camera capture mode.

        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            fps: Target frames per second
            pixfmt: Pixel format (GRAY8, RGB24, etc.)
            flip_180: Rotate frame 180° (for upside-down camera mount)
            rotation_correction: Degrees to rotate for alignment correction (e.g., -3.7)

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

        # Apply 180° rotation if camera mounted upside down
        if self._flip_180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)

        # Apply rotation correction for alignment (if configured)
        if abs(self._rotation_correction) > 0.1:  # Only rotate if >0.1 degrees
            h, w = frame.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, self._rotation_correction, 1.0)
            frame = cv2.warpAffine(frame, M, (w, h))

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
    """List camera devices from Windows PnP system.

    Returns:
        List of camera device dictionaries with friendly_name, serial, manufacturer, etc.

    Note:
        - Tries "Camera" class first (fastest, most accurate)
        - Falls back to "Image" class if no cameras found
        - "Image" class includes scanners/printers, so filtering is important
    """
    devices = _query_pnp_devices("Camera")
    if not devices:
        devices = _query_pnp_devices("Image")
    output: list[dict[str, str]] = []
    for device in devices:
        # Note: Present/Status filtering now done in PowerShell query for speed
        # These checks are just safety fallbacks

        friendly = (device.get("FriendlyName") or "").strip()
        instance = (device.get("InstanceId") or "").strip()
        serial = (device.get("Serial") or "").strip()
        manufacturer = (device.get("Manufacturer") or "").strip()
        description = (device.get("Description") or "").strip()
        hwids = device.get("HardwareIds") or ""

        # Skip if no friendly name
        if not friendly:
            continue

        # Convert hardware IDs to string if it's a list
        if isinstance(hwids, list):
            hwids = " ".join(hwids)
        hwids = str(hwids).lower()

        # Filter out printers and scanners by hardware IDs
        # Printers often have USB\Class_07 (printer class) in their hardware IDs
        if "class_07" in hwids or "class_09" in hwids:  # USB printer or hub class
            logger.debug(f"Skipping printer/hub device by HW ID: {friendly}")
            continue

        # Filter by manufacturer (common printer brands)
        mfg_lower = manufacturer.lower()
        printer_mfgs = ["brother", "hp inc", "hewlett-packard", "epson", "canon",
                       "xerox", "konica", "ricoh", "sharp", "kyocera", "lexmark"]
        if any(brand in mfg_lower for brand in printer_mfgs):
            # But only skip if name also suggests printer/scanner
            name_lower = friendly.lower()
            if any(term in name_lower for term in ["printer", "scanner", "scan", "mfp", "multifunction"]):
                logger.info(f"Skipping printer device: {friendly} (Mfg: {manufacturer})")
                continue

        # Fall back to instance ID for serial if not available
        if not serial and instance:
            serial = instance.split("\\")[-1]

        # Build device info with all available data
        device_info = {
            "friendly_name": friendly,
            "instance_id": instance,
            "serial": serial or friendly,
        }

        # Add manufacturer if available
        if manufacturer:
            device_info["manufacturer"] = manufacturer

        # Add description if available and different from friendly name
        if description and description != friendly:
            device_info["description"] = description

        output.append(device_info)

    return output


def _query_pnp_devices(device_class: str) -> list[dict[str, str]]:
    """Query PnP devices via PowerShell.

    Args:
        device_class: Device class to query (Camera, Image, etc.)

    Returns:
        List of device dictionaries

    Note:
        - Uses 10 second timeout to prevent hanging on slower systems
        - Returns empty list on timeout or error
        - Optimized: queries all properties in batch rather than per-device
    """
    # Optimized query: Get all properties in one batch operation per device
    # This is MUCH faster than calling Get-PnpDeviceProperty 4 times per device
    command = (
        "Get-PnpDevice -Class "
        + device_class
        + " | Where-Object { $_.Present -eq $true -and ($_.Status -eq 'OK' -or $_.Status -eq $null) } "
        + "| ForEach-Object { "
        + "$dev = $_; "
        # Get all properties in ONE call by getting the property array
        + "$props = Get-PnpDeviceProperty -InstanceId $dev.InstanceId -ErrorAction SilentlyContinue; "
        # Extract specific properties from the array
        + "$serial = ($props | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_SerialNumber' } | Select-Object -First 1).Data; "
        + "$mfg = ($props | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_Manufacturer' } | Select-Object -First 1).Data; "
        + "$desc = ($props | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_DeviceDesc' } | Select-Object -First 1).Data; "
        + "$hwids = ($props | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_HardwareIds' } | Select-Object -First 1).Data; "
        + "[pscustomobject]@{"
        + "FriendlyName=$dev.FriendlyName;"
        + "InstanceId=$dev.InstanceId;"
        + "Serial=$serial;"
        + "Manufacturer=$mfg;"
        + "Description=$desc;"
        + "HardwareIds=($hwids -join ' ');"  # Convert array to string
        + "Status=$dev.Status;"
        + "Present=$dev.Present"
        + "} "
        + "} | ConvertTo-Json"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=5.0,  # 5 second timeout (reduced from 10s due to query optimization)
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"PowerShell query for {device_class} devices timed out after 5s")
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse PowerShell output for {device_class} devices")
        return []
    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)]


def list_uvc_devices() -> list[dict[str, str]]:
    """Return UVC camera devices with friendly names and serials."""
    return _list_camera_devices()

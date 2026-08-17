"""Device discovery utilities for camera enumeration."""

from __future__ import annotations

import concurrent.futures
import logging
import subprocess
import sys
import threading
import time
from typing import Optional

from PySide6 import QtWidgets

from capture.uvc_backend import list_uvc_devices

logger = logging.getLogger(__name__)

DEFAULT_OPENCV_MAX_INDEX = 16

# Cache for device discovery to avoid repeated probes
_uvc_cache: Optional[list[dict[str, str]]] = None
_opencv_cache: Optional[list[int]] = None
_cache_lock = threading.Lock()


def clear_device_cache() -> None:
    """Clear cached device discovery results.

    Call this when you want to force a fresh device probe,
    such as after a camera disconnect/reconnect event.
    """
    global _uvc_cache, _opencv_cache
    with _cache_lock:
        _uvc_cache = None
        _opencv_cache = None
        logger.debug("Device cache cleared")


def current_serial(combo: QtWidgets.QComboBox) -> str:
    """Get the currently selected serial from a combo box.

    Args:
        combo: QComboBox with device selections

    Returns:
        Serial number or device identifier string
    """
    data = combo.currentData()
    if isinstance(data, str) and data.strip():
        return data.strip()
    return combo.currentText().strip()


def _probe_single_index(index: int, timeout_seconds: float = 3.0) -> Optional[int]:
    """Probe a single camera index with timeout protection.

    Args:
        index: Camera index to probe
        timeout_seconds: Timeout for probe operation (default 3.0s, increased for ArduCam)

    Returns:
        Index if camera available, None otherwise

    Native camera opens run in a child process because a timed-out OpenCV call
    cannot be safely cancelled from a Python thread. Process isolation prevents
    an abandoned DirectShow thread from crashing Qt or the interpreter later.
    """
    script = (
        "import cv2,sys; "
        "cap=cv2.VideoCapture(int(sys.argv[1]), cv2.CAP_DSHOW); "
        "opened=cap.isOpened(); cap.release(); "
        "raise SystemExit(0 if opened else 1)"
    )
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script, str(index)],
            check=False,
            timeout=timeout_seconds,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
    except subprocess.TimeoutExpired:
        logger.debug(f"Camera index {index} probe timed out after {timeout_seconds}s")
        return None
    except OSError as exc:
        logger.debug("Failed to launch camera index %s probe: %s", index, exc)
        return None
    return index if completed.returncode == 0 else None


def is_arducam_device(name: str) -> bool:
    """Check if a device name indicates an ArduCam device.

    Args:
        name: Device friendly name

    Returns:
        True if device is an ArduCam
    """
    if not name:
        return False
    name_lower = name.lower()
    return "arducam" in name_lower or "ardu cam" in name_lower


def sort_cameras_prefer_arducam(devices: list[dict[str, str]]) -> list[dict[str, str]]:
    """Sort camera list to put ArduCam devices first.

    Args:
        devices: List of device info dicts with 'friendly_name' key

    Returns:
        Sorted list with ArduCam devices first, then others
    """
    arducam_devices = []
    other_devices = []

    for device in devices:
        name = device.get("friendly_name", "")
        if is_arducam_device(name):
            arducam_devices.append(device)
        else:
            other_devices.append(device)

    return arducam_devices + other_devices


def probe_opencv_indices(
    max_index: int = DEFAULT_OPENCV_MAX_INDEX,
    parallel: bool = False,
    use_cache: bool = True,
) -> list[int]:
    """Probe for available OpenCV camera indices.

    Args:
        max_index: Maximum index to check (default 16)
        parallel: Use parallel probing for speed (default False for reliability)
        use_cache: Use cached results if available (default True)

    Returns:
        List of available camera indices

    Note:
        - Uses 3 second timeout per camera (increased for ArduCam devices)
        - Sequential mode (default): more reliable, handles USB bandwidth constraints
        - Parallel mode: faster but can cause USB contention and missed devices
        - Default max_index scans 0-15 so four-camera rigs are not hidden
        - This is a fallback - prefer UVC devices in production
        - Results are cached to avoid repeated slow probes
    """
    global _opencv_cache

    # Check cache first
    if use_cache:
        with _cache_lock:
            if _opencv_cache is not None:
                logger.debug(f"Using cached OpenCV indices: {_opencv_cache}")
                return _opencv_cache.copy()

    logger.info(f"Probing OpenCV camera indices 0-{max_index-1} (parallel={parallel})")

    if parallel:
        # Probe all indices in parallel for speed
        indices: list[int] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_index) as executor:
            futures = {executor.submit(_probe_single_index, i, 1.0): i for i in range(max_index)}

            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result(timeout=2.0)  # Extra timeout for safety
                    if result is not None:
                        indices.append(result)
                except Exception as e:
                    logger.debug(f"Camera probe failed: {e}")

        indices.sort()
        logger.info(f"Found {len(indices)} OpenCV cameras: {indices}")

    else:
        # Sequential probing - more reliable but slower
        indices = []
        for i in range(max_index):
            result = _probe_single_index(i, 3.0)
            if result is not None:
                indices.append(result)
                logger.debug(f"Camera {i}: detected")
            else:
                logger.debug(f"Camera {i}: not available")

            # Small delay to avoid USB contention between probes
            if i < max_index - 1:  # Don't delay after last camera
                time.sleep(0.1)

        logger.info(f"Found {len(indices)} OpenCV cameras: {indices}")

    # Cache results
    if use_cache:
        with _cache_lock:
            _opencv_cache = indices.copy()

    return indices


def probe_uvc_devices(use_cache: bool = True) -> list[dict[str, str]]:
    """Probe for available UVC devices.

    Args:
        use_cache: Use cached results if available (default True)

    Returns:
        List of device info dictionaries with serial and friendly_name

    Note:
        - Fast - doesn't open cameras, uses PowerShell enumeration
        - Filters out virtual/software cameras (OBS, Snap Camera, etc.)
        - Results are cached to avoid repeated PowerShell calls
        - This is the preferred method for production use
    """
    global _uvc_cache

    # Check cache first
    if use_cache:
        with _cache_lock:
            if _uvc_cache is not None:
                logger.debug(f"Using cached UVC devices ({len(_uvc_cache)} devices)")
                return _uvc_cache.copy()

    logger.info("Probing UVC devices via PowerShell")
    devices = list_uvc_devices()
    usable: list[dict[str, str]] = []

    for device in devices:
        name = device.get("friendly_name", "")
        if not name:
            logger.debug("Skipping device with no friendly name")
            continue

        # Skip virtual/software cameras and non-camera devices
        name_lower = name.lower()

        # Virtual/software cameras: always filtered, even if named "...Camera"
        virtual_terms = [
            "obs",
            "snap",
            "virtual",
            "screen",
            "desktop",
            "display",
        ]

        # Non-camera function devices (printers, scanners, document cameras, audio)
        noncamera_terms = [
            "printer",
            "scanner",
            "scan",
            "print",
            "mfp",
            "multifunction",
            "document camera",
            "doc camera",
            "document scanner",
            "audio",
            "microphone",
            "mic",
            "speaker",
        ]

        # Printer/scanner brand names: only filtered when the device is not
        # clearly a standalone camera (e.g. "Brother MFP" vs "Brother Camera").
        brand_terms = [
            "brother",
            "hp ",
            "epson",
            "canon printer",
            "xerox",
            "konica",
            "ricoh",
            "sharp mfp",
            "kyocera",
        ]

        if any(term in name_lower for term in virtual_terms):
            should_skip = True
        elif any(term in name_lower for term in noncamera_terms):
            should_skip = True
        elif any(term in name_lower for term in brand_terms) and "camera" not in name_lower:
            should_skip = True
        else:
            should_skip = False

        if should_skip:
            logger.info(f"Filtering out non-camera device: {name}")
            continue

        # Return all physical camera devices - verification happens during actual opening
        logger.debug(f"Accepting camera device: {name}")
        usable.append(device)

    logger.info(f"Found {len(usable)} UVC devices")

    # Sort to prefer ArduCam devices
    usable = sort_cameras_prefer_arducam(usable)
    logger.debug(f"Sorted devices (ArduCam first): {[d.get('friendly_name', '') for d in usable]}")

    # Cache results
    if use_cache:
        with _cache_lock:
            _uvc_cache = usable.copy()

    return usable


def probe_all_devices(use_cache: bool = True) -> tuple[list[dict[str, str]], list[int]]:
    """Probe for all available cameras (UVC + OpenCV fallback).

    Args:
        use_cache: Use cached results if available (default True)

    Returns:
        Tuple of (uvc_devices, opencv_indices)

    Note:
        - Always tries UVC first (fast, serial-based)
        - Only probes OpenCV if UVC finds no devices
        - Use UVC devices in production for reliability
        - OpenCV indices are fallback for development only
    """
    logger.info("Probing all camera devices")

    # Try UVC first (fast, doesn't open cameras)
    uvc_devices = probe_uvc_devices(use_cache=use_cache)

    if uvc_devices:
        logger.info(f"Using UVC devices ({len(uvc_devices)} found)")
        return (uvc_devices, [])

    # Fallback to OpenCV indices (slower, opens cameras)
    logger.warning("No UVC devices found, falling back to OpenCV indices")
    opencv_indices = probe_opencv_indices(use_cache=use_cache)

    return ([], opencv_indices)


__all__ = [
    "current_serial",
    "clear_device_cache",
    "DEFAULT_OPENCV_MAX_INDEX",
    "probe_opencv_indices",
    "probe_uvc_devices",
    "probe_all_devices",
    "is_arducam_device",
    "sort_cameras_prefer_arducam",
]

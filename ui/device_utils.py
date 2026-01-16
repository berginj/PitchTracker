"""Device discovery utilities for camera enumeration."""

from __future__ import annotations

import cv2
from PySide6 import QtWidgets

from capture.uvc_backend import list_uvc_devices


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


def probe_opencv_indices(max_index: int = 8) -> list[int]:
    """Probe for available OpenCV camera indices.

    Args:
        max_index: Maximum index to check

    Returns:
        List of available camera indices
    """
    indices: list[int] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ok = cap.isOpened()
        cap.release()
        if ok:
            indices.append(i)
    return indices


def probe_uvc_devices() -> list[dict[str, str]]:
    """Probe for available UVC devices that can be opened.

    Returns:
        List of device info dictionaries with serial and friendly_name
    """
    devices = list_uvc_devices()
    usable: list[dict[str, str]] = []

    for device in devices:
        name = device.get("friendly_name", "")
        if not name:
            continue

        # Try to open device to verify it's accessible
        cap = cv2.VideoCapture(f"video={name}", cv2.CAP_DSHOW)
        ok = cap.isOpened()
        cap.release()

        if ok:
            usable.append(device)

    return usable


__all__ = [
    "current_serial",
    "probe_opencv_indices",
    "probe_uvc_devices",
]

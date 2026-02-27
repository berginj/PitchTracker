"""Device management controller.

Extracted from MainWindow to reduce god class complexity.
Manages camera device enumeration and selection.
"""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from PySide6 import QtWidgets

from ui.device_utils import (
    current_serial,
    is_arducam_device,
    probe_opencv_indices,
    probe_uvc_devices,
)
from log_config.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class DeviceManager:
    """Manages camera device enumeration and selection.

    Responsibilities:
    - Enumerating available camera devices (UVC and OpenCV)
    - Populating device selection dropdowns
    - Detecting ArduCam devices
    - Auto-selecting default cameras
    """

    def __init__(
        self,
        left_input: QtWidgets.QComboBox,
        right_input: QtWidgets.QComboBox,
        status_label: QtWidgets.QLabel,
        get_backend: Callable[[], str],
    ):
        """Initialize device manager.

        Args:
            left_input: Combobox for left camera selection
            right_input: Combobox for right camera selection
            status_label: Label for status messages
            get_backend: Callback to get current backend ("uvc" or "opencv")
        """
        self._left_input = left_input
        self._right_input = right_input
        self._status_label = status_label
        self._get_backend = get_backend

        logger.debug("DeviceManager initialized")

    def get_left_serial(self) -> Optional[str]:
        """Get currently selected left camera serial."""
        return current_serial(self._left_input)

    def get_right_serial(self) -> Optional[str]:
        """Get currently selected right camera serial."""
        return current_serial(self._right_input)

    def refresh_devices(self) -> int:
        """Refresh device list and populate dropdowns.

        Returns:
            Number of devices found
        """
        self._left_input.clear()
        self._right_input.clear()

        backend = self._get_backend()

        if backend == "uvc":
            return self._refresh_uvc_devices()
        else:
            return self._refresh_opencv_devices()

    def _refresh_uvc_devices(self) -> int:
        """Refresh UVC devices.

        Returns:
            Number of devices found
        """
        devices = probe_uvc_devices()  # Already sorted with ArduCam first
        arducam_count = sum(
            1 for d in devices if is_arducam_device(d.get("friendly_name", ""))
        )

        for device in devices:
            label = f"{device['serial']} - {device['friendly_name']}"
            self._left_input.addItem(label, device["serial"])
            self._right_input.addItem(label, device["serial"])

        if devices:
            status = f"Found {len(devices)} usable device(s)"
            if arducam_count > 0:
                status += f" ({arducam_count} ArduCam)"
            self._status_label.setText(status + ".")

            # Auto-select first two cameras
            if len(devices) >= 2:
                self._left_input.setCurrentIndex(0)
                self._right_input.setCurrentIndex(1)
        else:
            self._status_label.setText("No UVC devices found.")

        logger.info(f"UVC refresh: {len(devices)} devices, {arducam_count} ArduCam")
        return len(devices)

    def _refresh_opencv_devices(self) -> int:
        """Refresh OpenCV devices.

        Returns:
            Number of devices found
        """
        # Get friendly names from UVC to identify ArduCam devices
        uvc_devices = probe_uvc_devices()
        uvc_by_index = {i: dev for i, dev in enumerate(uvc_devices)}
        indices = probe_opencv_indices()
        arducam_count = 0

        for index in indices:
            # Get friendly name if available
            friendly_name = ""
            if index in uvc_by_index:
                friendly_name = uvc_by_index[index].get("friendly_name", "")
                if is_arducam_device(friendly_name):
                    arducam_count += 1

            label = f"{friendly_name}" if friendly_name else f"Index {index}"
            self._left_input.addItem(label, str(index))
            self._right_input.addItem(label, str(index))

        if indices:
            status = f"Found {len(indices)} camera index(es)"
            if arducam_count > 0:
                status += f" ({arducam_count} ArduCam)"
            self._status_label.setText(status + ".")

            # Auto-select first two cameras
            if len(indices) >= 2:
                self._left_input.setCurrentIndex(0)
                self._right_input.setCurrentIndex(1)
        else:
            self._status_label.setText("No OpenCV camera indices available.")

        logger.info(f"OpenCV refresh: {len(indices)} indices, {arducam_count} ArduCam")
        return len(indices)

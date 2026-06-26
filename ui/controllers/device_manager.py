"""Device management controller.

Extracted from MainWindow to reduce god class complexity.
Manages camera device enumeration and selection.
"""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from PySide6 import QtWidgets

from ui.device_utils import (
    DEFAULT_OPENCV_MAX_INDEX,
    current_serial,
    is_arducam_device,
    probe_opencv_indices,
    probe_uvc_devices,
)
from configs.app_state import load_state, save_state
from log_config.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# app_state keys for stable left/right camera assignment by hardware id (serial
# for UVC, index string for OpenCV). Persisting these lets the rig come back up
# with the same physical camera on each side across restarts and re-enumeration.
STATE_KEY_LEFT = "camera_left_id"
STATE_KEY_RIGHT = "camera_right_id"


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
        devices = probe_uvc_devices(use_cache=False)  # Already sorted with ArduCam first
        arducam_count = sum(1 for d in devices if is_arducam_device(d.get("friendly_name", "")))

        for device in devices:
            label = f"{device['serial']} - {device['friendly_name']}"
            self._left_input.addItem(label, device["serial"])
            self._right_input.addItem(label, device["serial"])

        if devices:
            status = f"Found {len(devices)} usable device(s)"
            if arducam_count > 0:
                status += f" ({arducam_count} ArduCam)"
            self._status_label.setText(status + ".")

            # Restore prior left/right assignment by serial; fall back to order.
            self._apply_saved_or_default_selection()
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
        uvc_devices = probe_uvc_devices(use_cache=False)
        uvc_by_index = {i: dev for i, dev in enumerate(uvc_devices)}
        indices = probe_opencv_indices(max_index=DEFAULT_OPENCV_MAX_INDEX, parallel=False, use_cache=False)
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

            # Restore prior left/right assignment by id; fall back to order.
            self._apply_saved_or_default_selection()
        else:
            self._status_label.setText("No OpenCV camera indices available.")

        logger.info(f"OpenCV refresh: {len(indices)} indices, {arducam_count} ArduCam")
        return len(indices)

    def _available_ids(self) -> list[str]:
        """Ordered list of hardware ids currently in the left combobox."""
        return [self._left_input.itemData(i) for i in range(self._left_input.count())]

    def _select_id(self, combo: QtWidgets.QComboBox, device_id: Optional[str]) -> bool:
        """Select ``device_id`` in ``combo`` if present. Returns True on success."""
        if not device_id:
            return False
        index = combo.findData(device_id)
        if index < 0:
            return False
        combo.setCurrentIndex(index)
        return True

    def _apply_saved_or_default_selection(self) -> None:
        """Restore persisted left/right ids, else auto-select first two distinct."""
        ids = self._available_ids()
        if len(ids) < 1:
            return

        state = load_state()
        left_ok = self._select_id(self._left_input, state.get(STATE_KEY_LEFT))
        right_ok = self._select_id(self._right_input, state.get(STATE_KEY_RIGHT))

        if not left_ok:
            self._left_input.setCurrentIndex(0)
        if not right_ok:
            # Prefer a different physical device than the left side.
            left_id = self._left_input.currentData()
            fallback = next((i for i, d in enumerate(ids) if d != left_id), 0)
            self._right_input.setCurrentIndex(fallback)

        if left_ok or right_ok:
            logger.info(
                "Restored camera assignment left=%s right=%s",
                self._left_input.currentData(),
                self._right_input.currentData(),
            )

    def persist_selection(self) -> None:
        """Persist the current left/right assignment by hardware id."""
        state = load_state()
        left_id = self._left_input.currentData()
        right_id = self._right_input.currentData()
        if left_id:
            state[STATE_KEY_LEFT] = str(left_id)
        if right_id:
            state[STATE_KEY_RIGHT] = str(right_id)
        save_state(state)
        logger.info("Persisted camera assignment left=%s right=%s", left_id, right_id)

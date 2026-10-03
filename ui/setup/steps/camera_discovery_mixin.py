"""Discovery ownership and UI completion handling for the legacy camera step."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ui.setup.steps.base_step import BaseStep
from ui.setup.steps.camera_discovery_worker import CameraDiscoveryWorker
from ui.themes import style_status_label


class CameraDiscoveryMixin(BaseStep):
    """Keep cancellable discovery ownership separate from camera preview I/O."""

    _backend: str
    _discovery_worker: CameraDiscoveryWorker | None
    _refresh_after_cancel: bool
    _left_combo: QtWidgets.QComboBox
    _right_combo: QtWidgets.QComboBox
    _refresh_button: QtWidgets.QPushButton
    _status_label: QtWidgets.QLabel

    def _set_status_message(self, message: str, tone: str = "info") -> None:
        """Update the step status label."""
        style_status_label(self._status_label, tone, message)

    def _refresh_devices(self) -> None:
        """Discover available cameras in a background thread."""
        if self._discovery_worker is not None:
            self._refresh_after_cancel = self._discovery_worker.is_cancelled()
            return
        self._set_status_message("Searching for cameras...", "info")
        self._refresh_button.setEnabled(False)
        self._show_loading(True)

        self.set_busy(True)
        self._discovery_worker = CameraDiscoveryWorker(self._backend)
        self._discovery_worker.signals.finished_signal.connect(self._on_discovery_complete)
        self._discovery_worker.signals.error_signal.connect(self._on_discovery_error)
        self._discovery_worker.signals.terminal_signal.connect(self._on_discovery_terminal)
        QtCore.QThreadPool.globalInstance().start(self._discovery_worker)

    def _show_loading(self, visible: bool) -> None:
        """Show or hide the loading indicator."""
        if not hasattr(self, "_loading_frame"):
            from ui.themes.dialog_helpers import build_loading_indicator

            self._loading_frame, _, self._loading_bar = build_loading_indicator(
                "Probing USB devices...", self
            )
            self._loading_bar.setRange(0, 0)
            layout = self.layout()
            if not isinstance(layout, QtWidgets.QBoxLayout):
                raise RuntimeError("Camera step requires a box layout")
            layout.insertWidget(layout.count() - 1, self._loading_frame)
        self._loading_frame.setVisible(visible)

    @QtCore.Slot(list)
    def _on_discovery_complete(self, devices: list[object]) -> None:
        """Handle device discovery results on the main thread."""
        if not self._is_active_discovery():
            return

        self._left_combo.clear()
        self._right_combo.clear()

        if not devices:
            self._set_status_message("No cameras found. Check connections and try again.", "error")
            return

        self._left_combo.addItem("(Select Camera)", None)
        self._right_combo.addItem("(Select Camera)", None)

        if self._backend == "opencv":
            for index in devices:
                if not isinstance(index, int):
                    continue
                label = f"Camera {index}"
                self._left_combo.addItem(label, str(index))
                self._right_combo.addItem(label, str(index))
        else:
            for device in devices:
                if not isinstance(device, dict):
                    continue
                serial = str(device.get("serial", "") or "")
                friendly_name = str(device.get("friendly_name", "") or "")
                label = f"{serial} - {friendly_name}" if serial and friendly_name else (friendly_name or serial)
                self._left_combo.addItem(label, serial)
                self._right_combo.addItem(label, serial)

        self._set_status_message(
            f"Found {len(devices)} camera(s). Select left and right cameras above.",
            "success",
        )

    @QtCore.Slot(str)
    def _on_discovery_error(self, message: str) -> None:
        """Handle device discovery failure on the main thread."""
        if not self._is_active_discovery():
            return
        self._set_status_message(f"Error discovering cameras: {message}", "error")

    def _is_active_discovery(self) -> bool:
        worker = self._discovery_worker
        return (worker is not None and not worker.is_cancelled()
                and self.sender() is worker.signals)

    @QtCore.Slot()
    def _on_discovery_terminal(self) -> None:
        worker = self._discovery_worker
        if worker is None or self.sender() is not worker.signals:
            return
        self._discovery_worker = None
        self._show_loading(False)
        self._refresh_button.setEnabled(True)
        self.set_busy(False)
        if self._refresh_after_cancel:
            self._refresh_after_cancel = False
            self._refresh_devices()

    def cancel_pending(self) -> bool:
        self._refresh_after_cancel = False
        worker = self._discovery_worker
        if worker is None:
            return False
        worker.cancel()
        return True

    def force_cancel_pending(self) -> None:
        self.cancel_pending()

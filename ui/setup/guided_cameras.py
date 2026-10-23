"""Saved rig settings and explicit camera discovery."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from PySide6 import QtWidgets

from app.services.setup_workflow import SetupWorkflowService
from capture.device_discovery import list_uvc_devices
from contracts.setup_capture import SetupCapturePurpose
from ui.setup.focus_assistant import FocusAssistantDialog
from ui.setup.focus_preview_controller import FocusPreviewController
from ui.setup.guided_base import WorkflowStep, display_image
from ui.setup.instrument_widgets import Disclosure, PairedViews, ResponsiveActions, setup_button, stage_heading
from ui.setup.providers.discovery import discover_camera_selection
from ui.themes import get_style_manager


class CamerasStage(WorkflowStep):
    def __init__(self, workflow: SetupWorkflowService, catalog: Any = None):
        super().__init__(workflow, "Cameras")
        self.catalog = catalog
        self.snapshot = None
        self._focus_dialog: FocusAssistantDialog | None = None
        self._focus_preview: FocusPreviewController | None = None
        stage_heading(self, "Pair your cameras", "Assign the physical left and right views, then preview their shared field of view.")
        self.backend_label = QtWidgets.QLabel()
        get_style_manager().style_label(self.backend_label, "muted")
        self.saved_setup = Disclosure("Rig and saved setup")
        self.rig = QtWidgets.QComboBox()
        self.rig.addItem("New rig / unfinished setup", None)
        for path in sorted(workflow.rigs.base_dir.glob("*/rig_profile.json")):
            self.rig.addItem(path.parent.name, path.parent.name)
        self.rig.setCurrentIndex(max(0, self.rig.findData(workflow.state["base_profile_id"])))
        self.saved_setup.form.addRow("Saved rig", self.rig)
        self.saved_setup.form.addRow(self.backend_label)
        self.rig.currentIndexChanged.connect(self.select_rig)
        self.left = QtWidgets.QComboBox()
        self.right = QtWidgets.QComboBox()
        for side, combo in (("Left", self.left), ("Right", self.right)):
            combo.addItem("Choose a device", "")
            combo.setAccessibleName(f"{side} camera identity")
        self.camera_views = PairedViews((self.left, self.right))
        self.previews = self.camera_views.previews
        self.configuration_changed.connect(self.clear_previews)
        self.layout_box.addWidget(self.camera_views)
        self.mode_summary = QtWidgets.QLabel()
        self.mode_summary.setObjectName("SetupModeSummary")
        self.mode_summary.setWordWrap(True)
        self.layout_box.addWidget(self.mode_summary)
        self.camera_controls = Disclosure("Capture mode and camera controls")
        form = self.camera_controls.form
        legacy = setup_button("Import existing local setup", lambda: self.action(self.workflow.import_legacy, edit=True))
        self.saved_setup.form.addRow(legacy)
        self.widgets: dict[str, QtWidgets.QWidget] = {}
        for key, label, minimum, maximum in (
            ("width", "Width (px)", 64, 8192), ("height", "Height (px)", 64, 8192),
            ("fps", "Frame rate", 1, 240), ("exposure_us", "Exposure (µs)", 1, 1000000),
        ):
            widget = QtWidgets.QSpinBox()
            widget.setRange(minimum, maximum)
            widget.setKeyboardTracking(False)
            form.addRow(label, widget)
            self.widgets[key] = widget
            widget.editingFinished.connect(lambda key=key, widget=widget: self.save(key, widget.value()))
        gain = QtWidgets.QDoubleSpinBox()
        gain.setRange(0, 65535)
        gain.setKeyboardTracking(False)
        form.addRow("Gain (device units)", gain)
        self.widgets["gain"] = gain
        gain.editingFinished.connect(lambda: self.save("gain", gain.value()))
        self.color = QtWidgets.QCheckBox("Color capture")
        form.addRow(self.color)
        self.color.toggled.connect(lambda value: self.save("color_mode", value))
        self.wb = QtWidgets.QSpinBox()
        self.wb.setRange(0, 20000)
        self.wb.setSpecialValueText("Sample and lock")
        self.wb.setKeyboardTracking(False)
        form.addRow("White balance (K)", self.wb)
        self.wb.editingFinished.connect(lambda: self.save("wb", self.wb.value() or None))
        pin_wb = setup_button("Lock observed white balance", self.pin_white_balance)
        form.addRow(pin_wb)
        lens = setup_button("I adjusted the lens / focus", lambda: self.action(self.workflow.mark_focus_adjusted, edit=True))
        form.addRow(lens)
        for key, label in (("flip_left", "Flip left 180°"), ("flip_right", "Flip right 180°")):
            checkbox = QtWidgets.QCheckBox(label)
            form.addRow(checkbox)
            self.widgets[key] = checkbox
            checkbox.toggled.connect(lambda value, key=key: self.save(key, value))
        self.left.currentIndexChanged.connect(self.assign)
        self.right.currentIndexChanged.connect(self.assign)
        self.discover_button = setup_button("Discover cameras", self.discover, primary=True)
        self.apply_button = setup_button("Use selected camera pair", self.assign)
        self.apply_button.hide()
        self.preview_button = setup_button(
            "Preview selected cameras", lambda: self.capture(SetupCapturePurpose.PREVIEW, self.preview_ready),
        )
        self.preview_button.setEnabled(False)
        self.cancel_button = setup_button("Cancel", self.cancel_pending)
        self.cancel_button.hide()
        self.focus_button = setup_button("Focus cameras in large view", self.open_focus_assistant)
        self.action_panel = ResponsiveActions((self.discover_button, self.apply_button, self.preview_button,
                                              self.focus_button, self.cancel_button))
        self.layout_box.addWidget(self.action_panel)
        self.layout_box.addWidget(self.camera_controls)
        self.layout_box.addWidget(self.saved_setup)
        self.footer()

    def refresh(self) -> None:
        self.backend_label.setText("Capture backend: " + self.workflow.state["backend"])
        config = self.workflow.config.camera
        for key, widget in self.widgets.items():
            widget.blockSignals(True)
            if isinstance(widget, QtWidgets.QCheckBox):
                widget.setChecked(bool(getattr(config, key)))
            elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                widget.setValue(getattr(config, key))
            widget.blockSignals(False)
        for widget, value in ((self.color, config.color_mode), (self.wb, config.wb or 0)):
            widget.blockSignals(True)
            if isinstance(widget, QtWidgets.QCheckBox):
                widget.setChecked(bool(value))
            else:
                widget.setValue(int(value))
            widget.blockSignals(False)
        ids = self.workflow.state["camera_ids"]
        for side, combo in (("left", self.left), ("right", self.right)):
            combo.blockSignals(True)
            if ids.get(side) and combo.findData(ids[side]) < 0:
                combo.addItem(ids[side], ids[side])
            combo.setCurrentIndex(combo.findData(ids.get(side) or ""))
            combo.blockSignals(False)
        self.show_saved()
        self.refresh_actions()

    def refresh_actions(self) -> None:
        if self.is_busy():
            return
        assigned, _ = self.validate()
        camera = self.workflow.config.camera
        self.mode_summary.setText(f"Requested: {camera.width} × {camera.height} · {camera.fps} fps\nVerify hardware readbacks in Image checks.")
        self.preview_button.setEnabled(assigned)
        self.focus_button.setEnabled(assigned)
        reason = "" if assigned else "Select and apply two distinct cameras first."
        self.preview_button.setToolTip(reason)
        self.focus_button.setToolTip(reason)
        sm = get_style_manager()
        sm.style_button(self.discover_button, "default" if assigned else "primary")
        sm.style_button(self.preview_button, "primary" if assigned else "default")

    def clear_previews(self) -> None:
        for preview in self.previews:
            preview.clear_source()

    def set_busy(self, busy: bool) -> None:
        super().set_busy(busy)
        self.cancel_button.setVisible(busy)
        if not busy:
            self.refresh_actions()

    def discover(self) -> None:
        def load(cancel):
            snapshot = discover_camera_selection(
                catalog=self.catalog, list_devices=(
                    lambda: [{"serial": "sim-left", "friendly_name": "Simulated left"},
                             {"serial": "sim-right", "friendly_name": "Simulated right"}]
                ) if self.workflow.state["backend"] == "sim" else list_uvc_devices,
                requested_mode=(self.workflow.config.camera.width, self.workflow.config.camera.height,
                                self.workflow.config.camera.fps),
                validated_pairs=self.workflow.rigs.previously_validated_camera_pairs(),
            )
            return None if cancel.is_set() else snapshot
        result = self.action(lambda: self.tooling("Discover cameras", load))
        if result is None:
            return
        self.snapshot = result
        ids = self.workflow.state["camera_ids"]
        for side, combo, recommendation in (
            ("left", self.left, result.recommended_left_id), ("right", self.right, result.recommended_right_id),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Select camera", "")
            for camera in result.cameras:
                combo.addItem(f"{camera.friendly_name} — {camera.hardware_id}", camera.hardware_id)
            combo.setCurrentIndex(max(0, combo.findData(ids.get(side) or recommendation)))
            combo.blockSignals(False)
        # Recommendations are visible; applying an assignment is explicit.
        self.set_details(asdict(result))
        self.apply_button.show()
        self.refresh_actions()

    def assign(self, *_args: Any) -> None:
        left, right = str(self.left.currentData() or ""), str(self.right.currentData() or "")
        if not left or not right or left == right:
            return
        self.action(lambda: self.workflow.assign(left, right), edit=True)
        if self.snapshot is not None:
            by_id = {camera.hardware_id: camera for camera in self.snapshot.cameras}
            self.workflow.remember_inventory({
                side: asdict(by_id[identity]) for side, identity in self.workflow.state["camera_ids"].items()
                if identity in by_id
            })
        self.refresh_actions()

    def select_rig(self, *_args: Any) -> None:
        self.action(lambda: self.workflow.select_rig(self.rig.currentData()))
        self.refresh()
        self.configuration_changed.emit()

    def save(self, key: str, value: Any) -> None:
        self.action(lambda: self.workflow.update_settings("camera", {key: value}), edit=True)
        self.refresh_actions()

    def pin_white_balance(self) -> None:
        self.action(self.workflow.use_observed_white_balance, edit=True)
        self.refresh()

    def preview_ready(self, _payload: Any) -> None:
        for side, label in zip(("left", "right"), self.previews):
            display_image(label, self.workflow.images[side], keep_aspect=True)
        self.show_saved()

    def open_focus_assistant(self) -> None:
        """Open a viewer; explicit Start live preview acquires cameras."""
        if self.is_busy():
            return
        if self._focus_dialog is not None:
            self._focus_dialog.raise_()
            self._focus_dialog.activateWindow()
            return
        dialog = FocusAssistantDialog(self.window())
        self._focus_dialog = dialog
        preview = FocusPreviewController(self.workflow, self)
        self._focus_preview = preview
        dialog.capture_requested.connect(preview.start)
        dialog.cancel_requested.connect(preview.stop)
        preview.frame_ready.connect(dialog.accept_frame)
        preview.busy_changed.connect(self.set_busy)
        preview.busy_changed.connect(dialog.set_busy)
        preview.failed.connect(dialog.show_failure)
        if self.workflow.images:
            dialog.set_images(self.workflow.images)
        dialog.finished.connect(self.focus_closed)
        dialog.showMaximized()

    def focus_closed(self) -> None:
        dialog = self._focus_dialog
        if dialog is not None:
            dialog.deleteLater()
            self._focus_dialog = None
        if self._focus_preview is not None:
            self._focus_preview.deleteLater()
            self._focus_preview = None

    def cancel_pending(self) -> bool:
        if self._focus_preview is not None and self._focus_preview.timer.isActive():
            self._focus_preview.stop()
            return True
        return super().cancel_pending()

    def capture_failed(self, terminal) -> None:
        super().capture_failed(terminal)
        if self._focus_dialog is not None and self._focus_dialog.isVisible():
            self._focus_dialog.show_failure(terminal.message)

    def validate(self) -> tuple[bool, str]:
        ids = self.workflow.state["camera_ids"]
        valid = bool(ids.get("left") and ids.get("right") and ids["left"] != ids["right"])
        return valid, "" if valid else "Select two distinct cameras"

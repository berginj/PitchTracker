"""Capture or import full metric stereo calibration inside guided setup."""

from pathlib import Path
from uuid import uuid4

from PySide6 import QtWidgets

from app.services.setup_workflow import SetupWorkflowService
from app.services.tooling import get_tooling_service
from contracts.setup_capture import SetupCapturePurpose
from ui.setup.guided_base import WorkflowStep, display_image
from ui.setup.instrument_widgets import Disclosure, PairedViews, ResponsiveActions, setup_button, stage_heading
from ui.themes import get_style_manager, style_status_label


class CalibrationStage(WorkflowStep):
    def __init__(self, workflow: SetupWorkflowService):
        super().__init__(workflow, "Calibration")
        stage_heading(
            self, "Calibrate the stereo pair",
            "Measure the printed board, then capture varied positions, angles and depths. A full metric fit is required.",
        )
        self.camera_views = PairedViews()
        self.previews = self.camera_views.previews
        for preview in self.previews:
            preview.setText("Capture a board pair to inspect this view")
            preview.setWordWrap(True)
        self.layout_box.addWidget(self.camera_views)
        self.collection = QtWidgets.QFrame()
        self.collection.setObjectName("SetupCollection")
        collection_layout = QtWidgets.QVBoxLayout(self.collection)
        collection_layout.setContentsMargins(16, 14, 16, 14)
        self.count = QtWidgets.QLabel()
        get_style_manager().style_label(self.count, "sectionTitle")
        collection_layout.addWidget(self.count)
        self.pair_progress = QtWidgets.QProgressBar()
        self.pair_progress.setObjectName("SetupPairProgress")
        self.pair_progress.setRange(0, 10)
        self.pair_progress.setTextVisible(False)
        self.pair_progress.setAccessibleName("Saved calibration board pairs; ten pairs minimum")
        collection_layout.addWidget(self.pair_progress)
        self.collection_note = QtWidgets.QLabel("Collection progress is separate from calibration quality. Fit results still need validation.")
        self.collection_note.setWordWrap(True)
        get_style_manager().style_label(self.collection_note, "muted")
        collection_layout.addWidget(self.collection_note)
        self.layout_box.addWidget(self.collection)
        self.board_settings = Disclosure("Measured board dimensions")
        self.board_settings.toggle.setChecked(True)
        form = self.board_settings.form
        self.columns, self.rows = QtWidgets.QSpinBox(), QtWidgets.QSpinBox()
        for widget in (self.columns, self.rows):
            widget.setRange(3, 30)
            widget.setKeyboardTracking(False)
            widget.editingFinished.connect(self.board_changed)
        self.square = QtWidgets.QDoubleSpinBox()
        self.square.setRange(1, 1000)
        self.square.setDecimals(2)
        self.square.setKeyboardTracking(False)
        self.square.editingFinished.connect(self.board_changed)
        form.addRow("ChArUco columns", self.columns)
        form.addRow("ChArUco rows", self.rows)
        form.addRow("Measured square size (mm)", self.square)
        self.capture_button = setup_button("Capture board pair", self.capture_pair, primary=True)
        self.fit_button = setup_button("Run full calibration", self.run_calibration)
        self.cancel_button = setup_button("Cancel", self.cancel_pending)
        self.cancel_button.hide()
        self.action_panel = ResponsiveActions((self.capture_button, self.fit_button, self.cancel_button))
        self.layout_box.addWidget(self.action_panel)
        self.layout_box.addWidget(self.board_settings)
        self.saved_calibration = Disclosure("Use an existing full calibration")
        self.check_button = setup_button("Check saved calibration", self.check)
        self.import_button = setup_button("Import calibration NPZ", self.import_calibration)
        self.saved_calibration.form.addRow(self.check_button)
        self.saved_calibration.form.addRow(self.import_button)
        self.layout_box.addWidget(self.saved_calibration)
        self.footer()

    def refresh(self) -> None:
        board = self.workflow.state["board"]
        cols, rows = (int(value) for value in board.get("pattern", "9x6").split("x"))
        for widget, value in ((self.columns, cols), (self.rows, rows), (self.square, board.get("square_mm", 30))):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        count = len(self.workflow.state["captures"])
        if not count:
            for preview in self.previews:
                preview.clear_source("Capture a board pair to inspect this view")
        self.count.setText(f"{count} saved board pairs · 10 minimum for a full fit")
        self.pair_progress.setValue(min(count, 10))
        self.show_saved()
        self.refresh_actions()

    def refresh_actions(self) -> None:
        if self.is_busy():
            return
        state = self.workflow.state
        enough_pairs = len(state["captures"]) >= 10
        self.fit_button.setEnabled(enough_pairs)
        self.check_button.setEnabled(bool(state["artifacts"].get("calibration")))
        sm = get_style_manager()
        sm.style_button(self.capture_button, "default" if enough_pairs else "primary")
        sm.style_button(self.fit_button, "primary" if enough_pairs else "default")
        if state["artifacts"].get("calibration") and not self.validate()[0]:
            self.saved_calibration.toggle.setChecked(True)

    def show_saved(self) -> None:
        super().show_saved()
        if self.validate()[0]:
            style_status_label(self.status, "success", "Metric calibration matches the saved rig")

    def set_busy(self, busy: bool) -> None:
        super().set_busy(busy)
        self.cancel_button.setVisible(busy)
        if not busy:
            self.refresh_actions()

    def board_changed(self) -> None:
        self.action(lambda: self.workflow.update_board(
            f"{self.columns.value()}x{self.rows.value()}", self.square.value(),
        ), edit=True)
        self.refresh()

    def check(self) -> None:
        self.action(self.workflow.validate_calibration)
        check = self.workflow.state["checks"].get("calibration", {})
        self.set_details(check)
        if check.get("passed"):
            style_status_label(self.status, "success", "Metric calibration matches the saved rig")
        self.refresh_actions()

    def import_calibration(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import full stereo calibration", "", "Calibration (*.npz)")
        if path:
            self.action(lambda: self.workflow.accept_calibration(Path(path)), edit=True)
            self.set_details(self.workflow.state["checks"].get("calibration", {}))
            self.refresh_actions()

    def capture_pair(self) -> None:
        self.capture(SetupCapturePurpose.CALIBRATION_PAIR, self.pair_ready)

    def pair_ready(self, _payload) -> None:
        for side, preview in zip(("left", "right"), self.previews):
            display_image(preview, self.workflow.images[side])
        self.refresh()

    def run_calibration(self) -> None:
        def run():
            generation = self.workflow.generation
            directory = self.workflow.root / ("calibration-job-" + uuid4().hex)
            request = self.workflow.calibration_request(directory)
            result = self.tooling("Full stereo calibration", lambda cancel: (
                get_tooling_service().run_calibration_with_cancellation(request, cancel)
            ))
            if result is None:
                return
            if generation != self.workflow.generation:
                raise ValueError("Calibration belongs to earlier settings; run it again")
            self.workflow.accept_calibration(directory / "stereo_calibration.npz", generated=True)
            self.configuration_changed.emit()
            self.set_details(result.to_payload())
            style_status_label(self.status, "success", "Full metric calibration saved")
        self.action(run)
        self.refresh_actions()

    def validate(self) -> tuple[bool, str]:
        check = self.workflow.state["checks"].get("calibration", {})
        passed = bool(check.get("passed") and "calibration" in self.workflow.visit_checks)
        return passed, "" if passed else "Create or validate a compatible full metric calibration"

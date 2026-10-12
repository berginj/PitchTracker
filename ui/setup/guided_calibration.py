"""Capture or import full metric stereo calibration inside guided setup."""

from pathlib import Path
from uuid import uuid4

from PySide6 import QtWidgets

from app.services.setup_workflow import SetupWorkflowService
from app.services.tooling import get_tooling_service
from contracts.setup_capture import SetupCapturePurpose
from ui.setup.guided_base import WorkflowStep, display_image
from ui.themes import style_status_label


class CalibrationStage(WorkflowStep):
    def __init__(self, workflow: SetupWorkflowService):
        super().__init__(workflow, "Calibration")
        note = QtWidgets.QLabel(
            "Reuse a compatible full calibration or capture at least 10 board poses. "
            "Measure the printed square size; vary position, angle, and depth."
        )
        note.setWordWrap(True)
        self.layout_box.addWidget(note)
        form = QtWidgets.QFormLayout()
        self.layout_box.addLayout(form)
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
        self.count = QtWidgets.QLabel()
        self.layout_box.addWidget(self.count)
        preview_layout = QtWidgets.QHBoxLayout()
        self.previews = [QtWidgets.QLabel(), QtWidgets.QLabel()]
        for preview in self.previews:
            preview.setMinimumSize(180, 120)
            preview_layout.addWidget(preview)
        self.layout_box.addLayout(preview_layout)
        for label, callback in (
            ("Check saved calibration", self.check), ("Import calibration NPZ", self.import_calibration),
            ("Capture board pair", self.capture_pair), ("Run full calibration", self.run_calibration),
            ("Cancel", self.cancel_pending),
        ):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            self.layout_box.addWidget(button)
        self.footer()

    def refresh(self) -> None:
        board = self.workflow.state["board"]
        cols, rows = (int(value) for value in board.get("pattern", "9x6").split("x"))
        for widget, value in ((self.columns, cols), (self.rows, rows), (self.square, board.get("square_mm", 30))):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self.count.setText(f"Saved board pairs: {len(self.workflow.state['captures'])}")
        self.show_saved()

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

    def import_calibration(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import full stereo calibration", "", "Calibration (*.npz)")
        if path:
            self.action(lambda: self.workflow.accept_calibration(Path(path)), edit=True)
            self.set_details(self.workflow.state["checks"].get("calibration", {}))

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

    def validate(self) -> tuple[bool, str]:
        check = self.workflow.state["checks"].get("calibration", {})
        passed = bool(check.get("passed") and "calibration" in self.workflow.visit_checks)
        return passed, "" if passed else "Create or validate a compatible full metric calibration"

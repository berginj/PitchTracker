"""Setup Doctor dialog for fixed-rig production readiness checks."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from app.services.rig_profile import CRITICAL, PASS, WARN, RigProfile, RigProfileService, RigProfileValidation
from app.services.setup_doctor import STAGE_NAMES, SetupDoctorReport, SetupDoctorStageResult, SetupDoctorWorkflow
from configs.settings import AppConfig
from ui.themes import apply_standard_layout, get_style_manager, polish_form_controls


STAGE_GUIDANCE = {
    "Camera identity": "Confirm backend plus left/right camera serials match the active rig profile.",
    "Camera stability": "Use recorded stability metrics from the rig profile; unstable cameras require physical correction.",
    "Orientation and software correction": "Verify recorded flip, rotation, and vertical offset corrections are modest and stable.",
    "Overlap and toe-in": "Review overlap and toe-in metrics; poor overlap or major toe-in requires physical adjustment.",
    "ChArUco metadata": "Confirm board pattern, square size, and marker dictionary are recorded.",
    "Calibration capture quality": "Confirm the calibration set has enough valid stereo poses for production.",
    "Full stereo calibration": "Require full matrix calibration for production readiness; quick calibration remains diagnostic.",
    "ROI setup": "Confirm lane and plate ROIs are saved in the active rig profile.",
    "Runtime dry-run": "Validate that production startup can consume the active profile without critical failures.",
}


class SetupDoctorDialog(QtWidgets.QDialog):
    """Stage-driven Setup Doctor status and validation surface."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        config: Optional[AppConfig] = None,
        config_path: Path = Path("configs/default.yaml"),
        backend: str = "uvc",
        left_serial: Optional[str] = None,
        right_serial: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Setup Doctor")
        self.resize(860, 700)
        self._style_manager = get_style_manager()
        self._config = config
        self._config_path = config_path
        self._backend = backend
        self._left_serial = left_serial
        self._right_serial = right_serial
        self._profile_service = RigProfileService(config_path=config_path)
        self._workflow = SetupDoctorWorkflow(
            self._profile_service,
            config=config,
            backend=backend,
            left_serial=left_serial,
            right_serial=right_serial,
        )
        self._profile: Optional[RigProfile] = None
        self._validation: Optional[RigProfileValidation] = None
        self._report: Optional[SetupDoctorReport] = None
        self._stage_results: dict[str, SetupDoctorStageResult] = {}
        self._current_stage_index = 0

        self._status_label = QtWidgets.QLabel()
        self._status_label.setWordWrap(True)
        self._profile_label = QtWidgets.QLabel()
        self._profile_label.setWordWrap(True)
        self._stage_title = QtWidgets.QLabel()
        self._stage_title.setWordWrap(True)
        self._stage_guidance = QtWidgets.QLabel()
        self._stage_guidance.setWordWrap(True)
        self._stage_result = QtWidgets.QLabel()
        self._stage_result.setWordWrap(True)
        self._details = QtWidgets.QTextEdit()
        self._details.setReadOnly(True)
        self._stage_table = QtWidgets.QTableWidget(0, 3)
        self._stage_table.setHorizontalHeaderLabels(["Stage", "State", "Notes"])
        self._stage_table.horizontalHeader().setStretchLastSection(True)
        self._stage_table.verticalHeader().setVisible(False)
        self._stage_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._stage_table.cellClicked.connect(self._select_stage)

        self._previous_button = QtWidgets.QPushButton("Previous")
        self._run_stage_button = QtWidgets.QPushButton("Run Stage")
        self._next_button = QtWidgets.QPushButton("Next")
        self._run_all_button = QtWidgets.QPushButton("Run All")
        self._save_report_button = QtWidgets.QPushButton("Save Report")
        close_button = QtWidgets.QPushButton("Close")
        self._previous_button.clicked.connect(self._previous_stage)
        self._run_stage_button.clicked.connect(self._run_current_stage)
        self._next_button.clicked.connect(self._next_stage)
        self._run_all_button.clicked.connect(self._run_all_stages)
        self._save_report_button.clicked.connect(self._save_report)
        close_button.clicked.connect(self.accept)
        self._style_manager.style_button(self._run_stage_button, "primary")
        self._style_manager.style_button(self._run_all_button, "primary")
        self._style_manager.style_button(self._save_report_button, "ghost")
        self._style_manager.style_button(close_button, "ghost")

        self._build_layout(close_button)
        polish_form_controls(self)
        self.refresh_status()

    @property
    def validation(self) -> Optional[RigProfileValidation]:
        return self._validation

    def refresh_status(self) -> None:
        self._profile = self._workflow.load_profile()
        self._validation = self._workflow.validate(self._profile)
        self._report = self._workflow.run_all()
        self._stage_results = {result.stage: result for result in self._report.stage_results}
        self._render_header()
        self._populate_stages()
        self._update_current_stage()

    def _build_layout(self, close_button: QtWidgets.QPushButton) -> None:
        header = QtWidgets.QVBoxLayout()
        apply_standard_layout(header, margins=(0, 0, 0, 0), spacing=8)
        title = QtWidgets.QLabel("Setup Doctor")
        self._style_manager.style_label(title, "pageTitle")
        subtitle = QtWidgets.QLabel("Validate the active fixed rig before coaching sessions.")
        subtitle.setWordWrap(True)
        self._style_manager.style_label(subtitle, "muted")
        header.addWidget(title)
        header.addWidget(subtitle)
        header.addWidget(self._status_label)
        header.addWidget(self._profile_label)

        stage_controls = QtWidgets.QHBoxLayout()
        stage_controls.addWidget(self._previous_button)
        stage_controls.addWidget(self._run_stage_button)
        stage_controls.addWidget(self._next_button)
        stage_controls.addStretch(1)
        stage_controls.addWidget(self._run_all_button)
        stage_controls.addWidget(self._save_report_button)
        stage_controls.addWidget(close_button)

        stage_panel = QtWidgets.QVBoxLayout()
        apply_standard_layout(stage_panel, margins=(0, 0, 0, 0), spacing=6)
        self._style_manager.style_label(self._stage_title, "sectionTitle")
        self._style_manager.style_label(self._stage_guidance, "muted")
        stage_panel.addWidget(self._stage_title)
        stage_panel.addWidget(self._stage_guidance)
        stage_panel.addWidget(self._stage_result)

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addLayout(header)
        layout.addWidget(self._stage_table, 2)
        layout.addLayout(stage_panel)
        layout.addWidget(self._details, 1)
        layout.addLayout(stage_controls)
        self.setLayout(layout)

    def _render_header(self) -> None:
        validation = self._validation
        if validation is None:
            return
        state = self._report.overall_state if self._report is not None else validation.state
        tone = "success" if state == PASS else "warning" if state == WARN else "error"
        self._style_manager.style_status_indicator(self._status_label, tone)
        self._status_label.setText(f"Setup Doctor: {state}")

        profile_id = self._profile.profile_id if self._profile is not None else "<none>"
        calib_path = validation.diagnostics.get("calibration_file", "")
        roi_path = validation.diagnostics.get("roi_file", "")
        self._profile_label.setText(f"Profile: {profile_id}\nCalibration: {calib_path}\nROI: {roi_path}")

    def _populate_stages(self) -> None:
        self._stage_table.setRowCount(len(STAGE_NAMES))
        for row, stage in enumerate(STAGE_NAMES):
            result = self._stage_results.get(stage)
            state = result.state if result is not None else "PENDING"
            notes = result.notes if result is not None else ""
            self._stage_table.setItem(row, 0, QtWidgets.QTableWidgetItem(stage))
            self._stage_table.setItem(row, 1, QtWidgets.QTableWidgetItem(state))
            self._stage_table.setItem(row, 2, QtWidgets.QTableWidgetItem(notes))
        self._stage_table.resizeColumnsToContents()
        self._stage_table.selectRow(self._current_stage_index)

    def _update_current_stage(self) -> None:
        stage = STAGE_NAMES[self._current_stage_index]
        self._stage_title.setText(f"{self._current_stage_index + 1}. {stage}")
        self._stage_guidance.setText(STAGE_GUIDANCE.get(stage, ""))
        result = self._stage_results.get(stage)
        if result is None:
            self._stage_result.setText("Stage has not run.")
            self._details.clear()
        else:
            tone = "success" if result.state == PASS else "warning" if result.state == WARN else "error"
            self._style_manager.style_status_indicator(self._stage_result, tone)
            self._stage_result.setText(f"{result.state}: {result.notes}")
            self._details.setPlainText("\n".join(f"- {item}" for item in result.details) or "No additional details.")
        self._previous_button.setEnabled(self._current_stage_index > 0)
        self._next_button.setEnabled(self._current_stage_index < len(STAGE_NAMES) - 1)
        self._stage_table.selectRow(self._current_stage_index)

    def _run_current_stage(self) -> None:
        self._profile = self._workflow.load_profile()
        self._validation = self._workflow.validate(self._profile)
        stage = STAGE_NAMES[self._current_stage_index]
        result = self._workflow.run_stage(stage, self._profile)
        self._stage_results[stage] = result
        self._report = None
        self._render_header()
        self._populate_stages()
        self._update_current_stage()

    def _run_all_stages(self) -> None:
        self._profile = self._workflow.load_profile()
        self._validation = self._workflow.validate(self._profile)
        self._report = self._workflow.run_all()
        self._stage_results = {result.stage: result for result in self._report.stage_results}
        self._render_header()
        self._populate_stages()
        self._update_current_stage()

    def _save_report(self) -> None:
        if self._report is None:
            self._report = self._workflow.run_all()
            self._stage_results = {result.stage: result for result in self._report.stage_results}
        report_path = self._workflow.save_report(self._report, self._profile)
        self._status_label.setText(f"Setup Doctor: {self._report.overall_state} | Report saved: {report_path}")

    def _previous_stage(self) -> None:
        self._current_stage_index = max(0, self._current_stage_index - 1)
        self._update_current_stage()

    def _next_stage(self) -> None:
        self._current_stage_index = min(len(STAGE_NAMES) - 1, self._current_stage_index + 1)
        self._update_current_stage()

    def _select_stage(self, row: int, _column: int) -> None:
        self._current_stage_index = max(0, min(row, len(STAGE_NAMES) - 1))
        self._update_current_stage()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.refresh_status)


__all__ = ["SetupDoctorDialog", "STAGE_NAMES"]

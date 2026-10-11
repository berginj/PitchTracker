"""Desktop workspace for shadow studies and locked physical comparisons."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

from app.services.tooling import get_tooling_service
from app.services.tooling.research import load_object, save_research_document
from contracts.research import MeasurementWorkspaceRequest, SessionInspectionRequest
from ui.tooling_task import run_tooling_task

if TYPE_CHECKING:
    from ui.review.review_window import ReviewWindow

logger = logging.getLogger(__name__)

CASE_COLUMNS = (
    "case_id",
    "stratum",
    "captured_utc",
    "mode",
    "reference_channel_id",
    "reference_status",
    "system_outcome",
    "reference_speed_mph",
    "measured_speed_mph",
    "reference_speed_uncertainty_mph",
    "reference_plate_xy_ft",
    "measured_plate_xy_ft",
    "reference_plate_uncertainty_ft",
    "measured_speed_source",
    "speed_estimator",
    "measured_speed_reference_z_ft",
    "reference_speed_reference_z_ft",
    "reference_record_sha256",
    "evidence_package_sha256",
    "used_for_tuning",
)
TEXT_COLUMNS = frozenset(CASE_COLUMNS[:7] + CASE_COLUMNS[13:15] + CASE_COLUMNS[17:19])


class MeasurementValidationDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, session_dir: Path | None = None):
        super().__init__(parent)
        self.setWindowTitle("Measurement Validation")
        self.resize(1100, 740)
        self.session_dir = session_dir
        self.source_paths: list[Path] = []
        self.workspace: dict[str, Any] | None = None
        self._case_extras: list[dict[str, Any]] = []
        self._loading = False
        self._task_active = False
        self._closing = False
        layout = QtWidgets.QVBoxLayout(self)
        self.session_label = QtWidgets.QLabel(str(session_dir) if session_dir else "Select a recorded session.")
        layout.addWidget(self.session_label)
        layout.addWidget(
            QtWidgets.QLabel(
                "Shadow research retains every attempt. Evaluation does not issue an accuracy approval. "
                "Speed: mph; positions: feet; timestamps: UTC."
            )
        )
        buttons = QtWidgets.QHBoxLayout()
        layout.addLayout(buttons)
        for label, callback in (
            ("Select session", self.select_session),
            ("Inspect evidence", self.inspect),
            ("Batch refits", self.batch_refits),
            ("Apply refit to case", self.apply_refit),
            ("Import protocol", self.import_protocol),
            ("Import dataset", self.import_dataset),
            ("Add shadow case", self.add_case),
            ("Evaluate", self.evaluate),
            ("Save study", self.save_study),
            ("Save report", self.save_report),
        ):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        tabs = QtWidgets.QTabWidget()
        layout.addWidget(tabs)
        self.protocol_editor = QtWidgets.QPlainTextEdit()
        self.metadata_editor = QtWidgets.QPlainTextEdit()
        self.cases = QtWidgets.QTableWidget(0, len(CASE_COLUMNS))
        self.cases.setHorizontalHeaderLabels(CASE_COLUMNS)
        self.cases.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        for label, widget in (
            ("Protocol", self.protocol_editor),
            ("Dataset and references", self.metadata_editor),
            ("Cases", self.cases),
            ("Evidence and results", self.output),
        ):
            tabs.addTab(widget, label)
        # Required values stay blank until supplied by the operator; no hashes,
        # reference uncertainty, tolerances or independent truth are invented.
        self.protocol_editor.setPlainText(
            json.dumps(
                {
                    "schema_version": "physical_validation_protocol.v2",
                    "protocol_id": "",
                    "trajectory_mode": "stereo_3d",
                    "locked_utc": "",
                    "claim_scope": ["speed", "plate_location"],
                    "planned_strata": {},
                    "thresholds": {},
                    "tail_policy": {"percentile": 0.95, "minimum_evaluated_samples": 100},
                    "exclusion_policy": {},
                    "environment_scope": {},
                    "correction_policy_sha256": "",
                },
                indent=2,
            )
        )
        self.metadata_editor.setPlainText(
            json.dumps(
                {
                    "schema_version": "physical_validation_dataset.v2",
                    "dataset_id": "",
                    "phase": "shadow",
                    "protocol_sha256": "",
                    "rig_profile_id": "",
                    "rig_profile_revision": 1,
                    "pipeline_fingerprint": "",
                    "hardware_fingerprint_sha256": "",
                    "config_sha256": "",
                    "calibration_sha256": "",
                    "field_transform_sha256": "",
                    "environment": {},
                    "reference_channels": [],
                },
                indent=2,
            )
        )
        self.protocol_editor.textChanged.connect(self._invalidate)
        self.metadata_editor.textChanged.connect(self._invalidate)
        self.cases.itemChanged.connect(self._invalidate)

    def _invalidate(self, *_args: Any) -> None:
        if not self._loading:
            self.workspace = None

    def batch_refits(self):
        from ui.review.fit_batch_dialog import FitBatchDialog

        FitBatchDialog(self, self.session_dir).exec()

    def apply_refit(self):
        from app.services.analysis.derived_measurements import shadow_measurements

        try:
            row = self.cases.currentRow()
            if row < 0:
                raise ValueError("Select the shadow case to update")
            phase = json.loads(self.metadata_editor.toPlainText()).get("phase")
            if phase != "shadow":
                raise ValueError("Confirmation datasets are read-only")
            filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select one derived fit", "", "JSON (*.json)")
            if filename:
                for key, value in shadow_measurements(Path(filename), phase).items():
                    column = CASE_COLUMNS.index(key)
                    text = str(value) if key in TEXT_COLUMNS and value is not None else json.dumps(value)
                    self.cases.setItem(row, column, QtWidgets.QTableWidgetItem(text))
                self.source_paths.append(Path(filename))
        except Exception as exc:
            self._error(exc)

    def _run(self, title, operation):
        self._task_active = True
        try:
            return run_tooling_task(self, title, operation)
        finally:
            self._task_active = False
            if self._closing:
                QtCore.QTimer.singleShot(0, self.reject)

    def reject(self) -> None:
        if self._task_active:
            self._closing = True
            for child in self.findChildren(QtWidgets.QDialog):
                child.reject()
            return
        super().reject()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._task_active:
            self.reject()
            event.ignore()
        else:
            event.accept()

    def _error(self, exc: Exception) -> None:
        logger.exception("Measurement workspace operation failed")
        self.output.setPlainText(f"Unable to complete operation: {exc}")

    def select_session(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select recorded session")
        if path:
            self.session_dir = Path(path)
            self.session_label.setText(path)
            self.workspace = None

    def inspect(self) -> None:
        try:
            if self.session_dir is None:
                raise ValueError("Select a recorded session first")
            request = SessionInspectionRequest(self.session_dir)
            result = self._run(
                "Inspect measurement evidence",
                lambda cancel: get_tooling_service().inspect_measurement_session(
                    request,
                    cancel,
                ),
            )
            if result is not None:
                self.output.setPlainText(json.dumps(result.report, indent=2))
        except Exception as exc:  # noqa: BLE001 - actionable UI failure
            self._error(exc)

    def _import(self, title: str) -> dict[str, Any] | None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, title, "", "JSON files (*.json)")
        if not path:
            return None
        payload = load_object(Path(path))
        self.source_paths.append(Path(path))
        return payload

    def import_protocol(self) -> None:
        try:
            payload = self._import("Import locked protocol")
            if payload is not None:
                self.protocol_editor.setPlainText(json.dumps(payload, indent=2))
        except Exception as exc:  # noqa: BLE001 - actionable UI failure
            self._error(exc)

    def import_dataset(self) -> None:
        try:
            payload = self._import("Import measurement dataset")
            if payload is None:
                return
            self._loading = True
            cases = payload.pop("cases", [])
            self._case_extras = [dict(case) for case in cases]
            self.metadata_editor.setPlainText(json.dumps(payload, indent=2))
            self.cases.setRowCount(len(cases))
            for row, case in enumerate(cases):
                self._set_case(row, case)
            confirmation = payload.get("phase") != "shadow"
            self.metadata_editor.setReadOnly(confirmation)
            self.cases.setEditTriggers(
                QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
                if confirmation
                else QtWidgets.QAbstractItemView.EditTrigger.AllEditTriggers
            )
            self.workspace = None
        except Exception as exc:  # noqa: BLE001 - actionable UI failure
            self._error(exc)
        finally:
            self._loading = False

    def _set_case(self, row: int, case: dict[str, Any]) -> None:
        for column, key in enumerate(CASE_COLUMNS):
            value = case.get(key)
            text = "" if value is None else (str(value) if key in TEXT_COLUMNS else json.dumps(value))
            self.cases.setItem(row, column, QtWidgets.QTableWidgetItem(text))

    def add_case(self) -> None:
        try:
            if json.loads(self.metadata_editor.toPlainText()).get("phase") != "shadow":
                raise ValueError("Confirmation cases are read-only; create a separate shadow dataset for tuning")
            row = self.cases.rowCount()
            self.cases.insertRow(row)
            self._case_extras.append({})
            self._set_case(
                row,
                {
                    "mode": "stereo_3d",
                    "reference_status": "INVALID",
                    "system_outcome": "UNAVAILABLE",
                    "used_for_tuning": True,
                },
            )
            self.workspace = None
        except Exception as exc:  # noqa: BLE001 - actionable UI failure
            self._error(exc)

    def request(self) -> MeasurementWorkspaceRequest:
        if self.session_dir is None:
            raise ValueError("Select a recorded session first")
        protocol = json.loads(self.protocol_editor.toPlainText())
        dataset = json.loads(self.metadata_editor.toPlainText())
        cases = []
        for row in range(self.cases.rowCount()):
            case = dict(self._case_extras[row])
            for column, key in enumerate(CASE_COLUMNS):
                item = self.cases.item(row, column)
                text = item.text().strip() if item else ""
                case[key] = text if key in TEXT_COLUMNS else (json.loads(text) if text else None)
            cases.append(case)
        dataset["cases"] = cases
        return MeasurementWorkspaceRequest(protocol, dataset, self.session_dir)

    def evaluate(self) -> None:
        self.workspace = None
        try:
            request = self.request()
            result = self._run(
                "Evaluate measurements",
                lambda cancel: get_tooling_service().evaluate_measurement_workspace(
                    request,
                    cancel,
                ),
            )
            if result is not None:
                self.workspace = result.report
                self.output.setPlainText(json.dumps(result.report, indent=2))
        except Exception as exc:  # noqa: BLE001 - actionable UI failure
            self._error(exc)

    def _save(self, payload: dict[str, Any], title: str) -> None:
        if self.session_dir is None:
            raise ValueError("Select a recorded session first")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, title, "", "JSON files (*.json)")
        if path:
            save_research_document(Path(path), payload, self.session_dir, source_paths=tuple(self.source_paths))

    def save_study(self) -> None:
        try:
            if self.workspace is None:
                raise ValueError("Evaluate the current study before saving")
            self._save(self.workspace["protocol"], "Save protocol to a new file")
            self._save(self.workspace["dataset"], "Save dataset to a new file")
        except Exception as exc:  # noqa: BLE001 - actionable UI failure
            self._error(exc)

    def save_report(self) -> None:
        try:
            if self.workspace is None:
                raise ValueError("Evaluate the current study before saving")
            self._save(self.workspace, "Save measurement workspace report")
        except Exception as exc:  # noqa: BLE001 - actionable UI failure
            self._error(exc)


def open_measurement_validation(window: ReviewWindow, session_dir: Path | None) -> None:
    """Keep the research dialog owned through work and deferred parent closure."""
    dialog = MeasurementValidationDialog(window, session_dir)
    window._measurement_dialog = dialog
    try:
        dialog.exec()
    finally:
        window._measurement_dialog = None
        dialog.deleteLater()
        if window._close_after_measurement:
            QtCore.QTimer.singleShot(0, window.close)

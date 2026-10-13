"""Thin research controls; all comparison, annotation and selection logic is serviced."""

import json
from pathlib import Path
from PySide6 import QtCore, QtWidgets

from app.services.analysis.pipeline_comparison import run_pipeline_comparison
from app.services.analysis.comparison_annotations import save_annotation_revision, bind_annotation_revision
from app.services.analysis.comparison_selection import select_qualified_profile, select_classical_profile
from app.services.setup_workflow import SetupWorkflowService
from contracts.pipeline_comparison import PipelineComparisonRequest
from ui.tooling_task import ToolingTaskDialog


class PipelineComparisonDialog(QtWidgets.QDialog):
    progress_received = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compare approaches")
        self.resize(980, 680)
        self.task = None
        self.close_pending = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel(
                "Compare optional detectors on recorded inputs. Physical accuracy requires independent confirmation."
            )
        )
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.fields = {}
        for key, label, folder in (
            ("dataset", "Study manifest", False),
            ("output", "Research output", True),
            ("bundle", "Optional ONNX bundle", False),
            ("assets", "Optional 2D research assets", False),
            ("python", "Isolated research Python", False),
            ("repository", "Pinned BaseballCV checkout", True),
        ):
            field = QtWidgets.QLineEdit()
            button = QtWidgets.QPushButton("Choose…")
            button.clicked.connect(lambda checked=False, f=field, d=folder: self._browse(f, d))
            row = QtWidgets.QHBoxLayout()
            row.addWidget(field)
            row.addWidget(button)
            form.addRow(label, row)
            self.fields[key] = field
        actions = QtWidgets.QHBoxLayout()
        layout.addLayout(actions)
        for label, callback in (
            ("Run comparison", self._run),
            ("Open report", self._open),
            ("Review labels", self._labels),
            ("Select qualified profile", self._select),
            ("Restore classical profile", self._classical),
        ):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Session",
                "Variant",
                "Status",
                "Recall",
                "Center p95 px",
                "Target p95 ft",
                "Pitch outcomes",
                "Detector p95 ms",
            ]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details)
        self.progress_received.connect(self._progress)

    def _browse(self, field, directory=False):
        path = (
            QtWidgets.QFileDialog.getExistingDirectory(self, "Choose directory")
            if directory
            else QtWidgets.QFileDialog.getOpenFileName(self, "Choose local input")[0]
        )
        if path:
            field.setText(path)

    def _progress(self, value):
        if self.task:
            self.task.label.setText(f"{value.status}: {value.completed}/{value.total}")

    def _run(self):
        try:

            def optional(key):
                text = self.fields[key].text().strip()
                return Path(text) if text else None

            if not optional("dataset") or not optional("output"):
                raise ValueError("Select a study manifest and separate output directory")
            request = PipelineComparisonRequest(
                Path(self.fields["dataset"].text()),
                Path(self.fields["output"].text()),
                optional("bundle"),
                monocular_assets=optional("assets"),
                external_python=optional("python"),
                external_repository=optional("repository"),
            )
            self.task = ToolingTaskDialog(
                self,
                "Pipeline comparison",
                lambda cancel: run_pipeline_comparison(request, cancel, self.progress_received.emit),
            )
            self.task.worker.start()
            self.task.exec()
            if self.task.worker.error:
                raise self.task.worker.error
            result = self.task.worker.result
            if result is not None:
                self._show(result.report)
                self.details.appendPlainText(f"Report: {result.report_path}")
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Comparison unavailable", str(exc))
        finally:
            self.task = None
            if self.close_pending:
                super().reject()

    def _show(self, report):
        rows = report.get("results", [])
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            metric = row["metrics"]
            values = [
                row["session_id"],
                row["variant"],
                row["status"],
                metric["recall"],
                metric["center_error_px"]["p95"],
                metric["target_error_ft"]["p95"],
                f"{metric['completed_opportunities']}/{metric['opportunities']}",
                row["detector_roundtrip_ms"]["p95"],
            ]
            for column, value in enumerate(values):
                self.table.setItem(
                    row_index, column, QtWidgets.QTableWidgetItem("Unavailable" if value is None else str(value))
                )
        self.table.resizeColumnsToContents()
        self.details.setPlainText(
            json.dumps(
                {
                    "status": report["status"],
                    "model": report.get("model"),
                    "quality_assessments": report.get("quality_assessments", []),
                    "monocular_results": report.get("monocular_results", []),
                    "failures": [{"variant": r["variant"], "reason": r.get("reason")} for r in rows if r.get("reason")],
                },
                indent=2,
            )
        )

    def _open(self):
        path = QtWidgets.QFileDialog.getOpenFileName(self, "Open comparison report", filter="JSON (*.json)")[0]
        if path:
            try:
                self._show(json.loads(Path(path).read_text(encoding="utf-8")))
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Invalid report", str(exc))

    def _labels(self):
        path = QtWidgets.QFileDialog.getOpenFileName(self, "Human annotation file", filter="JSON (*.json)")[0]
        if not path:
            return
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Review raw-pixel labels and opportunity windows")
        dialog.resize(820, 640)
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(
            QtWidgets.QLabel(
                "Review centers, visibility, timestamps and independent opportunity windows. Save a new revision."
            )
        )
        text = QtWidgets.QPlainTextEdit(Path(path).read_text(encoding="utf-8"))
        layout.addWidget(text)
        reviewed = QtWidgets.QCheckBox("I have reviewed these labels")
        layout.addWidget(reviewed)
        save = QtWidgets.QPushButton("Save reviewed revision…")
        layout.addWidget(save)

        def save_labels():
            try:
                target = QtWidgets.QFileDialog.getSaveFileName(
                    dialog, "New annotation revision", filter="JSON (*.json)"
                )[0]
                if not target:
                    return
                payload = json.loads(text.toPlainText())
                payload["human_reviewed"] = reviewed.isChecked()
                save_annotation_revision(path, target, payload)
                session, accepted = QtWidgets.QInputDialog.getText(
                    dialog, "Bind to study", "Session identifier (leave blank to save labels only)"
                )
                if accepted and session.strip() and self.fields["dataset"].text():
                    output = QtWidgets.QFileDialog.getSaveFileName(
                        dialog, "New study revision", filter="JSON (*.json)"
                    )[0]
                    if output:
                        bind_annotation_revision(self.fields["dataset"].text(), session.strip(), target, output)
                        self.fields["dataset"].setText(output)
                dialog.accept()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(dialog, "Labels not saved", str(exc))

        save.clicked.connect(save_labels)
        dialog.exec()

    def _select(self):
        receipt = QtWidgets.QFileDialog.getOpenFileName(self, "Live qualification receipt", filter="JSON (*.json)")[0]
        if receipt and self.fields["bundle"].text():
            try:
                workflow = SetupWorkflowService()
                select_qualified_profile(workflow, self.fields["bundle"].text(), receipt)
                self.details.appendPlainText(
                    "Profile saved as pending setup edits. Finish and publish the rig revision in Setup before recording."
                )
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Profile unavailable", str(exc))

    def _classical(self):
        try:
            select_classical_profile(SetupWorkflowService())
            self.details.appendPlainText(
                "Classical profile saved as pending setup edits. Publish the rig revision in Setup."
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Profile not saved", str(exc))

    def reject(self):
        if self.task is not None and self.task.busy:
            self.close_pending = True
            self.task.reject()
            return
        super().reject()

    def closeEvent(self, event):
        if self.task is not None and self.task.busy:
            self.reject()
            event.ignore()
        else:
            event.accept()


def open_pipeline_comparison(host):
    if host._measurement_dialog is not None:
        host._measurement_dialog.raise_()
        return
    dialog = PipelineComparisonDialog(host)
    host._measurement_dialog = dialog
    try:
        dialog.exec()
    finally:
        host._measurement_dialog = None
        if host._close_after_measurement:
            host._close_after_measurement = False
            QtCore.QTimer.singleShot(0, host.close)

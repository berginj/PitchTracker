"""Desktop controls for local trajectory research jobs."""

import json
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from app.services.analysis.fit_batch import run_fit_batch
from contracts.fit_jobs import FitBatchRequest
from ui.tooling_task import ToolingTaskDialog


class FitBatchDialog(QtWidgets.QDialog):
    progress_received = QtCore.Signal(object)

    def __init__(self, parent, session_dir=None):
        super().__init__(parent)
        self.setWindowTitle("Batch trajectory refits")
        self.resize(780, 580)
        layout = QtWidgets.QVBoxLayout(self)
        self.sessions = QtWidgets.QListWidget()
        if session_dir:
            self.sessions.addItem(str(session_dir))
        layout.addWidget(self.sessions)
        buttons = QtWidgets.QHBoxLayout()
        layout.addLayout(buttons)
        for text, callback in (("Add session", self._add_session), ("Remove session", self._remove_session)):
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.output = QtWidgets.QLineEdit()
        output_button = QtWidgets.QPushButton("Choose output folder")
        output_button.clicked.connect(self._choose_output)
        form.addRow(output_button, self.output)
        self.backend = QtWidgets.QComboBox()
        for label, value in (
            ("CPU", "cpu"),
            ("Auto", "auto"),
            ("NVIDIA GPU (qualified builds)", "cuda"),
            ("Reference Python", "reference"),
        ):
            self.backend.addItem(label, value)
        form.addRow("Compute", self.backend)
        self.workers = QtWidgets.QSpinBox()
        self.workers.setRange(0, 16)
        self.workers.setSpecialValueText("Auto")
        form.addRow("Workers", self.workers)
        self.workflow = QtWidgets.QComboBox()
        self.workflow.addItem("Recorded observations", "observations")
        self.workflow.addItem("Timestamped stereo video", "videos")
        form.addRow("Inputs", self.workflow)
        self.config = QtWidgets.QLineEdit()
        form.addRow("Video replay config path", self.config)
        self.calibration = QtWidgets.QLineEdit()
        self.rois = QtWidgets.QLineEdit()
        self.transform = QtWidgets.QLineEdit()
        form.addRow("Stereo calibration NPZ", self.calibration)
        form.addRow("ROI JSON", self.rois)
        form.addRow("Field transform JSON", self.transform)
        self.overrides = QtWidgets.QPlainTextEdit("{}")
        self.overrides.setMaximumHeight(90)
        form.addRow("Fit overrides (JSON)", self.overrides)
        self.start_button = QtWidgets.QPushButton("Run / resume refits")
        self.start_button.clicked.connect(self._start)
        layout.addWidget(self.start_button)
        self.results = QtWidgets.QPlainTextEdit()
        self.results.setReadOnly(True)
        layout.addWidget(self.results)
        self.progress_received.connect(self._progress)
        self.task = None

    def _add_session(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Recorded session")
        if folder:
            self.sessions.addItem(folder)

    def _remove_session(self):
        self.sessions.takeItem(self.sessions.currentRow())

    def _choose_output(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Derived research output")
        if folder:
            self.output.setText(folder)

    def _progress(self, progress):
        if self.task is not None:
            self.task.label.setText(f"{progress.status}: {progress.completed}/{progress.total}")

    def _start(self):
        try:
            if not self.output.text().strip():
                raise ValueError("Choose a derived output folder")
            request = FitBatchRequest(
                tuple(Path(self.sessions.item(index).text()) for index in range(self.sessions.count())),
                Path(self.output.text()),
                workflow=self.workflow.currentData(),
                backend=self.backend.currentData(),
                workers=self.workers.value(),
                overrides=json.loads(self.overrides.toPlainText()),
                config_path=Path(self.config.text()) if self.config.text().strip() else None,
                calibration_path=Path(self.calibration.text()) if self.calibration.text().strip() else None,
                roi_path=Path(self.rois.text()) if self.rois.text().strip() else None,
                field_transform_path=Path(self.transform.text()) if self.transform.text().strip() else None,
            )
            self.task = ToolingTaskDialog(
                self,
                "Trajectory refits",
                lambda cancel: run_fit_batch(
                    request,
                    cancel,
                    self.progress_received.emit,
                ),
            )
            self.task.worker.start()
            self.task.exec()
            if self.task.worker.error is not None:
                raise self.task.worker.error
            result = self.task.worker.result
            if result is not None:
                self.results.setPlainText(json.dumps(result.report, indent=2))
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Trajectory refits", str(exc))
        finally:
            self.task = None

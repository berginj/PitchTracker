"""Explicit timing trial controls; the primary recording remains service-owned."""

from pathlib import Path
from PySide6 import QtWidgets
from contracts.model_bundle import ModelBundle
from ui.tooling_task import ToolingTaskDialog


def open_detector_trial(host):
    dialog = QtWidgets.QDialog(host)
    dialog.setWindowTitle("Optional detector timing trial")
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(
        QtWidgets.QLabel(
            "During an active recording, collect fifteen minutes of shadow detector timings.\n"
            "The trial does not change the primary pitch results."
        )
    )
    status = QtWidgets.QLabel("Choose a supplied local model bundle to start.")
    layout.addWidget(status)
    stereo = QtWidgets.QComboBox()
    for item in ("greedy_v1", "global_v2", "global_v3"):
        stereo.addItem(item)
    layout.addWidget(stereo)
    start, stop = QtWidgets.QPushButton("Start timing trial…"), QtWidgets.QPushButton("Stop and save timings")
    layout.addWidget(start)
    layout.addWidget(stop)

    def begin():
        try:
            path = QtWidgets.QFileDialog.getOpenFileName(dialog, "Choose model bundle", filter="JSON (*.json)")[0]
            if not path:
                return
            bundle = ModelBundle.load(Path(path))
            output = QtWidgets.QFileDialog.getSaveFileName(dialog, "New timing report", filter="JSON (*.json)")[0]
            if not output:
                return
            variant = f"baseballcv_{bundle.localization}:{stereo.currentText()}"
            task = ToolingTaskDialog(
                dialog,
                "Warm shadow detector",
                lambda cancel: host._service.start_detector_trial(path, variant, output, cancel),
            )
            task.worker.start()
            task.exec()
            if task.worker.error:
                raise task.worker.error
            status.setText("Trial running. Continue recording for at least fifteen minutes, then stop and save.")
            start.setEnabled(False)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(dialog, "Trial unavailable", str(exc))

    def finish():
        task = ToolingTaskDialog(dialog, "Stop shadow detector", lambda cancel: host._service.stop_detector_trial())
        task.worker.start()
        task.exec()
        if task.worker.error:
            QtWidgets.QMessageBox.warning(dialog, "Trial stop failed", str(task.worker.error))
        else:
            status.setText(f"Timing report: {task.worker.result}" if task.worker.result else "No trial is running.")
            start.setEnabled(True)

    start.clicked.connect(begin)
    stop.clicked.connect(finish)
    dialog.exec()

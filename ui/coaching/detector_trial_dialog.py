"""Explicit timing trial controls; the primary recording remains service-owned."""

from pathlib import Path
from PySide6 import QtWidgets
from contracts.model_bundle import ModelBundle
from ui.tooling_task import ToolingTaskDialog
from ui.themes import apply_standard_layout, build_dialog_header, polish_form_controls, show_message_dialog


def open_detector_trial(host):
    dialog = QtWidgets.QDialog(host)
    dialog.setWindowTitle("Optional detector timing trial")
    layout = QtWidgets.QVBoxLayout(dialog)
    apply_standard_layout(layout)
    layout.addWidget(build_dialog_header(
        "Detector timing trial", "During an active recording, collect fifteen minutes of shadow timings. "
        "The trial does not change primary pitch results."))
    status = QtWidgets.QLabel("Choose a supplied local model bundle to start.")
    status.setWordWrap(True)
    layout.addWidget(status)
    stereo = QtWidgets.QComboBox()
    stereo.setAccessibleName("Shadow trial stereo algorithm")
    for item in ("greedy_v1", "global_v2", "global_v3"):
        stereo.addItem(item)
    layout.addWidget(stereo)
    start, stop = QtWidgets.QPushButton("Start timing trial…"), QtWidgets.QPushButton("Stop and save timings")
    layout.addWidget(start)
    layout.addWidget(stop)
    close = QtWidgets.QPushButton("Close")
    close.clicked.connect(dialog.reject)
    layout.addWidget(close)

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
            status.setText(f"Trial unavailable: {exc}")
            show_message_dialog(dialog, "Trial unavailable", str(exc), tone="warning")

    def finish():
        task = ToolingTaskDialog(dialog, "Stop shadow detector", lambda cancel: host._service.stop_detector_trial())
        task.worker.start()
        task.exec()
        if task.worker.error:
            status.setText(f"Trial stop failed: {task.worker.error}")
            show_message_dialog(dialog, "Trial stop failed", str(task.worker.error), tone="warning")
        else:
            status.setText(f"Timing report: {task.worker.result}" if task.worker.result else "No trial is running.")
            start.setEnabled(True)

    start.clicked.connect(begin)
    stop.clicked.connect(finish)
    polish_form_controls(dialog)
    dialog.exec()

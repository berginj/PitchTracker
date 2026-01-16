"""Detector settings dialog for tuning detection parameters."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from detect.config import Mode


class DetectorSettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring classical and ML detector parameters."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        mode: str,
        frame_diff: float,
        bg_diff: float,
        bg_alpha: float,
        edge_thresh: float,
        blob_thresh: float,
        min_area: int,
        min_circ: float,
        threading_mode: str,
        worker_count: int,
        detector_type: str,
        model_path: str,
        model_input_size: tuple[int, int],
        model_conf_threshold: float,
        model_class_id: int,
        model_format: str,
    ) -> None:
        """Initialize detector settings dialog.

        Args:
            parent: Parent widget
            mode: Detection mode (MODE_A or MODE_B)
            frame_diff: Frame difference threshold
            bg_diff: Background difference threshold
            bg_alpha: Background update alpha
            edge_thresh: Edge detection threshold
            blob_thresh: Blob threshold
            min_area: Minimum blob area filter
            min_circ: Minimum circularity filter
            threading_mode: Threading mode (per_camera or worker_pool)
            worker_count: Number of worker threads
            detector_type: Detector type (classical or ml)
            model_path: Path to ONNX model file
            model_input_size: Model input dimensions (width, height)
            model_conf_threshold: Model confidence threshold
            model_class_id: Model class ID to detect
            model_format: Model format (yolo_v5, etc.)
        """
        super().__init__(parent)
        self.setWindowTitle("Detector Settings")
        self.resize(700, 560)

        # Help text
        help_text = QtWidgets.QTextEdit()
        help_text.setReadOnly(True)
        help_text.setText(
            "\n".join(
                [
                    "Detector Tuning Guide:",
                    "",
                    "- Mode: MODE_A uses frame differencing; MODE_B is more robust on busy backgrounds.",
                    "- Frame diff / BG diff: Sensitivity thresholds; lower = more detections, more noise.",
                    "- BG alpha: Background update rate; lower keeps older background longer.",
                    "- Edge thresh: Canny edge strength for MODE_B.",
                    "- Blob thresh: Threshold for blob candidate generation.",
                    "- Min area: Rejects tiny blobs; increase to reduce noise.",
                    "- Min circularity: 0..1; higher rejects non-circular shapes.",
                    "- ML: Select an ONNX model and input size if using detector type ML.",
                    "",
                    "Tip: Start with MODE_A and lower thresholds until the cue card is detected.",
                ]
            )
        )

        # Detection mode
        self._mode = QtWidgets.QComboBox()
        self._mode.addItems([Mode.MODE_A.value, Mode.MODE_B.value])
        self._mode.setCurrentText(mode)

        # Detector type
        self._detector_type = QtWidgets.QComboBox()
        self._detector_type.addItem("Classical", "classical")
        self._detector_type.addItem("ML (ONNX)", "ml")
        self._detector_type.setCurrentIndex(0 if detector_type != "ml" else 1)

        # ML model fields
        self._model_path = QtWidgets.QLineEdit(model_path or "")
        self._model_browse = QtWidgets.QPushButton("Browse")
        self._model_browse.clicked.connect(self._browse_model)

        self._model_input_w = QtWidgets.QSpinBox()
        self._model_input_h = QtWidgets.QSpinBox()
        for field in (self._model_input_w, self._model_input_h):
            field.setMinimum(64)
            field.setMaximum(2048)
        self._model_input_w.setValue(int(model_input_size[0]))
        self._model_input_h.setValue(int(model_input_size[1]))

        self._model_conf = QtWidgets.QDoubleSpinBox()
        self._model_conf.setDecimals(2)
        self._model_conf.setRange(0.0, 1.0)
        self._model_conf.setSingleStep(0.05)
        self._model_conf.setValue(float(model_conf_threshold))

        self._model_class_id = QtWidgets.QSpinBox()
        self._model_class_id.setMinimum(0)
        self._model_class_id.setMaximum(1000)
        self._model_class_id.setValue(int(model_class_id))

        self._model_format = QtWidgets.QComboBox()
        self._model_format.addItems(["yolo_v5"])
        self._model_format.setCurrentText(model_format or "yolo_v5")

        # Classical detector parameters
        self._frame_diff = QtWidgets.QDoubleSpinBox()
        self._bg_diff = QtWidgets.QDoubleSpinBox()
        self._bg_alpha = QtWidgets.QDoubleSpinBox()
        self._edge_thresh = QtWidgets.QDoubleSpinBox()
        self._blob_thresh = QtWidgets.QDoubleSpinBox()
        self._min_area = QtWidgets.QSpinBox()
        self._min_circ = QtWidgets.QDoubleSpinBox()

        # Threading
        self._threading = QtWidgets.QComboBox()
        self._threading.addItem("Per-camera threads", "per_camera")
        self._threading.addItem("Worker pool", "worker_pool")
        self._threading.setCurrentIndex(
            0 if threading_mode == "per_camera" else 1
        )

        self._workers = QtWidgets.QSpinBox()
        self._workers.setMinimum(1)
        self._workers.setMaximum(8)
        self._workers.setValue(max(1, int(worker_count)))

        # Configure spin boxes
        for field in (
            self._frame_diff,
            self._bg_diff,
            self._bg_alpha,
            self._edge_thresh,
            self._blob_thresh,
            self._min_circ,
        ):
            field.setDecimals(2)
            field.setMaximum(10_000.0)

        self._bg_alpha.setMaximum(1.0)
        self._bg_alpha.setSingleStep(0.01)
        self._min_area.setMaximum(100_000)

        # Set values
        self._frame_diff.setValue(frame_diff)
        self._bg_diff.setValue(bg_diff)
        self._bg_alpha.setValue(bg_alpha)
        self._edge_thresh.setValue(edge_thresh)
        self._blob_thresh.setValue(blob_thresh)
        self._min_area.setValue(min_area)
        self._min_circ.setValue(min_circ)

        # Form layout
        form = QtWidgets.QFormLayout()
        form.addRow("Detector type", self._detector_type)

        model_row = QtWidgets.QHBoxLayout()
        model_row.addWidget(self._model_path)
        model_row.addWidget(self._model_browse)
        form.addRow("Model path", model_row)

        input_row = QtWidgets.QHBoxLayout()
        input_row.addWidget(QtWidgets.QLabel("W"))
        input_row.addWidget(self._model_input_w)
        input_row.addWidget(QtWidgets.QLabel("H"))
        input_row.addWidget(self._model_input_h)
        form.addRow("Model input", input_row)

        form.addRow("Model conf", self._model_conf)
        form.addRow("Model class id", self._model_class_id)
        form.addRow("Model format", self._model_format)
        form.addRow("Mode", self._mode)
        form.addRow("Frame diff", self._frame_diff)
        form.addRow("BG diff", self._bg_diff)
        form.addRow("BG alpha", self._bg_alpha)
        form.addRow("Edge thresh", self._edge_thresh)
        form.addRow("Blob thresh", self._blob_thresh)
        form.addRow("Min area", self._min_area)
        form.addRow("Min circularity", self._min_circ)
        form.addRow("Detection threading", self._threading)
        form.addRow("Worker count (pool)", self._workers)

        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        apply_button = QtWidgets.QPushButton("Apply")
        cancel_button = QtWidgets.QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(help_text)
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

        # Connect toggle for ML fields
        self._detector_type.currentIndexChanged.connect(self._toggle_model_fields)
        self._toggle_model_fields()

    def values(self) -> dict:
        """Get configured detector settings.

        Returns:
            Dictionary of all detector settings
        """
        return {
            "mode": self._mode.currentText(),
            "frame_diff": self._frame_diff.value(),
            "bg_diff": self._bg_diff.value(),
            "bg_alpha": self._bg_alpha.value(),
            "edge_thresh": self._edge_thresh.value(),
            "blob_thresh": self._blob_thresh.value(),
            "min_area": self._min_area.value(),
            "min_circ": self._min_circ.value(),
            "threading_mode": self._threading.currentData(),
            "worker_count": self._workers.value(),
            "detector_type": self._detector_type.currentData(),
            "model_path": self._model_path.text().strip(),
            "model_input_size": (
                int(self._model_input_w.value()),
                int(self._model_input_h.value()),
            ),
            "model_conf_threshold": float(self._model_conf.value()),
            "model_class_id": int(self._model_class_id.value()),
            "model_format": self._model_format.currentText().strip(),
        }

    def _toggle_model_fields(self) -> None:
        """Enable/disable ML model fields based on detector type."""
        use_ml = self._detector_type.currentData() == "ml"
        for widget in (
            self._model_path,
            self._model_browse,
            self._model_input_w,
            self._model_input_h,
            self._model_conf,
            self._model_class_id,
            self._model_format,
        ):
            widget.setEnabled(use_ml)

    def _browse_model(self) -> None:
        """Open file browser dialog for ONNX model selection."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select ONNX model",
            str(Path(".")),
            "ONNX Files (*.onnx)",
        )
        if path:
            self._model_path.setText(path)


__all__ = ["DetectorSettingsDialog"]

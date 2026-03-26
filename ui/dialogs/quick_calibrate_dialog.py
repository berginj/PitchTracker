"""Quick calibration dialog for stereo calibration from checkerboard images."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from app.services.tooling import get_tooling_service
from contracts.tooling import CalibrationRequest
from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    get_style_manager,
    polish_form_controls,
    show_message_dialog,
)


class QuickCalibrateDialog(QtWidgets.QDialog):
    """Dialog for running quick stereo calibration from checkerboard images."""

    def __init__(self, parent: QtWidgets.QWidget | None, config_path: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Calibrate")
        self.resize(560, 340)

        self._style_manager = get_style_manager()
        self._config_path = config_path
        self.updated = False
        self.updates: dict | None = None

        self._left_dir = QtWidgets.QLineEdit()
        self._right_dir = QtWidgets.QLineEdit()
        self._pattern = QtWidgets.QLineEdit("9x6")
        self._square_mm = QtWidgets.QDoubleSpinBox()
        self._square_mm.setMinimum(1.0)
        self._square_mm.setMaximum(1000.0)
        self._square_mm.setValue(25.0)
        self._ext = QtWidgets.QLineEdit("*.png")

        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI."""
        left_browse = QtWidgets.QPushButton("Browse")
        right_browse = QtWidgets.QPushButton("Browse")
        left_browse.clicked.connect(lambda: self._browse_dir(self._left_dir))
        right_browse.clicked.connect(lambda: self._browse_dir(self._right_dir))
        self._style_manager.style_button(left_browse, "ghost")
        self._style_manager.style_button(right_browse, "ghost")

        form = QtWidgets.QFormLayout()
        apply_standard_layout(form, margins=(0, 0, 0, 0), spacing=12)

        left_row = QtWidgets.QHBoxLayout()
        left_row.setSpacing(10)
        left_row.addWidget(self._left_dir)
        left_row.addWidget(left_browse)

        right_row = QtWidgets.QHBoxLayout()
        right_row.setSpacing(10)
        right_row.addWidget(self._right_dir)
        right_row.addWidget(right_browse)

        form.addRow("Left images folder", left_row)
        form.addRow("Right images folder", right_row)
        form.addRow("Pattern (cols x rows)", self._pattern)
        form.addRow("Square size (mm)", self._square_mm)
        form.addRow("Image glob", self._ext)

        run_button = QtWidgets.QPushButton("Run Calibration")
        close_button = QtWidgets.QPushButton("Close")
        run_button.clicked.connect(self._run)
        close_button.clicked.connect(self.reject)
        self._style_manager.style_button(run_button, "primary")
        self._style_manager.style_button(close_button, "ghost")

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch()
        buttons.addWidget(close_button)
        buttons.addWidget(run_button)

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addWidget(
            build_dialog_header(
                "Quick Calibrate",
                "Run a fast stereo calibration using existing checkerboard captures from disk.",
            )
        )
        layout.addLayout(form)
        layout.addStretch()
        layout.addLayout(buttons)
        self.setLayout(layout)

        polish_form_controls(self)

    def _browse_dir(self, target: QtWidgets.QLineEdit) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            target.setText(path)

    def _run(self) -> None:
        left_dir = Path(self._left_dir.text().strip())
        right_dir = Path(self._right_dir.text().strip())
        pattern = self._pattern.text().strip()
        glob_pattern = self._ext.text().strip() or "*.png"
        if not left_dir.exists() or not right_dir.exists():
            show_message_dialog(self, "Quick Calibrate", "Select both folders.", tone="warning")
            return

        left_paths = sorted(left_dir.glob(glob_pattern))
        right_paths = sorted(right_dir.glob(glob_pattern))
        if not left_paths or not right_paths:
            show_message_dialog(self, "Quick Calibrate", "No images found.", tone="warning")
            return

        progress = QtWidgets.QProgressDialog("Running calibration...", "Cancel", 0, 0, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        QtWidgets.QApplication.processEvents()

        try:
            result = get_tooling_service().run_calibration(
                CalibrationRequest(
                    left_paths=tuple(left_paths),
                    right_paths=tuple(right_paths),
                    pattern=pattern,
                    square_mm=self._square_mm.value(),
                    config_path=self._config_path,
                    mode="quick",
                    write_updates=True,
                )
            )
        except Exception as exc:  # noqa: BLE001 - user-facing error dialog
            progress.close()
            show_message_dialog(self, "Quick Calibrate", str(exc), tone="error")
            return
        finally:
            progress.close()

        rejected = max(0, result.total_input_images - result.num_images_used)
        quality_token = result.quality_emoji or "[OK]"
        message = f"{quality_token} Calibration Quality: {result.quality_rating}\n"
        message += f"{result.quality_description}\n\n"
        message += f"RMS Reprojection Error: {result.rms_error_px:.3f} px\n"
        message += f"Images Used: {result.num_images_used}/{result.total_input_images}"

        if rejected > 0:
            message += f"\nRejected: {rejected} pairs (corner detection failed)"

        if result.recommendations:
            message += "\n\nRecommendations:\n"
            for recommendation in result.recommendations:
                message += f"- {recommendation}\n"

        message += "\n\nUpdated Configuration:\n"
        message += f"Baseline: {result.baseline_ft:.3f} ft\n"
        message += f"Focal Length: {result.focal_length_px:.1f} px"

        show_message_dialog(
            self,
            "Calibration Complete",
            message,
            tone="success",
            primary_buttons=(QtWidgets.QMessageBox.StandardButton.Ok,),
        )

        self.updated = True
        self.updates = result.to_payload()


__all__ = ["QuickCalibrateDialog"]

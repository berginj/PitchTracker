"""Quick calibration dialog for stereo calibration from checkerboard images."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from calib.quick_calibrate import calibrate_and_write


class QuickCalibrateDialog(QtWidgets.QDialog):
    """Dialog for running quick stereo calibration from checkerboard images."""

    def __init__(self, parent: QtWidgets.QWidget | None, config_path: Path) -> None:
        """Initialize quick calibration dialog.

        Args:
            parent: Parent widget
            config_path: Path to config file to update
        """
        super().__init__(parent)
        self.setWindowTitle("Quick Calibrate")
        self.resize(520, 240)
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

        left_browse = QtWidgets.QPushButton("Browse")
        right_browse = QtWidgets.QPushButton("Browse")
        left_browse.clicked.connect(lambda: self._browse_dir(self._left_dir))
        right_browse.clicked.connect(lambda: self._browse_dir(self._right_dir))

        form = QtWidgets.QFormLayout()
        left_row = QtWidgets.QHBoxLayout()
        left_row.addWidget(self._left_dir)
        left_row.addWidget(left_browse)
        right_row = QtWidgets.QHBoxLayout()
        right_row.addWidget(self._right_dir)
        right_row.addWidget(right_browse)
        form.addRow("Left images folder", left_row)
        form.addRow("Right images folder", right_row)
        form.addRow("Pattern (cols x rows)", self._pattern)
        form.addRow("Square size (mm)", self._square_mm)
        form.addRow("Image glob", self._ext)

        buttons = QtWidgets.QHBoxLayout()
        run_button = QtWidgets.QPushButton("Run Calibration")
        close_button = QtWidgets.QPushButton("Close")
        run_button.clicked.connect(self._run)
        close_button.clicked.connect(self.reject)
        buttons.addWidget(run_button)
        buttons.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _browse_dir(self, target: QtWidgets.QLineEdit) -> None:
        """Open folder browser dialog.

        Args:
            target: QLineEdit to update with selected folder
        """
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            target.setText(path)

    def _run(self) -> None:
        """Run stereo calibration from selected folders."""
        left_dir = Path(self._left_dir.text().strip())
        right_dir = Path(self._right_dir.text().strip())
        pattern = self._pattern.text().strip()
        glob_pattern = self._ext.text().strip() or "*.png"
        if not left_dir.exists() or not right_dir.exists():
            QtWidgets.QMessageBox.warning(self, "Quick Calibrate", "Select both folders.")
            return
        left_paths = sorted(left_dir.glob(glob_pattern))
        right_paths = sorted(right_dir.glob(glob_pattern))
        if not left_paths or not right_paths:
            QtWidgets.QMessageBox.warning(self, "Quick Calibrate", "No images found.")
            return
        try:
            updates = calibrate_and_write(
                left_paths=left_paths,
                right_paths=right_paths,
                pattern=pattern,
                square_mm=self._square_mm.value(),
                config_path=self._config_path,
            )
        except Exception as exc:  # noqa: BLE001 - show calibration errors
            QtWidgets.QMessageBox.critical(self, "Quick Calibrate", str(exc))
            return
        QtWidgets.QMessageBox.information(
            self,
            "Quick Calibrate",
            f"Updated stereo config: {updates}",
        )
        self.updated = True
        self.updates = updates


__all__ = ["QuickCalibrateDialog"]

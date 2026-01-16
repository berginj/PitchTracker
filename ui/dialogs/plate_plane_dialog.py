"""Plate plane calibration dialog for estimating plate plane Z coordinate."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets


class PlatePlaneDialog(QtWidgets.QDialog):
    """Dialog for selecting image pair for plate plane calibration."""

    def __init__(self, parent: QtWidgets.QWidget | None, config_path: Path) -> None:
        """Initialize plate plane calibration dialog.

        Args:
            parent: Parent widget
            config_path: Path to config file (currently unused, reserved for future)
        """
        super().__init__(parent)
        self.setWindowTitle("Plate Plane Calibrate")
        self.resize(520, 200)
        self._left = QtWidgets.QLineEdit()
        self._right = QtWidgets.QLineEdit()
        left_browse = QtWidgets.QPushButton("Browse")
        right_browse = QtWidgets.QPushButton("Browse")
        left_browse.clicked.connect(lambda: self._browse(self._left))
        right_browse.clicked.connect(lambda: self._browse(self._right))

        form = QtWidgets.QFormLayout()
        left_row = QtWidgets.QHBoxLayout()
        left_row.addWidget(self._left)
        left_row.addWidget(left_browse)
        right_row = QtWidgets.QHBoxLayout()
        right_row.addWidget(self._right)
        right_row.addWidget(right_browse)
        form.addRow("Left image", left_row)
        form.addRow("Right image", right_row)

        buttons = QtWidgets.QHBoxLayout()
        run_button = QtWidgets.QPushButton("Run")
        cancel_button = QtWidgets.QPushButton("Cancel")
        run_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(run_button)
        buttons.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _browse(self, target: QtWidgets.QLineEdit) -> None:
        """Open file browser dialog for image selection.

        Args:
            target: QLineEdit to update with selected file path
        """
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select image",
            str(Path("recordings")),
            "Image Files (*.png *.jpg *.jpeg *.bmp)",
        )
        if path:
            target.setText(path)

    def values(self) -> tuple[str, str]:
        """Get selected image paths.

        Returns:
            Tuple of (left_image_path, right_image_path)
        """
        return (self._left.text().strip(), self._right.text().strip())


__all__ = ["PlatePlaneDialog"]

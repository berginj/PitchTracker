"""Plate plane calibration dialog for estimating plate plane Z coordinate."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    get_style_manager,
    style_dialog_button_box,
)


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
        self.resize(600, 280)
        self._style_manager = get_style_manager()
        self._config_path = config_path

        # Initialize widgets
        self._left = QtWidgets.QLineEdit()
        self._right = QtWidgets.QLineEdit()

        self._left_browse = QtWidgets.QPushButton("Browse...")
        self._right_browse = QtWidgets.QPushButton("Browse...")
        self._left_browse.clicked.connect(lambda: self._browse(self._left))
        self._right_browse.clicked.connect(lambda: self._browse(self._right))

        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI with theme system."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        # Header
        header = build_dialog_header(
            "Plate Plane Calibration",
            "Select stereo image pair containing plate reference"
        )
        layout.addWidget(header)

        # Form
        form = QtWidgets.QFormLayout()
        form.setSpacing(12)

        left_row = QtWidgets.QHBoxLayout()
        left_row.addWidget(self._left, 1)
        left_row.addWidget(self._left_browse)

        right_row = QtWidgets.QHBoxLayout()
        right_row.addWidget(self._right, 1)
        right_row.addWidget(self._right_browse)

        form.addRow("Left image:", left_row)
        form.addRow("Right image:", right_row)
        layout.addLayout(form)

        # Buttons
        button_box = QtWidgets.QDialogButtonBox()
        run_btn = button_box.addButton("Run Calibration", QtWidgets.QDialogButtonBox.AcceptRole)
        cancel_btn = button_box.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
        style_dialog_button_box(button_box, primary=True)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self._style_manager.polish_form_controls(self)

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

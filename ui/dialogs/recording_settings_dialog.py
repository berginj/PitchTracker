"""Recording settings dialog for session configuration."""

from __future__ import annotations


from PySide6 import QtWidgets

from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    get_style_manager,
    style_dialog_button_box,
)


class RecordingSettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring recording session settings."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        session: str,
        output_dir: str,
        speed_mph: float,
    ) -> None:
        """Initialize recording settings dialog.

        Args:
            parent: Parent widget
            session: Current session name
            output_dir: Current output directory
            speed_mph: Manually measured speed in mph
        """
        super().__init__(parent)
        self.setWindowTitle("Recording Settings")
        self.resize(600, 280)
        self._style_manager = get_style_manager()

        # Initialize widgets
        self._session = QtWidgets.QLineEdit(session)
        self._session.setAccessibleName("Session name")

        self._output_dir = QtWidgets.QLineEdit(output_dir)
        self._output_dir.setAccessibleName("Output directory")

        self._speed = QtWidgets.QDoubleSpinBox()
        self._speed.setAccessibleName("Measured speed")
        self._speed.setMinimum(0.0)
        self._speed.setMaximum(130.0)
        self._speed.setSuffix(" mph")
        self._speed.setValue(speed_mph)

        self._browse_button = QtWidgets.QPushButton("Browse...")
        self._browse_button.setAccessibleName("Browse output directory")
        self._browse_button.clicked.connect(self._browse)

        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI with theme system."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        # Header
        header = build_dialog_header(
            "Recording Settings", "Configure session name, output location, and reference speed"
        )
        layout.addWidget(header)

        # Form layout
        form = QtWidgets.QFormLayout()
        form.setSpacing(12)

        output_row = QtWidgets.QHBoxLayout()
        output_row.addWidget(self._output_dir, 1)
        output_row.addWidget(self._browse_button)

        form.addRow("Session name:", self._session)
        form.addRow("Output directory:", output_row)
        form.addRow("Measured speed:", self._speed)

        layout.addLayout(form)

        # Buttons
        button_box = QtWidgets.QDialogButtonBox()
        apply_btn = button_box.addButton("Apply", QtWidgets.QDialogButtonBox.AcceptRole)
        apply_btn.setAccessibleName("Apply recording settings")
        cancel_btn = button_box.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
        cancel_btn.setAccessibleName("Cancel recording settings")
        style_dialog_button_box(button_box, primary=True)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self._style_manager.polish_form_controls(self)

    def _browse(self) -> None:
        """Open folder browser dialog."""
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self._output_dir.setText(path)

    def values(self) -> tuple[str, str, float]:
        """Get configured values.

        Returns:
            Tuple of (session_name, output_dir, speed_mph)
        """
        return (
            self._session.text().strip(),
            self._output_dir.text().strip(),
            self._speed.value(),
        )


__all__ = ["RecordingSettingsDialog"]

"""Recording settings dialog for session configuration."""

from __future__ import annotations

from PySide6 import QtWidgets


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
        self.resize(520, 220)

        self._session = QtWidgets.QLineEdit(session)
        self._output_dir = QtWidgets.QLineEdit(output_dir)

        self._speed = QtWidgets.QDoubleSpinBox()
        self._speed.setMinimum(0.0)
        self._speed.setMaximum(130.0)
        self._speed.setSuffix(" mph")
        self._speed.setValue(speed_mph)

        browse_button = QtWidgets.QPushButton("Browse")
        browse_button.clicked.connect(self._browse)

        # Form layout
        form = QtWidgets.QFormLayout()

        output_row = QtWidgets.QHBoxLayout()
        output_row.addWidget(self._output_dir)
        output_row.addWidget(browse_button)

        form.addRow("Session name", self._session)
        form.addRow("Output dir", output_row)
        form.addRow("Measured speed", self._speed)

        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        apply_button = QtWidgets.QPushButton("Apply")
        cancel_button = QtWidgets.QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

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

"""Pre-recording checklist dialog."""

from __future__ import annotations

from PySide6 import QtWidgets


class ChecklistDialog(QtWidgets.QDialog):
    """Dialog displaying pre-recording checklist."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize checklist dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Pre-Record Checklist")
        self.resize(520, 360)

        steps = QtWidgets.QTextEdit()
        steps.setReadOnly(True)
        steps.setText(
            "\n".join(
                [
                    "Pre-Recording Checklist:",
                    "",
                    "- Lenses focused and locked",
                    "- Exposure/gain set to manual",
                    "- FPS stable (>= 58) on both cameras",
                    "- Lane ROI and Plate ROI saved",
                    "- Strike zone settings verified",
                    "- Session name set",
                ]
            )
        )

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(steps)
        layout.addWidget(close_button)
        self.setLayout(layout)


__all__ = ["ChecklistDialog"]

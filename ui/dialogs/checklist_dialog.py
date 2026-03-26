"""Pre-recording checklist dialog."""

from __future__ import annotations

from PySide6 import QtWidgets

from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    get_style_manager,
    style_dialog_button_box,
)


class ChecklistDialog(QtWidgets.QDialog):
    """Dialog displaying pre-recording checklist."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize checklist dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Pre-Record Checklist")
        self.resize(520, 420)
        self._style_manager = get_style_manager()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI with theme system."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        # Header
        header = build_dialog_header(
            "Pre-Recording Checklist",
            "Verify all items before starting recording"
        )
        layout.addWidget(header)

        # Checklist content
        steps = QtWidgets.QTextEdit()
        steps.setReadOnly(True)
        steps.setProperty("role", "panelMessage")
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
        layout.addWidget(steps)

        # Buttons
        button_box = QtWidgets.QDialogButtonBox()
        close_btn = button_box.addButton("Close", QtWidgets.QDialogButtonBox.AcceptRole)
        style_dialog_button_box(button_box, primary=True)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self._style_manager.polish_form_controls(self)


__all__ = ["ChecklistDialog"]

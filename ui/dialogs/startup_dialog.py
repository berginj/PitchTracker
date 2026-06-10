"""Startup dialog for location and pitcher selection."""

from __future__ import annotations

from PySide6 import QtWidgets

from configs.app_state import load_state
from configs.location_profiles import list_profiles
from configs.pitchers import load_pitchers
from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    get_style_manager,
    style_dialog_button_box,
)


class StartupDialog(QtWidgets.QDialog):
    """Dialog for selecting location profile and pitcher at startup."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize startup dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Select Location and Pitcher")
        self.resize(520, 280)
        self._style_manager = get_style_manager()

        # Initialize widgets
        self._profile = QtWidgets.QComboBox()
        self._profile.addItems(list_profiles())

        self._pitcher = QtWidgets.QComboBox()
        self._pitcher.setEditable(True)
        self._pitcher.addItems(load_pitchers())

        # Restore last pitcher from app state
        state = load_state()
        last_pitcher = state.get("last_pitcher")
        if last_pitcher:
            self._pitcher.setCurrentText(last_pitcher)

        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI with theme system."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        # Header
        header = build_dialog_header("Session Setup", "Select location profile and pitcher to begin")
        layout.addWidget(header)

        # Form
        form = QtWidgets.QFormLayout()
        form.setSpacing(12)
        form.addRow("Location profile:", self._profile)
        form.addRow("Pitcher:", self._pitcher)
        layout.addLayout(form)

        # Buttons
        button_box = QtWidgets.QDialogButtonBox()
        button_box.addButton("Continue", QtWidgets.QDialogButtonBox.AcceptRole)
        button_box.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
        style_dialog_button_box(button_box, primary=True)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self._style_manager.polish_form_controls(self)

    def values(self) -> tuple[str, str]:
        """Get selected profile and pitcher names.

        Returns:
            Tuple of (profile_name, pitcher_name)
        """
        return (
            self._profile.currentText().strip(),
            self._pitcher.currentText().strip(),
        )


__all__ = ["StartupDialog"]

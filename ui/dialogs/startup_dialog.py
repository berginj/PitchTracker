"""Startup dialog for location and pitcher selection."""

from __future__ import annotations

from PySide6 import QtWidgets

from configs.location_profiles import list_profiles
from configs.pitchers import load_pitchers
from configs.app_state import load_state


class StartupDialog(QtWidgets.QDialog):
    """Dialog for selecting location profile and pitcher at startup."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize startup dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Select Location and Pitcher")
        self.resize(520, 220)

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

        form = QtWidgets.QFormLayout()
        form.addRow("Location profile", self._profile)
        form.addRow("Pitcher", self._pitcher)

        buttons = QtWidgets.QHBoxLayout()
        apply_button = QtWidgets.QPushButton("Continue")
        cancel_button = QtWidgets.QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

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

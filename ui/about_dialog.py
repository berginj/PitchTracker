"""About dialog for the launcher."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ui.themes import get_style_manager
from updater import get_current_version


class AboutDialog(QtWidgets.QDialog):
    """About dialog with version and project information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About PitchTracker")
        self.resize(500, 400)
        self._build_ui()

    def _build_ui(self):
        """Build about dialog UI."""
        sm = get_style_manager()
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QtWidgets.QLabel("PitchTracker")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sm.style_label(title, "pageTitle")
        layout.addWidget(title)

        version = QtWidgets.QLabel(f"Version {get_current_version()}")
        version.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sm.style_label(version, "eyebrow")
        layout.addWidget(version)

        description = QtWidgets.QLabel(
            "A dual-camera stereo vision system for baseball pitch tracking and analysis.\n\n"
            "Features:\n"
            "• Real-time pitch detection and tracking\n"
            "• Stereo calibration and 3D trajectory reconstruction\n"
            "• Strike zone analysis\n"
            "• Session recording and metrics\n"
            "• Role-based interfaces (Setup Wizard + Coaching App)"
        )
        description.setWordWrap(True)
        sm.style_label(description, "muted")
        layout.addWidget(description)

        components = QtWidgets.QLabel(
            "Key Components:\n"
            "• Setup Wizard - Guided system configuration\n"
            "• Coaching App - Real-time session management\n"
            "• Pipeline Service - Detection and tracking engine\n"
            "• Calibration Tools - Stereo camera calibration"
        )
        components.setWordWrap(True)
        sm.style_label(components, "eyebrow")
        layout.addWidget(components)

        layout.addStretch()

        close_button = QtWidgets.QPushButton("Close")
        sm.style_button(close_button, "primary")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)


__all__ = ["AboutDialog"]

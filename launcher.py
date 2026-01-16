#!/usr/bin/env python
"""PitchTracker unified launcher - role selector entry point."""

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


class AboutDialog(QtWidgets.QDialog):
    """About dialog with version and project information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About PitchTracker")
        self.resize(500, 400)
        self._build_ui()

    def _build_ui(self):
        """Build about dialog UI."""
        layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("PitchTracker")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24pt; font-weight: bold; color: #2196F3; padding: 20px;")
        layout.addWidget(title)

        # Version
        version = QtWidgets.QLabel("Version 1.0.0")
        version.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("font-size: 12pt; color: #666; padding-bottom: 20px;")
        layout.addWidget(version)

        # Description
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
        description.setStyleSheet("padding: 20px; background-color: #f5f5f5; border-radius: 5px;")
        layout.addWidget(description)

        # Components
        components = QtWidgets.QLabel(
            "Key Components:\n"
            "• Setup Wizard - Guided system configuration\n"
            "• Coaching App - Real-time session management\n"
            "• Pipeline Service - Detection and tracking engine\n"
            "• Calibration Tools - Stereo camera calibration"
        )
        components.setWordWrap(True)
        components.setStyleSheet("padding: 10px; font-size: 9pt;")
        layout.addWidget(components)

        layout.addStretch()

        # Close button
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)


class LauncherWindow(QtWidgets.QMainWindow):
    """Main launcher window with role selector."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PitchTracker")
        self.resize(800, 600)
        self._build_ui()

    def _build_ui(self):
        """Build launcher UI."""
        # Central widget
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        # Logo/Title area
        title_widget = self._build_title()
        layout.addWidget(title_widget)

        # Role selection buttons
        buttons_widget = self._build_role_buttons()
        layout.addWidget(buttons_widget, 1)

        # Footer with About
        footer_widget = self._build_footer()
        layout.addWidget(footer_widget)

        central.setLayout(layout)
        self.setCentralWidget(central)

        # Set window icon if available
        self._set_window_icon()

    def _build_title(self) -> QtWidgets.QWidget:
        """Build title area."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        # Main title
        title = QtWidgets.QLabel("PitchTracker")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 36pt; font-weight: bold; color: #2196F3; padding: 20px;"
        )
        layout.addWidget(title)

        # Subtitle
        subtitle = QtWidgets.QLabel("Baseball Pitch Tracking & Analysis System")
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 14pt; color: #666; padding-bottom: 10px;")
        layout.addWidget(subtitle)

        # Instruction
        instruction = QtWidgets.QLabel("Select your role to begin:")
        instruction.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        instruction.setStyleSheet("font-size: 12pt; color: #999; padding-top: 20px;")
        layout.addWidget(instruction)

        widget.setLayout(layout)
        return widget

    def _build_role_buttons(self) -> QtWidgets.QWidget:
        """Build role selection buttons."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(40)

        # Setup Wizard button
        setup_button = self._create_role_button(
            "🔧 Setup & Calibration",
            "For technicians and installers\n\n"
            "• Camera configuration\n"
            "• Stereo calibration\n"
            "• ROI setup\n"
            "• System validation\n\n"
            "Run once or when reconfiguring",
            "#4CAF50",
            self._launch_setup,
        )

        # Coaching App button
        coach_button = self._create_role_button(
            "⚾ Coaching Sessions",
            "For coaches and pitchers\n\n"
            "• Start/stop sessions\n"
            "• Live pitch tracking\n"
            "• Real-time metrics\n"
            "• Session summaries\n\n"
            "Use daily for practice",
            "#2196F3",
            self._launch_coaching,
        )

        layout.addWidget(setup_button)
        layout.addWidget(coach_button)

        widget.setLayout(layout)
        return widget

    def _create_role_button(
        self, title: str, description: str, color: str, callback
    ) -> QtWidgets.QPushButton:
        """Create a styled role selection button."""
        button = QtWidgets.QPushButton()
        button.setMinimumSize(300, 350)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        # Create label with formatted text
        label_layout = QtWidgets.QVBoxLayout()

        # Title
        title_label = QtWidgets.QLabel(title)
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: white; padding: 10px;")
        title_label.setWordWrap(True)

        # Description
        desc_label = QtWidgets.QLabel(description)
        desc_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        desc_label.setStyleSheet("font-size: 11pt; color: white; padding: 15px;")
        desc_label.setWordWrap(True)

        label_layout.addWidget(title_label)
        label_layout.addWidget(desc_label)
        label_layout.addStretch()

        # Container widget for the layout
        container = QtWidgets.QWidget()
        container.setLayout(label_layout)

        # Use a grid layout to center the container
        button_layout = QtWidgets.QGridLayout()
        button_layout.addWidget(container, 0, 0)
        button.setLayout(button_layout)

        # Styling
        button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {color};
                border: none;
                border-radius: 10px;
                padding: 20px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(color, 0.8)};
            }}
            """
        )

        button.clicked.connect(callback)
        return button

    def _darken_color(self, color: str, factor: float = 0.9) -> str:
        """Darken a hex color by a factor."""
        # Simple darkening - multiply RGB values
        color = color.lstrip("#")
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _build_footer(self) -> QtWidgets.QWidget:
        """Build footer with about button."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()

        # About button
        about_button = QtWidgets.QPushButton("ℹ About")
        about_button.setMinimumHeight(40)
        about_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        about_button.clicked.connect(self._show_about)
        about_button.setStyleSheet(
            """
            QPushButton {
                font-size: 11pt;
                padding: 10px 20px;
                border: 2px solid #2196F3;
                border-radius: 5px;
                background-color: white;
                color: #2196F3;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
            """
        )

        layout.addStretch()
        layout.addWidget(about_button)

        widget.setLayout(layout)
        return widget

    def _set_window_icon(self):
        """Set window icon if available."""
        # Try to set an icon (placeholder for now)
        pass

    def _launch_setup(self):
        """Launch Setup Wizard."""
        try:
            # Import here to avoid circular imports
            from ui.setup import SetupWindow

            # Close launcher
            self.hide()

            # Create and show setup window
            self.setup_window = SetupWindow(backend="uvc")
            self.setup_window.show()

            # When setup window closes, show launcher again
            self.setup_window.destroyed.connect(self._on_child_closed)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Launch Error",
                f"Failed to launch Setup Wizard:\n{str(e)}\n\n"
                "Make sure all dependencies are installed.",
            )
            self.show()

    def _launch_coaching(self):
        """Launch Coaching App."""
        try:
            # Import here to avoid circular imports
            from ui.coaching import CoachWindow

            # Close launcher
            self.hide()

            # Create and show coaching window
            self.coach_window = CoachWindow(backend="uvc")
            self.coach_window.show()

            # When coaching window closes, show launcher again
            self.coach_window.destroyed.connect(self._on_child_closed)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Launch Error",
                f"Failed to launch Coaching App:\n{str(e)}\n\n"
                "Make sure all dependencies are installed and "
                "the system is configured (run Setup Wizard first).",
            )
            self.show()

    def _on_child_closed(self):
        """Called when a child window is closed."""
        # Show launcher again
        self.show()

    def _show_about(self):
        """Show about dialog."""
        dialog = AboutDialog(self)
        dialog.exec()


def main():
    """Main entry point."""
    app = QtWidgets.QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Set application metadata
    app.setApplicationName("PitchTracker")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PitchTracker")

    # Create and show launcher
    launcher = LauncherWindow()
    launcher.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

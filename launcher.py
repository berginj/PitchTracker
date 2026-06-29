#!/usr/bin/env python
"""PitchTracker unified launcher - role selector entry point."""

import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets


def _ensure_project_root_on_sys_path(project_root: Path) -> None:
    """Insert the project root once, normalized for Windows path casing."""
    normalized_root = os.path.normcase(str(project_root))
    for entry in sys.path:
        if os.path.normcase(entry) == normalized_root:
            return
    sys.path.insert(0, str(project_root))


# Add project root to path and set working directory
project_root = Path(__file__).parent.resolve()
_ensure_project_root_on_sys_path(project_root)
os.chdir(project_root)

from app.services.tooling import ToolingService, get_tooling_service  # noqa: E402
from launcher_support import clear_python_cache  # noqa: E402
from launcher_threads import StartupValidationThread  # noqa: E402
from launcher_updates import LauncherUpdateController  # noqa: E402
from startup_validator import create_required_directories  # noqa: E402
from ui.about_dialog import AboutDialog  # noqa: E402
from ui.themes import get_style_manager  # noqa: E402
from updater import (  # noqa: E402
    get_current_version,
    is_auto_update_enabled,
    set_auto_update_enabled,
)

__all__ = ["LauncherWindow", "clear_python_cache", "main"]


class LauncherWindow(QtWidgets.QMainWindow):
    """Main launcher window with role selector."""

    def __init__(
        self,
        startup_warnings: list[str] | None = None,
        validation_service: ToolingService | None = None,
    ):
        super().__init__()
        self._style_manager = get_style_manager()
        self._startup_warnings = list(startup_warnings or [])
        self._startup_errors: list[str] = []
        self._validation_state = "pending"
        self._validation_service = validation_service or get_tooling_service()
        self._validation_thread: StartupValidationThread | None = None
        self._update_controller = LauncherUpdateController(self)
        self.setWindowTitle("PitchTracker")
        self.resize(800, 600)
        self._build_ui()

        QtCore.QTimer.singleShot(0, self._start_environment_validation)
        # Check for updates after a short delay (non-blocking)
        QtCore.QTimer.singleShot(2000, self._update_controller.check_for_updates)

    def _build_ui(self):
        """Build launcher UI."""
        # Central widget
        central = QtWidgets.QWidget()
        central.setObjectName("LauncherShell")
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(18)

        # Logo/Title area
        title_widget = self._build_title()
        layout.addWidget(title_widget)

        # Startup warnings banner
        layout.addWidget(self._build_warning_banner())

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
        self._set_role_buttons_enabled(False)

    def _build_title(self) -> QtWidgets.QWidget:
        """Build title area."""
        widget = QtWidgets.QFrame()
        self._style_manager.style_panel(widget, "normal")
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(8)

        # Main title
        title = QtWidgets.QLabel("PitchTracker")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._style_manager.style_label(title, "title")
        layout.addWidget(title)

        # Subtitle
        subtitle = QtWidgets.QLabel("Baseball Pitch Tracking & Analysis System")
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._style_manager.style_label(subtitle, "muted")
        layout.addWidget(subtitle)

        # Instruction
        instruction = QtWidgets.QLabel("Choose the workflow that matches what you need to do next.")
        instruction.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._style_manager.style_label(instruction, "eyebrow")
        layout.addWidget(instruction)

        widget.setLayout(layout)
        return widget

    def _build_warning_banner(self) -> QtWidgets.QWidget:
        """Build a non-blocking startup status banner."""
        self._warning_frame = QtWidgets.QFrame()
        self._warning_frame.setProperty("notice", "info")
        self._style_manager.polish(self._warning_frame)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self._warning_title = QtWidgets.QLabel()
        self._style_manager.style_label(self._warning_title, "sectionTitle")
        layout.addWidget(self._warning_title)

        self._warning_body = QtWidgets.QLabel()
        self._warning_body.setWordWrap(True)
        self._warning_body.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self._style_manager.style_label(self._warning_body, "muted")
        layout.addWidget(self._warning_body)

        self._warning_frame.setLayout(layout)
        self._update_warning_banner()
        return self._warning_frame

    def _build_role_buttons(self) -> QtWidgets.QWidget:
        """Build role selection buttons."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Setup Wizard button
        self._setup_button = self._create_role_button(
            "Setup & Calibration",
            "For technicians and installers\n\n"
            "- Camera configuration\n"
            "- Stereo calibration\n"
            "- ROI setup\n"
            "- System validation\n\n"
            "Run once or when reconfiguring",
            "#4CAF50",
            self._launch_setup,
        )
        self._setup_button.setAccessibleName("Launch Setup Wizard")

        # Stereo Setup button
        self._stereo_setup_button = self._create_role_button(
            "Stereo Setup",
            "For genuine stereo rig setup\n\n"
            "- Live camera discovery\n"
            "- Paired preview checks\n"
            "- Alignment workflow\n"
            "- Calibration quality review\n\n"
            "Use for the 9-step stereo flow",
            "#4CAF50",
            self._launch_stereo_setup,
        )
        self._stereo_setup_button.setAccessibleName("Launch Stereo Setup")

        # Coaching App button
        self._coach_button = self._create_role_button(
            "Coaching Sessions",
            "For coaches and pitchers\n\n"
            "- Start/stop sessions\n"
            "- Live pitch tracking\n"
            "- Real-time metrics\n"
            "- Session summaries\n\n"
            "Use daily for practice",
            "#2196F3",
            self._launch_coaching,
        )
        self._coach_button.setAccessibleName("Launch Coaching App")

        layout.addWidget(self._setup_button)
        layout.addWidget(self._stereo_setup_button)
        layout.addWidget(self._coach_button)

        widget.setLayout(layout)
        return widget

    def _create_role_button(self, title: str, description: str, color: str, callback) -> QtWidgets.QPushButton:
        """Create a styled role selection button."""
        accent = "success" if color.lower() == "#4caf50" else "primary"

        button = QtWidgets.QPushButton()
        button.setMinimumSize(300, 350)
        button.setProperty("variant", "role-card")
        button.setProperty("accent", accent)
        self._style_manager.polish(button)

        # Create label with formatted text
        label_layout = QtWidgets.QVBoxLayout()
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(12)

        # Title
        title_label = QtWidgets.QLabel(title)
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._style_manager.style_label(title_label, "sectionTitle")
        title_label.setWordWrap(True)

        # Description
        desc_label = QtWidgets.QLabel(description)
        desc_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self._style_manager.style_label(desc_label, "muted")
        desc_label.setWordWrap(True)

        label_layout.addWidget(title_label)
        label_layout.addWidget(desc_label)
        label_layout.addStretch()

        # Container widget for the layout
        container = QtWidgets.QWidget()
        container.setLayout(label_layout)

        # Use a grid layout to center the container
        button_layout = QtWidgets.QGridLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addWidget(container, 0, 0)
        button.setLayout(button_layout)

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
        about_button.setText("About PitchTracker")
        about_button.setAccessibleName("About PitchTracker")
        about_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        about_button.clicked.connect(self._show_about)
        self._style_manager.style_button(about_button, "ghost")

        # Auto-update toggle (persisted)
        self._auto_update_checkbox = QtWidgets.QCheckBox("Install updates automatically")
        self._auto_update_checkbox.setChecked(is_auto_update_enabled())
        self._auto_update_checkbox.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._auto_update_checkbox.setToolTip(
            "When enabled, verified updates download and install automatically on launch."
        )
        self._auto_update_checkbox.toggled.connect(set_auto_update_enabled)

        layout.addWidget(self._auto_update_checkbox)
        layout.addStretch()
        layout.addWidget(about_button)

        widget.setLayout(layout)
        return widget

    def _set_window_icon(self):
        """Set window icon if available."""
        # Try to set an icon (placeholder for now)

    def _start_environment_validation(self) -> None:
        """Run startup validation after the launcher is already visible."""
        if self._validation_thread is not None:
            return

        self._validation_thread = StartupValidationThread(self._validation_service)
        self._validation_thread.validation_complete.connect(self._on_validation_complete)
        self._validation_thread.validation_failed.connect(self._on_validation_failed)
        self._validation_thread.start()

    def _on_validation_complete(self, errors: list[str], warnings: list[str]) -> None:
        """Handle background validation results."""
        thread = self._validation_thread
        self._validation_state = "completed"
        self._startup_errors = list(errors)
        self._startup_warnings = list(warnings)
        self._set_role_buttons_enabled(not bool(errors))
        self._update_warning_banner()
        self._validation_thread = None
        if thread is not None:
            thread.deleteLater()

    def _on_validation_failed(self, error_message: str) -> None:
        """Handle background validation failures."""
        thread = self._validation_thread
        self._validation_state = "completed"
        self._startup_errors = [f"Background validation failed: {error_message}"]
        self._startup_warnings = []
        self._set_role_buttons_enabled(False)
        self._update_warning_banner()
        self._validation_thread = None
        if thread is not None:
            thread.deleteLater()

    def _set_role_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable launcher entry points."""
        self._setup_button.setEnabled(enabled)
        self._stereo_setup_button.setEnabled(enabled)
        self._coach_button.setEnabled(enabled)

    def _update_warning_banner(self) -> None:
        """Render the current startup status into the banner."""
        if self._validation_state == "pending":
            self._warning_title.setText("Checking system readiness")
            self._warning_body.setText(
                "Running startup validation in the background so the launcher can appear immediately."
            )
            self._warning_frame.setProperty("notice", "info")
            self._style_manager.polish(self._warning_frame)
            self._warning_frame.show()
            return

        messages = self._startup_errors or self._startup_warnings
        if not messages:
            self._warning_frame.hide()
            return

        if self._startup_errors:
            self._warning_title.setText("Startup issues")
            self._warning_frame.setProperty("notice", "error")
        else:
            self._warning_title.setText("Startup warnings")
            self._warning_frame.setProperty("notice", "warning")

        self._style_manager.polish(self._warning_frame)
        self._warning_body.setText("\n".join(f"- {message}" for message in messages))
        self._warning_frame.show()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        """Bring the launcher to the foreground when it is first shown."""
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

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
                f"Failed to launch Setup Wizard:\n{str(e)}\n\n" "Make sure all dependencies are installed.",
            )
            self.show()

    def _launch_stereo_setup(self):
        """Launch the canonical stereo setup wizard."""
        try:
            # Import here to avoid circular imports
            from ui.setup.launcher_integration import launch_stereo_setup_window

            self.stereo_setup_window = launch_stereo_setup_window(self, self._on_child_closed)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Launch Error",
                f"Failed to launch Stereo Setup:\n{str(e)}\n\n" "Make sure all dependencies are installed.",
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
        # Install any update that was downloaded while a workflow was active.
        self._update_controller.install_pending_update()

    def _show_about(self):
        """Show about dialog."""
        dialog = AboutDialog(self)
        dialog.exec()


def main():
    """Main entry point."""
    # Create required directories first
    create_required_directories()

    # Create QApplication (needed for dialogs)
    app = QtWidgets.QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")
    get_style_manager().apply_to_app(app)

    # Set application metadata
    app.setApplicationName("PitchTracker")
    app.setApplicationVersion(get_current_version())
    app.setOrganizationName("PitchTracker")

    # Create and show launcher
    launcher = LauncherWindow()
    launcher.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

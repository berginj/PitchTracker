"""Setup wizard window for system configuration and calibration."""

from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from log_config.logger import get_logger
from ui.setup.steps import (
    BaseStep,
    CameraStep,
    CalibrationStep,
    DetectorStep,
    ExportStep,
    RoiStep,
    ValidationStep,
)
from ui.themes import (
    GlassButton,
    apply_standard_layout,
    ask_confirmation,
    get_style_manager,
    show_message_dialog,
    style_message_panel,
)

logger = get_logger(__name__)


class SetupWindow(QtWidgets.QMainWindow):
    """Setup wizard for PitchTracker system configuration.

    Guides user through:
    1. Camera discovery and selection
    2. Stereo calibration
    3. ROI configuration
    4. Detector tuning
    5. System validation
    6. Export calibration package
    """

    def __init__(self, backend: str = "uvc", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("PitchTracker Setup & Calibration")
        self.resize(1200, 800)

        # Switch to setup mode for bolder glass styling
        self._style_manager = get_style_manager()
        self._style_manager.set_mode("setup")

        self._backend = backend
        self._current_step_index = 0
        self._steps: List[BaseStep] = []

        # Initialize steps
        self._init_steps()

        # Build UI
        self._build_ui()

        # Show first step
        self._show_step(0)

    def _init_steps(self) -> None:
        """Initialize all wizard steps."""
        # Step 1: Camera Setup
        self._steps.append(CameraStep(self._backend))

        # Step 2: Stereo Calibration
        self._steps.append(CalibrationStep(self._backend))

        # Step 3: ROI Configuration
        self._steps.append(RoiStep(self._backend))

        # Step 4: Detector Tuning
        self._steps.append(DetectorStep())

        # Step 5: System Validation
        self._steps.append(ValidationStep())

        # Step 6: Export Package
        self._steps.append(ExportStep())

    def _build_ui(self) -> None:
        """Build wizard UI with step indicator, content area, and navigation."""
        header = self._build_header()

        # Step indicator at top
        self._step_indicator = self._build_step_indicator()

        # Content area (will show current step widget)
        self._content_stack = QtWidgets.QStackedWidget()
        for step in self._steps:
            self._content_stack.addWidget(step)

        # Navigation buttons at bottom
        self._nav_layout = self._build_navigation()

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addWidget(header)
        layout.addWidget(self._step_indicator)
        layout.addWidget(self._content_stack, 1)  # Content takes most space
        layout.addLayout(self._nav_layout)

        container = QtWidgets.QWidget()
        container.setObjectName("WizardShell")
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _build_header(self) -> QtWidgets.QWidget:
        """Build wizard header with title and context."""
        header = QtWidgets.QFrame()
        self._style_manager.style_panel(header, "normal")

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(24, 22, 24, 22)

        eyebrow = QtWidgets.QLabel("System setup")
        self._style_manager.style_label(eyebrow, "eyebrow")
        layout.addWidget(eyebrow)

        title = QtWidgets.QLabel("Configure the rig end to end")
        self._style_manager.style_label(title, "pageTitle")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Move through each step once, keep calibration quality high, and export a clean package when the system is ready."
        )
        subtitle.setWordWrap(True)
        self._style_manager.style_label(subtitle, "muted")
        layout.addWidget(subtitle)

        header.setLayout(layout)
        return header

    def _build_step_indicator(self) -> QtWidgets.QWidget:
        """Build step indicator bar showing progress."""
        step_names = [
            "1. Cameras",
            "2. Calibration",
            "3. ROI",
            "4. Detector",
            "5. Validate",
            "6. Export",
        ]

        indicator_layout = QtWidgets.QHBoxLayout()
        indicator_layout.setContentsMargins(0, 0, 0, 0)

        self._step_labels: List[QtWidgets.QLabel] = []
        for i, name in enumerate(step_names):
            label = QtWidgets.QLabel(name)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(40)

            # Apply glass theme styles
            self._apply_step_style(label, i, i == 0)

            self._step_labels.append(label)
            indicator_layout.addWidget(label)

        indicator_widget = QtWidgets.QWidget()
        indicator_widget.setProperty("surface", "toolbar")
        self._style_manager.polish(indicator_widget)
        indicator_widget.setLayout(indicator_layout)
        return indicator_widget

    def _apply_step_style(self, label: QtWidgets.QLabel, index: int, is_current: bool, is_complete: bool = False) -> None:
        """Apply glass-themed style to step indicator label."""
        label.setProperty("role", "panelMessage")
        if is_current:
            style_message_panel(label, "success")
        elif is_complete:
            style_message_panel(label, "info")
        else:
            style_message_panel(label, "neutral")
        font = label.font()
        font.setBold(is_current or is_complete)
        label.setFont(font)

    def _build_navigation(self) -> QtWidgets.QHBoxLayout:
        """Build navigation buttons."""
        self._back_button = GlassButton("< Back", variant="ghost")
        self._back_button.setMinimumWidth(100)
        self._back_button.clicked.connect(self._go_back)

        self._skip_button = GlassButton("Skip Step", variant="ghost")
        self._skip_button.setMinimumWidth(100)
        self._skip_button.clicked.connect(self._skip_step)

        self._next_button = GlassButton("Next >", variant="primary")
        self._next_button.setMinimumWidth(100)
        self._next_button.clicked.connect(self._go_next)
        self._next_button.setDefault(True)

        self._finish_button = GlassButton("Finish", variant="success")
        self._finish_button.setMinimumWidth(100)
        self._finish_button.clicked.connect(self._finish_wizard)
        self._finish_button.hide()

        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.addWidget(self._back_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self._skip_button)
        nav_layout.addWidget(self._next_button)
        nav_layout.addWidget(self._finish_button)

        return nav_layout

    def _update_step_indicator(self) -> None:
        """Update step indicator to show current step."""
        for i, label in enumerate(self._step_labels):
            is_current = i == self._current_step_index
            is_complete = i < len(self._steps) and self._steps[i].is_complete()
            self._apply_step_style(label, i, is_current, is_complete)

    def _update_navigation_buttons(self) -> None:
        """Update button states based on current step."""
        # Back button
        self._back_button.setEnabled(self._current_step_index > 0)

        # Skip button
        current_step = self._steps[self._current_step_index]
        self._skip_button.setVisible(current_step.is_optional())

        # Next/Finish buttons
        is_last_step = self._current_step_index >= len(self._steps) - 1
        self._next_button.setVisible(not is_last_step)
        self._finish_button.setVisible(is_last_step)

    def _show_step(self, index: int) -> None:
        """Show step at given index."""
        if index < 0 or index >= len(self._steps):
            return

        # Exit current step
        if 0 <= self._current_step_index < len(self._steps):
            self._steps[self._current_step_index].on_exit()

        # Update index
        self._current_step_index = index

        # Show new step
        self._content_stack.setCurrentIndex(index)
        current_step = self._steps[index]

        # Special handling for certain steps
        if index == 1 and isinstance(current_step, CalibrationStep):
            # Pass camera serials and backend from Step 1 to Step 2
            camera_step = self._steps[0]
            if isinstance(camera_step, CameraStep):
                left_serial = camera_step.get_left_serial()
                right_serial = camera_step.get_right_serial()
                backend = camera_step.get_backend()
                logger.debug(
                    "Transitioning to calibration step with left_serial={!r}, right_serial={!r}, backend={!r}",
                    left_serial,
                    right_serial,
                    backend,
                )
                if left_serial and right_serial:
                    current_step.set_camera_serials(left_serial, right_serial)
                    current_step._backend = backend  # Update backend
                    logger.debug("Camera serials passed to calibration step")
                else:
                    logger.warning(
                        "Cannot enter calibration step without both camera serials. left_serial={!r}, right_serial={!r}",
                        left_serial,
                        right_serial,
                    )
                    show_message_dialog(
                        self,
                        "Cameras Not Selected",
                        "Please select both left and right cameras in Step 1 before proceeding to calibration.\n\n"
                        f"Left camera: {'✓ Selected' if left_serial else '✗ Not selected'}\n"
                        f"Right camera: {'✓ Selected' if right_serial else '✗ Not selected'}"
                    )

        elif index == 2 and isinstance(current_step, RoiStep):
            # Pass left camera serial and backend from Step 1 to Step 3
            camera_step = self._steps[0]
            if isinstance(camera_step, CameraStep):
                left_serial = camera_step.get_left_serial()
                backend = camera_step.get_backend()
                if left_serial:
                    current_step.set_camera_serial(left_serial)
                    current_step._backend = backend  # Update backend

        current_step.on_enter()

        # Update UI
        self._update_step_indicator()
        self._update_navigation_buttons()

        # Update window title with step info
        self.setWindowTitle(f"PitchTracker Setup - {current_step.get_title()}")

    def _go_back(self) -> None:
        """Go to previous step."""
        if self._current_step_index > 0:
            self._show_step(self._current_step_index - 1)

    def _go_next(self) -> None:
        """Go to next step (with validation)."""
        current_step = self._steps[self._current_step_index]

        # Validate current step
        is_valid, error_msg = current_step.validate()
        if not is_valid:
            show_message_dialog(
                self,
                "Validation Error",
                f"Cannot proceed to next step:\n\n{error_msg}",
                tone="warning",
            )
            return

        # Mark as complete
        current_step.set_complete(True)

        # Go to next step
        if self._current_step_index < len(self._steps) - 1:
            self._show_step(self._current_step_index + 1)

    def _skip_step(self) -> None:
        """Skip current step (if optional)."""
        current_step = self._steps[self._current_step_index]

        if not current_step.is_optional():
            return

        # Confirm skip
        if ask_confirmation(
            self,
            "Skip Step",
            f"Are you sure you want to skip '{current_step.get_title()}'?\n\n"
            "You can return to this step later if needed.",
        ):
            # Go to next step without marking as complete
            if self._current_step_index < len(self._steps) - 1:
                self._show_step(self._current_step_index + 1)

    def _finish_wizard(self) -> None:
        """Complete wizard and close window."""
        current_step = self._steps[self._current_step_index]

        # Validate final step
        is_valid, error_msg = current_step.validate()
        if not is_valid:
            show_message_dialog(
                self,
                "Validation Error",
                f"Cannot finish setup:\n\n{error_msg}",
                tone="warning",
            )
            return

        # Mark as complete
        current_step.set_complete(True)

        # Show completion message
        show_message_dialog(
            self,
            "Setup Complete",
            "System setup and calibration complete!\n\n"
            "Calibration package has been exported and the system is ready for coaching sessions.",
            tone="success",
        )

        # Close window
        self.close()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle window close - switch back to production mode."""
        # Reset to production mode for main application
        self._style_manager.set_mode("production")
        super().closeEvent(event)

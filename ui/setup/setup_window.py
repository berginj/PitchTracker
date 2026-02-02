"""Setup wizard window for system configuration and calibration."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.setup.steps import (
    BaseStep,
    CameraStep,
    CalibrationStep,
    DetectorStep,
    ExportStep,
    RoiStep,
    ValidationStep,
)


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
        layout.addWidget(self._step_indicator)
        layout.addWidget(self._content_stack, 1)  # Content takes most space
        layout.addLayout(self._nav_layout)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

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

        self._step_labels: List[QtWidgets.QLabel] = []
        for i, name in enumerate(step_names):
            label = QtWidgets.QLabel(name)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Plain)
            label.setMinimumHeight(40)

            # Style current step
            if i == 0:
                label.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            else:
                label.setStyleSheet("background-color: #f0f0f0; color: #666;")

            self._step_labels.append(label)
            indicator_layout.addWidget(label)

        indicator_widget = QtWidgets.QWidget()
        indicator_widget.setLayout(indicator_layout)
        return indicator_widget

    def _build_navigation(self) -> QtWidgets.QHBoxLayout:
        """Build navigation buttons."""
        self._back_button = QtWidgets.QPushButton("< Back")
        self._back_button.setMinimumWidth(100)
        self._back_button.clicked.connect(self._go_back)

        self._skip_button = QtWidgets.QPushButton("Skip Step")
        self._skip_button.setMinimumWidth(100)
        self._skip_button.clicked.connect(self._skip_step)

        self._next_button = QtWidgets.QPushButton("Next >")
        self._next_button.setMinimumWidth(100)
        self._next_button.clicked.connect(self._go_next)
        self._next_button.setDefault(True)

        self._finish_button = QtWidgets.QPushButton("Finish")
        self._finish_button.setMinimumWidth(100)
        self._finish_button.clicked.connect(self._finish_wizard)
        self._finish_button.hide()

        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.addWidget(self._back_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self._skip_button)
        nav_layout.addWidget(self._next_button)
        nav_layout.addWidget(self._finish_button)

        return nav_layout

    def _update_step_indicator(self) -> None:
        """Update step indicator to show current step."""
        for i, label in enumerate(self._step_labels):
            if i == self._current_step_index:
                # Current step - green
                label.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            elif i < len(self._steps) and self._steps[i].is_complete():
                # Completed step - blue
                label.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
            else:
                # Future step - gray
                label.setStyleSheet("background-color: #f0f0f0; color: #666;")

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
                print(f"[SetupWizard] Transitioning to Calibration Step:")
                print(f"  Left Serial: {left_serial}")
                print(f"  Right Serial: {right_serial}")
                print(f"  Backend: {backend}")
                if left_serial and right_serial:
                    current_step.set_camera_serials(left_serial, right_serial)
                    current_step._backend = backend  # Update backend
                    print(f"[SetupWizard] Camera serials passed to calibration step")
                else:
                    print(f"[SetupWizard] ERROR: Camera serials not set! Left={left_serial}, Right={right_serial}")
                    QtWidgets.QMessageBox.warning(
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
            QtWidgets.QMessageBox.warning(
                self,
                "Validation Error",
                f"Cannot proceed to next step:\n\n{error_msg}",
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
        reply = QtWidgets.QMessageBox.question(
            self,
            "Skip Step",
            f"Are you sure you want to skip '{current_step.get_title()}'?\n\n"
            "You can return to this step later if needed.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Go to next step without marking as complete
            if self._current_step_index < len(self._steps) - 1:
                self._show_step(self._current_step_index + 1)

    def _finish_wizard(self) -> None:
        """Complete wizard and close window."""
        current_step = self._steps[self._current_step_index]

        # Validate final step
        is_valid, error_msg = current_step.validate()
        if not is_valid:
            QtWidgets.QMessageBox.warning(
                self,
                "Validation Error",
                f"Cannot finish setup:\n\n{error_msg}",
            )
            return

        # Mark as complete
        current_step.set_complete(True)

        # Show completion message
        QtWidgets.QMessageBox.information(
            self,
            "Setup Complete",
            "System setup and calibration complete!\n\n"
            "Calibration package has been exported and the system is ready for coaching sessions.",
        )

        # Close window
        self.close()

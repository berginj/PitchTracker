"""Setup wizard window for system configuration and calibration."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from log_config.logger import get_logger
from ui.setup.state_machine import SetupStateMachine
from ui.setup.steps import (
    BaseStep,
    CameraStep,
    CalibrationStep,
    DetectorStep,
    ExportStep,
    QualityReportStep,
    RoiStep,
    ValidationStep,
)
from ui.setup.wizard_spec import (
    WIZARD_STEP_ORDER,
    WizardStep,
    build_wizard_spec,
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
    7. Calibration quality report
    """

    def __init__(self, backend: str = "uvc", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("PitchTracker Setup & Calibration")
        self.resize(1200, 800)

        # Switch to setup mode for bolder glass styling
        self._style_manager = get_style_manager()
        self._style_manager.set_mode("setup")

        self._backend = backend
        self._steps: List[BaseStep] = []
        self._widget_by_step: Dict[WizardStep, BaseStep] = {}

        # Build the ordered step widgets, then drive navigation through the
        # tested, Qt-free SetupStateMachine engine instead of an ad-hoc index.
        self._init_steps()
        optional = tuple(step for step in WIZARD_STEP_ORDER if self._widget_by_step[step].is_optional())
        self._machine: SetupStateMachine[WizardStep] = SetupStateMachine(
            build_wizard_spec(optional=optional)
        )

        # Build UI
        self._build_ui()

        # Show first step
        self._show_current()

    def _init_steps(self) -> None:
        """Initialize all wizard steps in canonical order."""
        widgets: Dict[WizardStep, BaseStep] = {
            WizardStep.CAMERAS: CameraStep(self._backend),
            WizardStep.CALIBRATION: CalibrationStep(self._backend),
            WizardStep.ROI: RoiStep(self._backend),
            WizardStep.DETECTOR: DetectorStep(),
            WizardStep.VALIDATION: ValidationStep(),
            WizardStep.EXPORT: ExportStep(),
            WizardStep.QUALITY_REPORT: QualityReportStep(),
        }
        self._widget_by_step = widgets
        self._steps = [widgets[step] for step in WIZARD_STEP_ORDER]

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
        step_names = [self._machine.title_for(step) for step in self._machine.steps]

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

    def _apply_step_style(
        self, label: QtWidgets.QLabel, index: int, is_current: bool, is_complete: bool = False
    ) -> None:
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

    def _current_step(self) -> WizardStep:
        """The machine's current wizard step."""
        return self._machine.current

    def _current_widget(self) -> BaseStep:
        """The widget for the machine's current step."""
        return self._widget_by_step[self._machine.current]

    def _update_step_indicator(self) -> None:
        """Update step indicator to show current step."""
        current = self._machine.current
        for i, label in enumerate(self._step_labels):
            step = self._machine.steps[i]
            is_current = step == current
            is_complete = self._widget_by_step[step].is_complete()
            self._apply_step_style(label, i, is_current, is_complete)

    def _update_navigation_buttons(self) -> None:
        """Update button states based on current step."""
        # Back button
        self._back_button.setEnabled(self._machine.can_go_back())

        # Skip button (only for optional steps that may be skipped)
        self._skip_button.setVisible(self._machine.can_skip())

        # Next/Finish buttons
        is_last_step = self._machine.current_index >= len(self._machine.steps) - 1
        self._next_button.setVisible(not is_last_step)
        self._finish_button.setVisible(is_last_step)

    def _show_current(self) -> None:
        """Render the machine's current step."""
        index = self._machine.current_index
        current_step = self._machine.current
        current_widget = self._widget_by_step[current_step]

        # Show new step
        self._content_stack.setCurrentIndex(index)

        # Pass camera context forward to steps that need it.
        self._propagate_camera_context(current_step, current_widget)

        current_widget.on_enter()

        # Update UI
        self._update_step_indicator()
        self._update_navigation_buttons()

        # Update window title with step info
        self.setWindowTitle(f"PitchTracker Setup - {current_widget.get_title()}")

    def _propagate_camera_context(self, step: WizardStep, widget: BaseStep) -> None:
        """Hand camera serials/backend from the camera step to dependents."""
        camera_widget = self._widget_by_step[WizardStep.CAMERAS]
        if not isinstance(camera_widget, CameraStep):
            return

        if step == WizardStep.CALIBRATION and isinstance(widget, CalibrationStep):
            left_serial = camera_widget.get_left_serial()
            right_serial = camera_widget.get_right_serial()
            backend = camera_widget.get_backend()
            logger.debug(
                "Transitioning to calibration step with left_serial={!r}, right_serial={!r}, backend={!r}",
                left_serial,
                right_serial,
                backend,
            )
            if left_serial and right_serial:
                widget.set_camera_serials(left_serial, right_serial)
                widget._backend = backend
                logger.debug("Camera serials passed to calibration step")
            else:
                logger.warning(
                    "Cannot enter calibration step without both camera serials. " "left_serial={!r}, right_serial={!r}",
                    left_serial,
                    right_serial,
                )
                show_message_dialog(
                    self,
                    "Cameras Not Selected",
                    "Please select both left and right cameras in Step 1 before proceeding to calibration.\n\n"
                    f"Left camera: {'Selected' if left_serial else 'Not selected'}\n"
                    f"Right camera: {'Selected' if right_serial else 'Not selected'}",
                )
        elif step == WizardStep.ROI and isinstance(widget, RoiStep):
            left_serial = camera_widget.get_left_serial()
            backend = camera_widget.get_backend()
            if left_serial:
                widget.set_camera_serial(left_serial)
                widget._backend = backend

    def _go_back(self) -> None:
        """Go to previous step."""
        if not self._machine.can_go_back():
            return
        self._current_widget().on_exit()
        self._machine.go_back()
        self._show_current()

    def _go_next(self) -> None:
        """Go to next step (with validation)."""
        current_widget = self._current_widget()

        # Validate current step
        is_valid, error_msg = current_widget.validate()
        if not is_valid:
            show_message_dialog(
                self,
                "Validation Error",
                f"Cannot proceed to next step:\n\n{error_msg}",
                tone="warning",
            )
            return

        # Mark as complete in both the widget and the state machine.
        current_widget.set_complete(True)
        self._machine.mark_complete(self._machine.current, True)

        if not self._machine.can_advance():
            return
        current_widget.on_exit()
        self._machine.advance()
        self._show_current()

    def _skip_step(self) -> None:
        """Skip current step (if optional)."""
        if not self._machine.can_skip():
            return

        current_widget = self._current_widget()
        if ask_confirmation(
            self,
            "Skip Step",
            f"Are you sure you want to skip '{current_widget.get_title()}'?\n\n"
            "You can return to this step later if needed.",
        ):
            current_widget.on_exit()
            self._machine.skip()
            self._show_current()

    def _finish_wizard(self) -> None:
        """Complete wizard and close window."""
        current_widget = self._current_widget()

        # Validate final step
        is_valid, error_msg = current_widget.validate()
        if not is_valid:
            show_message_dialog(
                self,
                "Validation Error",
                f"Cannot finish setup:\n\n{error_msg}",
                tone="warning",
            )
            return

        # Mark as complete
        current_widget.set_complete(True)
        self._machine.mark_complete(self._machine.current, True)

        if not self._machine.can_finish():
            missing = ", ".join(self._machine.title_for(s) for s in self._machine.missing_required())
            show_message_dialog(
                self,
                "Setup Incomplete",
                f"Complete the remaining required steps before finishing:\n\n{missing}",
                tone="warning",
            )
            return

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

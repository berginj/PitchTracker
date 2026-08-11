"""Stereo setup wizard window for the canonical evidence-gated setup flow."""

from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.setup.state_machine import DEFAULT_SETUP_SPEC, SetupStateMachine, SetupStep
from ui.setup.steps.base_step import BaseStep
from ui.setup.stereo_steps import build_stereo_step_widgets
from ui.themes import (
    GlassButton,
    apply_standard_layout,
    ask_confirmation,
    get_style_manager,
    show_message_dialog,
    style_message_panel,
)


class StereoSetupWindow(QtWidgets.QMainWindow):
    """Window hosting the genuine stereo setup wizard on SetupStateMachine."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        widget_factory: Optional[Callable[[], Dict[SetupStep, BaseStep]]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("PitchTracker Stereo Setup")
        self.resize(1200, 800)

        self._style_manager = get_style_manager()
        self._style_manager.set_mode("setup")

        factory = widget_factory or build_stereo_step_widgets
        self._widget_by_step: Dict[SetupStep, BaseStep] = factory()
        self._machine = SetupStateMachine(DEFAULT_SETUP_SPEC)
        self._steps = [self._widget_by_step[spec.step] for spec in DEFAULT_SETUP_SPEC]
        self._closing_after_capture_cancel = False
        self._capture_close_deadline = 0.0
        for step in self._steps:
            step.busy_changed.connect(self._on_step_busy_changed)

        self._build_ui()
        self._show_current()

    def _build_ui(self) -> None:
        """Build the wizard shell."""
        header = self._build_header()
        self._step_indicator = self._build_step_indicator()

        self._content_stack = QtWidgets.QStackedWidget()
        self._content_stack.setMinimumSize(0, 0)
        for step in self._steps:
            self._content_stack.addWidget(step)

        self._content_scroll = QtWidgets.QScrollArea()
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._content_scroll.setSizeAdjustPolicy(
            QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        self._content_scroll.setMinimumSize(0, 0)
        self._content_scroll.setWidget(self._content_stack)

        self._nav_layout = self._build_navigation()

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addWidget(header)
        layout.addWidget(self._step_indicator)
        layout.addWidget(self._content_scroll, 1)
        layout.addLayout(self._nav_layout)

        container = QtWidgets.QWidget()
        container.setObjectName("StereoWizardShell")
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _build_header(self) -> QtWidgets.QWidget:
        """Build the stereo setup header."""
        header = QtWidgets.QFrame()
        self._style_manager.style_panel(header, "normal")

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(24, 22, 24, 22)

        eyebrow = QtWidgets.QLabel("Stereo setup")
        self._style_manager.style_label(eyebrow, "eyebrow")
        layout.addWidget(eyebrow)

        title = QtWidgets.QLabel("Configure the stereo rig end to end")
        self._style_manager.style_label(title, "pageTitle")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Verify camera pairing, synchronization, optical alignment, field coordinates, "
            "artifact persistence, and final calibration quality."
        )
        subtitle.setWordWrap(True)
        self._style_manager.style_label(subtitle, "muted")
        layout.addWidget(subtitle)

        header.setLayout(layout)
        return header

    def _build_step_indicator(self) -> QtWidgets.QWidget:
        """Build the horizontal step indicator."""
        indicator_layout = QtWidgets.QHBoxLayout()
        indicator_layout.setContentsMargins(0, 0, 0, 0)

        self._step_labels: List[QtWidgets.QLabel] = []
        for index, step in enumerate(self._machine.steps):
            label = QtWidgets.QLabel(self._machine.title_for(step))
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(40)
            self._apply_step_style(label, index == 0)
            self._step_labels.append(label)
            indicator_layout.addWidget(label)

        indicator_widget = QtWidgets.QWidget()
        indicator_widget.setProperty("surface", "toolbar")
        self._style_manager.polish(indicator_widget)
        indicator_widget.setLayout(indicator_layout)
        return indicator_widget

    def _apply_step_style(
        self,
        label: QtWidgets.QLabel,
        is_current: bool,
        is_complete: bool = False,
    ) -> None:
        """Apply themed styling to a step indicator label."""
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
        """Build wizard navigation buttons."""
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

    def _current_widget(self) -> BaseStep:
        """Return the widget for the machine's current step."""
        return self._widget_by_step[self._machine.current]

    def _show_current(self) -> None:
        """Render the machine's current step."""
        current_widget = self._current_widget()
        self._content_stack.setCurrentIndex(self._machine.current_index)
        current_widget.on_enter()
        self._update_step_indicator()
        self._update_navigation_buttons()
        self.setWindowTitle(f"PitchTracker Stereo Setup - {current_widget.get_title()}")

    def _update_step_indicator(self) -> None:
        """Update the step indicator to reflect current progress."""
        current = self._machine.current
        for index, label in enumerate(self._step_labels):
            step = self._machine.steps[index]
            is_current = step == current
            is_complete = self._widget_by_step[step].is_complete()
            self._apply_step_style(label, is_current, is_complete)

    def _update_navigation_buttons(self) -> None:
        """Update navigation button states for the current step."""
        busy = self._current_widget().is_busy()
        self._back_button.setEnabled(self._machine.can_go_back() and not busy)
        self._skip_button.setVisible(self._machine.can_skip())
        self._skip_button.setEnabled(not busy)

        is_last_step = self._machine.current_index >= len(self._machine.steps) - 1
        self._next_button.setVisible(not is_last_step)
        self._finish_button.setVisible(is_last_step)
        self._next_button.setEnabled(not busy)
        self._finish_button.setEnabled(not busy)

    def _on_step_busy_changed(self, _busy: bool) -> None:
        self._update_navigation_buttons()
        if self._closing_after_capture_cancel and not any(step.is_busy() for step in self._steps):
            QtCore.QTimer.singleShot(0, self.close)

    def _go_back(self) -> None:
        """Go to the previous step."""
        if self._current_widget().is_busy() or not self._machine.can_go_back():
            return
        self._current_widget().on_exit()
        self._machine.go_back()
        self._show_current()

    def _go_next(self) -> None:
        """Validate and advance to the next step."""
        current_widget = self._current_widget()
        if current_widget.is_busy():
            return
        is_valid, error_msg = current_widget.validate()
        if not is_valid:
            show_message_dialog(
                self,
                "Validation Error",
                f"Cannot proceed to next step:\n\n{error_msg}",
                tone="warning",
            )
            return

        current_widget.set_complete(True)
        self._machine.mark_complete(self._machine.current, True)

        if not self._machine.can_advance():
            return
        current_widget.on_exit()
        self._machine.advance()
        self._show_current()

    def _skip_step(self) -> None:
        """Skip the current step if the machine allows it."""
        if self._current_widget().is_busy() or not self._machine.can_skip():
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
        """Complete the stereo setup wizard and close the window."""
        current_widget = self._current_widget()
        if current_widget.is_busy():
            return
        is_valid, error_msg = current_widget.validate()
        if not is_valid:
            show_message_dialog(
                self,
                "Validation Error",
                f"Cannot finish setup:\n\n{error_msg}",
                tone="warning",
            )
            return

        current_widget.set_complete(True)
        self._machine.mark_complete(self._machine.current, True)

        if not self._machine.can_finish():
            missing = ", ".join(self._machine.title_for(step) for step in self._machine.missing_required())
            show_message_dialog(
                self,
                "Setup Incomplete",
                f"Complete the remaining required steps before finishing:\n\n{missing}",
                tone="warning",
            )
            return

        show_message_dialog(
            self,
            "Stereo Setup Complete",
            "Stereo setup is complete and the rig is ready for coaching sessions.",
            tone="success",
        )
        self.close()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Cancel and reap setup camera workers before hiding the wizard."""
        busy_steps = [step for step in self._steps if step.is_busy()]
        if busy_steps:
            now = time.monotonic()
            if not self._closing_after_capture_cancel:
                self._closing_after_capture_cancel = True
                self._capture_close_deadline = now + 2.0
                for step in busy_steps:
                    step.cancel_pending()
            elif now >= self._capture_close_deadline:
                for step in busy_steps:
                    step.force_cancel_pending()
                # Give the monitor one final Qt turn to publish terminal state.
                if now < self._capture_close_deadline + 0.5:
                    event.ignore()
                    QtCore.QTimer.singleShot(50, self.close)
                    return
            else:
                for step in busy_steps:
                    step.cancel_pending()
            if now < self._capture_close_deadline + 0.5:
                event.ignore()
                QtCore.QTimer.singleShot(50, self.close)
                return
        self._style_manager.set_mode("production")
        super().closeEvent(event)

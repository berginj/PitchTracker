"""Stereo setup wizard window for the canonical evidence-gated setup flow."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.setup.state_machine import GUIDED_SETUP_SPEC, SetupStateMachine, StepSpec
from ui.setup.steps.base_step import BaseStep
from ui.themes import (
    GlassButton,
    ask_confirmation,
    get_style_manager,
    show_message_dialog,
)
from ui.setup.instrument_style import instrument_stylesheet
from ui.setup.instrument_widgets import StageStack


class StereoSetupWindow(QtWidgets.QMainWindow):
    """Window hosting the genuine stereo setup wizard on SetupStateMachine."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        widget_factory: Optional[Callable[[], Dict[Any, BaseStep]]] = None,
        specs: tuple[StepSpec[Any], ...] = GUIDED_SETUP_SPEC,
        config_path: Path | None = None,
        backend: str = "uvc",
        workflow=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("PitchTracker Stereo Setup")
        self.setMinimumSize(640, 480)
        self.resize(1200, 800)

        self._style_manager = get_style_manager()
        self._style_manager.set_mode("setup")

        if widget_factory is None:
            from app.services.catalog.service import CameraCatalogService
            from app.services.setup_workflow import SetupWorkflowService
            from ui.setup.guided_steps import build_guided_setup_widgets
            workflow = workflow or SetupWorkflowService(
                config_path=config_path or Path("configs/default.yaml"), backend=backend,
            )
            catalog = CameraCatalogService()

            def widget_factory():
                return build_guided_setup_widgets(workflow, catalog)
        self.workflow = workflow
        self._widget_by_step: Dict[Any, BaseStep] = widget_factory()
        self._machine: SetupStateMachine[Any] = SetupStateMachine(specs)
        self._steps = [self._widget_by_step[spec.step] for spec in specs]
        self._closing_after_capture_cancel = False
        self._capture_close_deadline = 0.0
        for step in self._steps:
            step.busy_changed.connect(self._on_step_busy_changed)
            if hasattr(step, "configuration_changed"):
                step.configuration_changed.connect(self._invalidate_progress)

        self._build_ui()
        self._show_current()

    def _build_ui(self) -> None:
        """Build the wizard shell."""
        header = self._build_header()
        self._step_indicator = self._build_step_indicator()

        self._content_stack = StageStack()
        self._content_stack.setObjectName("SetupStageStack")
        self._content_stack.setMinimumSize(0, 0)
        for step in self._steps:
            self._content_stack.addWidget(step)

        self._content_scroll = QtWidgets.QScrollArea()
        self._content_scroll.setObjectName("SetupScroll")
        self._content_scroll.viewport().setObjectName("SetupViewport")
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._content_scroll.setSizeAdjustPolicy(
            QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        self._content_scroll.setMinimumSize(0, 0)
        self._content_scroll.setWidget(self._content_stack)

        self._nav_layout = self._build_navigation()

        self._body_layout = QtWidgets.QHBoxLayout()
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        self._body_layout.addWidget(self._step_indicator)
        content_layout = QtWidgets.QVBoxLayout()
        content_layout.setContentsMargins(24, 22, 24, 18)
        content_layout.setSpacing(16)
        content_layout.addWidget(self._content_scroll, 1)
        content_layout.addLayout(self._nav_layout)
        self._body_layout.addLayout(content_layout, 1)
        container = QtWidgets.QWidget()
        container.setObjectName("StereoWizardShell")
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addLayout(self._body_layout, 1)
        self.setCentralWidget(container)
        self._apply_appearance()
        self._resize_rail()

    def _build_header(self) -> QtWidgets.QWidget:
        """Build the stereo setup header."""
        header = QtWidgets.QFrame()
        header.setObjectName("SetupChrome")
        layout = QtWidgets.QHBoxLayout(header)
        layout.setContentsMargins(24, 16, 24, 16)
        title = QtWidgets.QLabel("PitchTracker")
        title.setObjectName("SetupBrand")
        layout.addWidget(title)
        context = QtWidgets.QLabel("RIG SETUP")
        context.setObjectName("SetupContext")
        layout.addWidget(context)
        layout.addStretch()
        self._appearance = QtWidgets.QComboBox()
        self._appearance.setAccessibleName("Setup appearance")
        self._appearance.addItem("Light appearance", False)
        self._appearance.addItem("Dark appearance", True)
        self._appearance.currentIndexChanged.connect(self._apply_appearance)
        layout.addWidget(self._appearance)
        return header

    def _apply_appearance(self) -> None:
        self.setStyleSheet(instrument_stylesheet(dark=bool(self._appearance.currentData())))

    def _build_step_indicator(self) -> QtWidgets.QWidget:
        """Build the persistent stage rail; it does not bypass validation."""
        indicator_widget = QtWidgets.QWidget()
        indicator_widget.setObjectName("SetupRail")
        indicator_widget.setFixedWidth(174)
        indicator_layout = QtWidgets.QVBoxLayout(indicator_widget)
        indicator_layout.setContentsMargins(12, 24, 12, 18)
        indicator_layout.setSpacing(8)
        self._rail_title = QtWidgets.QLabel("YOUR RIG")
        self._style_manager.style_label(self._rail_title, "eyebrow")
        indicator_layout.addWidget(self._rail_title)
        self._step_labels: List[QtWidgets.QLabel] = []
        for index, step in enumerate(self._machine.steps):
            label = QtWidgets.QLabel(self._machine.title_for(step))
            label.setWordWrap(True)
            label.setMinimumHeight(48)
            self._apply_step_style(label, index == 0)
            self._step_labels.append(label)
            indicator_layout.addWidget(label)
        indicator_layout.addStretch()
        self._rail_note = QtWidgets.QLabel("Research setup\nAccuracy approval is separate")
        self._rail_note.setWordWrap(True)
        self._style_manager.style_label(self._rail_note, "muted")
        indicator_layout.addWidget(self._rail_note)
        return indicator_widget

    def _apply_step_style(
        self,
        label: QtWidgets.QLabel,
        is_current: bool,
        is_complete: bool = False,
    ) -> None:
        """Apply themed styling to a step indicator label."""
        label.setProperty("role", "setupStage")
        label.setProperty("stepState", "current" if is_current else "complete" if is_complete else "pending")
        self._style_manager.polish(label)

    def _build_navigation(self) -> QtWidgets.QHBoxLayout:
        """Build wizard navigation buttons."""
        self._back_button = GlassButton("< Back", variant="ghost")
        self._back_button.setAccessibleName("Go to previous step")
        self._back_button.setMinimumWidth(100)
        self._back_button.clicked.connect(self._go_back)

        self._skip_button = GlassButton("Skip Step", variant="ghost")
        self._skip_button.setAccessibleName("Skip current step")
        self._skip_button.setMinimumWidth(100)
        self._skip_button.clicked.connect(self._skip_step)

        self._next_button = GlassButton("Check & continue >", variant="default")
        self._next_button.setAccessibleName("Go to next step")
        self._next_button.setMinimumWidth(100)
        self._next_button.clicked.connect(self._go_next)
        self._next_button.setDefault(True)

        self._finish_button = GlassButton("Finish", variant="success")
        self._finish_button.setAccessibleName("Finish setup wizard")
        self._finish_button.setMinimumWidth(100)
        self._finish_button.clicked.connect(self._finish_wizard)
        self._finish_button.hide()

        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.addWidget(self._back_button)
        nav_layout.addStretch()
        self._save_note = QtWidgets.QLabel("Changes save immediately")
        self._style_manager.style_label(self._save_note, "muted")
        nav_layout.addWidget(self._save_note)
        nav_layout.addWidget(self._skip_button)
        nav_layout.addWidget(self._next_button)
        nav_layout.addWidget(self._finish_button)
        return nav_layout

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_step_indicator"):
            self._resize_rail()

    def _resize_rail(self) -> None:
        compact = self.width() < 900
        self._step_indicator.setFixedWidth(64 if compact else 174)
        self._rail_title.setVisible(not compact)
        self._rail_note.setVisible(not compact)
        self._save_note.setVisible(not compact)
        for index, label in enumerate(self._step_labels):
            title = self._machine.title_for(self._machine.steps[index])
            label.setText(str(index + 1) if compact else f"{index + 1}  {title}")
            label.setToolTip(title)
            label.setAccessibleName(f"Step {index + 1}: {title}")
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter if compact else QtCore.Qt.AlignmentFlag.AlignVCenter)

    def _current_widget(self) -> BaseStep:
        """Return the widget for the machine's current step."""
        return self._widget_by_step[self._machine.current]

    def _invalidate_progress(self) -> None:
        for step in self._machine.steps:
            widget = self._widget_by_step[step]
            valid, _reason = widget.validate()
            if not valid:
                widget.set_complete(False)
                self._machine.mark_complete(step, False)
        self._update_step_indicator()

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

        try:
            current_widget.finish_setup()
        except Exception as exc:
            show_message_dialog(self, "Setup needs attention", str(exc), tone="warning")
            return

        show_message_dialog(
            self,
            "Stereo Setup Complete",
            "Setup is complete. The rig is ready for research recording with estimated measurements.",
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
            # A timeout triggers process cancellation; it does not establish
            # terminal state. Keep ownership until the monitor reports completion.
            event.ignore()
            QtCore.QTimer.singleShot(50, self.close)
            return
        for step in self._steps:
            step.on_exit()
        self._style_manager.set_mode("production")
        super().closeEvent(event)

"""Public hosting and command handoffs for the coaching facade."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from pathlib import Path

from PySide6 import QtWidgets

from app.services.orchestrator.runtime_status import RuntimeStatus
from ui.coaching.async_session import AsyncSessionController
from ui.coaching.session_commands import SessionOperation

if TYPE_CHECKING:
    from ui.coaching.coach_window import CoachWindow


class CoachingWorkspaceHost(QtWidgets.QMainWindow):
    def host_in_workspace(self, parent: QtWidgets.QWidget) -> None:
        from ui.workspace.hosting import embed_window

        h = cast("CoachWindow", self)
        h._workspace_hosted = True
        h._session_ctrl = AsyncSessionController(h)
        h.session_operation_changed.connect(h._refresh_session_controls)
        for button in (h._setup_button, h._start_recording_button, h._pause_button, h._end_button,
                       h._review_button, h._help_button):
            button.hide()  # The persistent shell owns essential session actions and help.
        h._status_label.hide()
        h._recording_indicator.hide()
        from ui.coaching.live_layout import configure_live_workspace
        configure_live_workspace(h)
        embed_window(h, parent, scroll_content=True)
        h.apply_runtime_status(h.pipeline_service.runtime_status())

    def session_operation(self) -> SessionOperation:
        h = cast("CoachWindow", self)
        if isinstance(h._session_ctrl, AsyncSessionController):
            return h._session_ctrl.operation()
        return SessionOperation()

    def recordings_directory(self) -> Path:
        return Path(cast("CoachWindow", self)._config.recording.output_dir)

    def session_command_busy(self) -> bool:
        h = cast("CoachWindow", self)
        return isinstance(h._session_ctrl, AsyncSessionController) and h._session_ctrl.busy()

    def begin_session_shutdown(self) -> bool:
        h = cast("CoachWindow", self)
        return not isinstance(h._session_ctrl, AsyncSessionController) or h._session_ctrl.begin_shutdown()

    def apply_runtime_status(self, status: RuntimeStatus) -> None:
        h = cast("CoachWindow", self)
        h._session_active = status.owns_recording
        h._session_paused = status.recording_phase != "recording"
        if status.pitcher.active_name is not None and status.pitcher.active_name != h._pitcher_name:
            h._pitcher_name = status.pitcher.active_name
            h._pitcher_label.setText(f"Pitcher: {h._pitcher_name}")
            h._fatigue_indicator.reset()
            h.notify_preparation_changed()
        h._refresh_session_controls()

    def request_pitcher(self, name: str) -> None:
        host = cast("CoachWindow", self)
        if isinstance(host._session_ctrl, AsyncSessionController):
            host._session_ctrl.request_pitcher(name)

    def _refresh_session_controls(self) -> None:
        h = cast("CoachWindow", self)
        status = h.pipeline_service.runtime_status()
        enabled = not h.session_command_busy() and not status.pending_operation
        h._switch_pitcher_btn.setEnabled(enabled and status.recording_phase != "finalizing")
        h._lane_button.setEnabled(enabled and not status.owns_recording and status.capture_phase == "live")
        h._settings_button.setEnabled(enabled and not status.owns_capture and not status.owns_recording)
        h._diagnostics_button.setEnabled(enabled)
        h._detector_trial_button.setEnabled(enabled)
        for action, button in getattr(h, "_advanced_actions", []):
            action.setEnabled(button.isEnabled())
            reason = "Wait for session operation" if not enabled else "Preview only" if button is h._lane_button else "Stop preview first"
            action.setText(str(action.data()) + (f" · {reason}" if not button.isEnabled() else ""))

    def polling_allowed(self) -> bool:
        h = cast("CoachWindow", self)
        return not h.session_command_busy() and not h.pipeline_service.runtime_status().pending_operation

    def perform_session_action(self, action: str) -> None:
        h = cast("CoachWindow", self)
        if isinstance(h._session_ctrl, AsyncSessionController):
            h._session_ctrl.perform(action)
            return
        if action == "prepare":
            h._setup_session()
        elif action == "record":
            h._start_recording()
        elif action in {"pause", "resume"}:
            h._pause_session()
        elif action == "end":
            h._end_session()
        elif action == "stop_preview":
            h._service.stop_capture()
            h._session_prepared = False
            h._setup_button.setEnabled(True)
            h._start_recording_button.setEnabled(False)
            h._end_button.setEnabled(False)
            h._set_status_message("Preview stopped. Prepare a session to begin again.")
        else:
            raise ValueError(f"Unsupported session action: {action}")

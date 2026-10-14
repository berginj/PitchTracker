"""Workspace session actions: dialogs on Qt, slow commands in a retained worker."""

from __future__ import annotations

from dataclasses import replace
import logging

from PySide6 import QtWidgets

from configs.app_state import load_state, save_state
from ui.coaching.session_commands import PrepareSession, SessionCommandResult, SessionCommandRunner, SessionOperation
from ui.coaching.session_controller import SessionController
from ui.themes import ask_confirmation

logger = logging.getLogger(__name__)


class AsyncSessionController(SessionController):
    def __init__(self, host):
        super().__init__(host)
        self.runner = SessionCommandRunner(host.pipeline_service, host)
        self.runner.changed.connect(host.session_operation_changed)
        self.runner.completed.connect(self._completed)
        self._dialog: QtWidgets.QDialog | None = None
        self._dialog_operation: str | None = None
        self._closing = False

    def operation(self) -> SessionOperation:
        if self._dialog_operation:
            return SessionOperation(pending=self._dialog_operation)
        return self.runner.state

    def busy(self) -> bool:
        return self.runner.busy or self._dialog_operation is not None

    def begin_shutdown(self) -> bool:
        self._closing = True
        self.runner.stop_admission()
        if self._dialog is not None:
            self._dialog.reject()
        elif self._dialog_operation:
            modal = QtWidgets.QApplication.activeModalWidget()
            if isinstance(modal, QtWidgets.QDialog) and modal.parentWidget() is self._host:
                modal.reject()
        return not self.busy()

    def _admitted(self) -> bool:
        return not self._closing and not self.busy() and not self._host.pipeline_service.runtime_status().pending_operation

    def _failure(self, operation: str, exc: Exception) -> None:
        logger.exception("Session UI action failed: %s", operation)
        self.runner.state = SessionOperation(failure_operation=operation, failure_message=str(exc))
        self._host.session_operation_changed.emit()

    def setup_session(self) -> None:
        if not self._admitted() or self._host.pipeline_service.runtime_status().owns_recording:
            return
        from ui.coaching.dialogs import SessionStartDialog

        h = self._host
        self._dialog_operation = "prepare_details"
        h.session_operation_changed.emit()
        try:
            h.refresh_preparation_config()
            dialog = SessionStartDialog(h._config, parent=h, backend=h._backend, config_path=h._config_path,
                                        prepare_only=True)
            self._dialog = dialog
            accepted = dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
            self._dialog = None
            if not accepted or self._closing:
                return
            config = replace(h._config, strike_zone=replace(h._config.strike_zone, batter_height_in=dialog.batter_height_in),
                             ball=replace(h._config.ball, type=dialog.ball_type),
                             camera=replace(h._config.camera, width=h._camera_width, height=h._camera_height,
                                            fps=h._camera_fps, color_mode=h._camera_color_mode))
            config, left, right = self._apply_active_rig_capture_settings(config, dialog.left_serial, dialog.right_serial)
            prepared = PrepareSession(config, h._config_path, left, right, dialog.session_name, dialog.pitcher_name)
            self.runner.submit("prepare", prepared)
        except Exception as exc:
            self._failure("prepare", exc)
        finally:
            self._dialog = None
            self._dialog_operation = None
            h.session_operation_changed.emit()

    def start_recording(self) -> None:
        if not self._admitted() or not self._host._session_prepared:
            return
        status = self._host.pipeline_service.runtime_status()
        if status.capture_phase == "live" and not status.owns_recording:
            self.runner.submit("record", session_name=self._host._session_name)

    def pause_session(self) -> None:
        status = self._host.pipeline_service.runtime_status()
        self.perform("resume" if status.recording_phase == "paused" else "pause")

    def end_session(self) -> None:
        self.perform("end")

    def perform(self, action: str) -> None:
        if action == "prepare":
            self.setup_session()
            return
        if action == "record":
            self.start_recording()
            return
        if not self._admitted():
            return
        status = self._host.pipeline_service.runtime_status()
        if action == "pause" and status.recording_phase != "recording":
            return
        if action == "resume" and status.recording_phase != "paused":
            return
        if action == "stop_preview" and (not status.owns_capture or status.owns_recording):
            return
        if action == "end":
            if not status.owns_recording:
                return
            self._dialog_operation = "confirm_end"
            self._host.session_operation_changed.emit()
            try:
                confirmed = ask_confirmation(
                    self._host, "End Session",
                    f"End '{status.session_id}' and save accepted pitches?\nCameras remain live after finalization.",
                    confirm_variant="danger")
            finally:
                self._dialog_operation = None
                self._host.session_operation_changed.emit()
            if not confirmed or self._closing:
                return
        self.runner.submit(action)

    def _completed(self, result: SessionCommandResult) -> None:
        if self._closing:
            return
        h, command = self._host, result.command
        if result.error:
            return  # Service snapshot and operation receipt retain truthful ownership.
        if command.operation == "prepare" and result.status.capture_phase == "live":
            prepared = command.preparation
            assert prepared is not None
            h._config = prepared.config
            h._session_name, h._pitcher_name = prepared.session_name, prepared.pitcher_name
            h._session_prepared = True
            h._pitch_count = h._last_pitch_count = 0
            h._processed_pitch_ids.clear()
            h._pitch_snapshot = []
            h._pitch_display.apply_strike_zone_overlay_config(prepared.config.strike_zone.batter_height_in)
            h._session_label.setText(f"Session: {prepared.session_name}")
            h._pitcher_label.setText(f"Pitcher: {prepared.pitcher_name}")
            h._pitch_count_label.setText("Pitches: 0")
            for mode in (h._broadcast_mode, h._progression_mode, h._game_mode):
                mode.clear()
            h._session_tracker.clear()
            try:
                state = load_state()
                state.update(last_left_camera=prepared.left_serial, last_right_camera=prepared.right_serial)
                save_state(state)
            except Exception:
                logger.exception("Prepared cameras but camera preferences could not be saved")
                self.runner.state = replace(self.runner.state, notice="Cameras ready. Camera preferences could not be saved.")
        elif command.operation in {"end", "stop_preview"}:
            h._session_prepared = False
        h.notify_preparation_changed()

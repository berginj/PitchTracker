"""Bounded UI command dispatch; pipeline services retain all lifecycle ownership."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from uuid import uuid4

from PySide6 import QtCore

from app.qt_pipeline_service import QtPipelineService
from app.services.orchestrator.runtime_status import RuntimeStatus
from configs.settings import AppConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrepareSession:
    config: AppConfig
    config_path: Path
    left_serial: str
    right_serial: str
    session_name: str
    pitcher_name: str


@dataclass(frozen=True)
class SessionCommand:
    operation: str
    correlation_id: str
    preparation: PrepareSession | None = None
    session_name: str = ""
    pitcher_name: str = ""


@dataclass(frozen=True)
class SessionOperation:
    pending: str | None = None
    failure_operation: str | None = None
    failure_message: str = ""
    notice: str = ""


@dataclass(frozen=True)
class SessionCommandResult:
    command: SessionCommand
    status: RuntimeStatus
    error: str = ""
    notice: str = ""
    summary: object | None = None


class SessionCommandThread(QtCore.QThread):
    def __init__(self, pipeline: QtPipelineService, command: SessionCommand, parent: QtCore.QObject):
        super().__init__(parent)
        self.pipeline, self.command = pipeline, command
        self.result: SessionCommandResult | None = None

    def run(self) -> None:
        command, pipeline = self.command, self.pipeline
        error, notice, summary = "", "", None
        try:
            if command.operation == "prepare":
                prepared = command.preparation
                assert prepared is not None
                status = pipeline.runtime_status()
                if status.owns_recording:
                    raise RuntimeError("End the recording before preparing another session")
                if status.owns_capture and status.capture_phase != "live":
                    raise RuntimeError("Retry Stop Preview before preparing cameras")
                pipeline.set_record_directory(Path(prepared.config.recording.output_dir))
                if status.owns_capture:
                    pipeline.set_batter_height_in(prepared.config.strike_zone.batter_height_in)
                    pipeline.set_ball_type(prepared.config.ball.type)
                else:
                    pipeline.start_capture(prepared.config, prepared.left_serial, prepared.right_serial,
                                           str(prepared.config_path))
                pipeline.change_pitcher(prepared.pitcher_name)
            elif command.operation == "pitcher":
                pipeline.change_pitcher(command.pitcher_name)
            elif command.operation == "record":
                notice = pipeline.start_recording(pitch_id="session", session_name=command.session_name,
                                                  mode="session")
            elif command.operation == "pause":
                pipeline.pause_recording()
            elif command.operation == "resume":
                pipeline.resume_recording()
            elif command.operation == "end":
                pipeline.stop_recording()
                try:
                    summary = pipeline.get_last_session_summary()
                except Exception:
                    logger.exception("Recording finalized but its summary could not be read")
                    notice = "Session saved. Final summary unavailable; open Sessions to inspect the artifacts."
            elif command.operation == "stop_preview":
                pipeline.stop_capture()
            else:
                raise ValueError(f"Unknown session operation: {command.operation}")
        except Exception as exc:
            logger.exception("Session command failed: %s (%s)", command.operation, command.correlation_id)
            error = str(exc)
        self.result = SessionCommandResult(command, pipeline.runtime_status(), error, notice, summary)


class SessionCommandRunner(QtCore.QObject):
    """Admit one command, retain its thread, and deliver its terminal receipt on Qt."""

    completed = QtCore.Signal(object)
    changed = QtCore.Signal()

    def __init__(self, pipeline: QtPipelineService, parent: QtCore.QObject):
        super().__init__(parent)
        self._pipeline = pipeline
        self._worker: SessionCommandThread | None = None
        self._closing = False
        self.state = SessionOperation()

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def stop_admission(self) -> None:
        self._closing = True

    def submit(self, operation: str, preparation: PrepareSession | None = None, session_name: str = "", pitcher_name: str = "") -> bool:
        if self.busy or self._closing or self._pipeline.runtime_status().pending_operation:
            return False
        command = SessionCommand(operation, uuid4().hex, preparation, session_name, pitcher_name)
        self.state = SessionOperation(pending=operation)
        worker = SessionCommandThread(self._pipeline, command, self)
        self._worker = worker
        worker.finished.connect(self._finished)
        self.changed.emit()  # Admission is visible before the worker starts.
        worker.start()
        return True

    def _finished(self) -> None:
        worker = self._worker
        assert worker is not None
        worker.wait()
        result = worker.result
        assert result is not None
        self._worker = None
        worker.deleteLater()
        self.state = SessionOperation(failure_operation=result.command.operation if result.error else None,
                                      failure_message=result.error, notice=result.notice)
        self.completed.emit(result)
        self.changed.emit()

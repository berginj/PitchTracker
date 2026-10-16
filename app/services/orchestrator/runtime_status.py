"""Immutable, nonblocking lifecycle status owned by the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import wraps
from pathlib import Path
from threading import Lock, RLock
import time
from typing import Any, Callable, TypeVar, TYPE_CHECKING
from uuid import uuid4

from app.events.event_bus import EventBus
from app.events.event_metadata import EventMetadata
from record.recorder import RecordingBundle
from contracts.pitcher import PitcherSelection

Result = TypeVar("Result")
if TYPE_CHECKING:
    from app.services.recording import RecordingServiceImpl
    from app.services.orchestrator.event_coordination import EventCoordinator


@dataclass(frozen=True)
class FinalizedSession:
    session_id: str
    session_dir: Path


@dataclass(frozen=True)
class RuntimeFailure:
    operation: str
    message: str
    code: str = "OPERATION_FAILED"


@dataclass(frozen=True)
class RuntimeStatus:
    sequence: int = 0
    capture_phase: str = "idle"
    recording_phase: str = "idle"
    session_id: str | None = None
    pending_operation: str | None = None
    correlation_id: str = ""
    failure: RuntimeFailure | None = None
    finalized_session: FinalizedSession | None = None
    active_session_dir: Path | None = None
    pitcher: PitcherSelection = PitcherSelection()

    @property
    def owns_capture(self) -> bool:
        return self.capture_phase != "idle"

    @property
    def owns_recording(self) -> bool:
        return self.recording_phase in {"starting", "recording", "paused", "finalizing"}


@dataclass(frozen=True)
class RuntimeStatusEvent:
    status: RuntimeStatus
    timestamp_ns: int
    metadata: EventMetadata


class RuntimeStatusPublisher:
    def __init__(self, bus: EventBus):
        self.commands = RLock()  # Also serializes nested shutdown -> stop commands.
        self._snapshot_lock = RLock()
        self._status = RuntimeStatus()
        self._bus = bus

    def snapshot(self) -> RuntimeStatus:
        with self._snapshot_lock:
            return self._status

    def publish(self, **changes: Any) -> RuntimeStatus:
        with self._snapshot_lock:
            self._status = replace(self._status, sequence=self._status.sequence + 1, **changes)
            status = self._status
        timestamp = time.monotonic_ns()
        self._bus.publish(RuntimeStatusEvent(status, timestamp, EventMetadata(
            message_type="RuntimeStatusEvent", correlation_id=status.correlation_id,
            timestamp_ns=timestamp, session_id=status.session_id or (
                status.finalized_session.session_id if status.finalized_session else None),
        )))
        return status


def runtime_command(operation: str) -> Callable[[Callable[..., Result]], Callable[..., Result]]:
    """Project facts only at lifecycle boundaries; never hold the snapshot lock during I/O."""
    def decorate(method: Callable[..., Result]) -> Callable[..., Result]:
        @wraps(method)
        def call(owner: Any, *args: Any, **kwargs: Any) -> Result:
            # Constructor-less structural fixtures remain supported by lifecycle tests.
            publisher = getattr(owner, "_runtime", None)
            if publisher is None:
                return method(owner, *args, **kwargs)
            with publisher.commands:
                before = publisher.snapshot()
                changes: dict[str, Any] = {
                    "pending_operation": operation, "correlation_id": uuid4().hex, "failure": None,
                }
                if operation == "start_capture":
                    changes["capture_phase"] = "starting"
                elif operation == "stop_capture" and before.owns_capture:
                    changes["capture_phase"] = "stopping"
                elif operation == "start_recording" and not before.owns_recording:
                    changes["recording_phase"] = "starting"
                elif operation == "stop_recording" and before.owns_recording:
                    changes["recording_phase"] = "finalizing"
                publisher.publish(**changes)
                session_id = before.session_id
                if operation == "start_recording" and not before.owns_recording:
                    session_id = kwargs.get("session_name") or (args[1] if len(args) > 1 else None) or "session"
                try:
                    result = method(owner, *args, **kwargs)
                except Exception as exc:
                    _publish_facts(owner, operation, session_id, RuntimeFailure(operation, str(exc)))
                    raise
                _publish_facts(owner, operation, session_id, result=result)
                return result
        return call
    return decorate


def _publish_facts(owner: Any, operation: str, session_id: str | None,
                   failure: RuntimeFailure | None = None, result: Any = None) -> None:
    publisher = owner._runtime
    before = publisher.snapshot()
    capture = "stopping" if owner._capture_stopping else "live" if owner._capturing else "idle"
    if owner._recording_active:
        recording = "finalizing" if owner._recording_stopping else "paused" if owner._recording_paused else "recording"
    elif operation == "stop_recording" and failure is None:
        recording = "completed"
    else:
        recording = "completed" if before.recording_phase == "completed" else "idle"
    finalized = before.finalized_session
    if operation == "stop_recording" and failure is None and isinstance(result, RecordingBundle):
        if result.session_dir is not None:
            completed_id = session_id or (
                finalized.session_id if finalized and finalized.session_dir == result.session_dir else "session")
            finalized = FinalizedSession(completed_id, result.session_dir)
    publisher.publish(capture_phase=capture, recording_phase=recording,
                      session_id=session_id if owner._recording_active else None,
                      active_session_dir=(owner._recording_service.get_session_dir()
                                          if owner._recording_active and owner._recording_service else None),
                      pending_operation=None, failure=failure, finalized_session=finalized)


class RuntimeStatusMethods:
    _runtime: RuntimeStatusPublisher
    _lock: Lock
    _recording_service: RecordingServiceImpl | None
    _event_coordinator: EventCoordinator

    @runtime_command("change_pitcher")
    def change_pitcher(self, name: str) -> PitcherSelection:
        status = self.runtime_status()
        if status.recording_phase == "finalizing" or status.capture_phase == "stopping":
            raise RuntimeError("Finish the pending stop before changing pitchers")
        return self._event_coordinator.request_pitcher(name)

    def runtime_status(self) -> RuntimeStatus:
        """Return a cached snapshot without waiting for capture/recording locks."""
        return self._runtime.snapshot()

    def get_session_dir(self) -> Path | None:
        """Return the current session directory, or None if not recording."""
        with self._lock:
            return self._recording_service.get_session_dir() if self._recording_service else None

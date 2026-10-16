"""Status reads remain nonblocking while lifecycle work drains; failures retain ownership."""

from pathlib import Path
from types import SimpleNamespace
from threading import Event, Thread
import time

import pytest

from app.events.event_bus import EventBus
from app.services.orchestrator.runtime_status import (
    RuntimeStatusMethods, RuntimeStatusPublisher, RuntimeStatusEvent, runtime_command,
)
from app.services.setup_workflow import SetupWorkflowService
from app.services.setup_workflow.runtime_access import (
    admission_status, begin_setup_capture, end_setup_capture, register_capture, release_capture,
)
from record.recorder import RecordingBundle


class LifecycleOwner(RuntimeStatusMethods):
    def __init__(self):
        self._capturing = True
        self._capture_stopping = False
        self._recording_active = False
        self._recording_paused = False
        self._recording_stopping = False
        self.bus = EventBus()
        self._runtime = RuntimeStatusPublisher(self.bus)
        self.entered, self.release = Event(), Event()
        self.release.set()
        self.fail_stop = False
        self._recording_service = SimpleNamespace(get_session_dir=lambda: Path("recordings/session"))

    @runtime_command("start_recording")
    def start_recording(self, pitch_id=None, session_name=None):
        self._recording_active = True

    @runtime_command("stop_recording")
    def stop_recording(self):
        self._recording_stopping = True
        self.entered.set()
        assert self.release.wait(5)
        if self.fail_stop:
            raise OSError("Writer still draining")
        self._recording_active = False
        self._recording_stopping = False
        return RecordingBundle("session", [], [], [], None, Path("recordings/session"))


def test_status_is_nonblocking_and_completed_receipt_follows_drain():
    owner = LifecycleOwner()
    events = []
    owner.bus.subscribe(RuntimeStatusEvent, events.append)
    owner.start_recording(session_name="session-42")
    assert owner.runtime_status().active_session_dir == Path("recordings/session")
    owner.release.clear()
    worker = Thread(target=owner.stop_recording)
    worker.start()
    try:
        assert owner.entered.wait(2)
        started = time.monotonic()
        status = owner.runtime_status()
        assert time.monotonic() - started < .1
        assert status.owns_recording and status.pending_operation == "stop_recording"
        assert status.finalized_session is None
        assert status.session_id == "session-42"
    finally:
        owner.release.set()
        worker.join(5)
    assert not worker.is_alive()
    status = owner.runtime_status()
    assert not status.owns_recording and status.recording_phase == "completed"
    assert status.active_session_dir is None
    assert status.finalized_session.session_id == "session-42"
    assert events[-1].metadata.session_id == "session-42"
    assert all(e.metadata.correlation_id and e.metadata.timestamp_ns for e in events)
    owner.stop_recording()
    assert owner.runtime_status().finalized_session.session_id == "session-42"


def test_failed_stop_has_no_completed_receipt_and_retry_preserves_session():
    owner = LifecycleOwner()
    owner.start_recording(session_name="owned-session")
    owner.fail_stop = True
    with pytest.raises(OSError, match="draining"):
        owner.stop_recording()
    status = owner.runtime_status()
    assert status.owns_recording and status.finalized_session is None
    assert status.failure.operation == "stop_recording"
    owner.fail_stop = False
    owner.stop_recording()
    assert owner.runtime_status().failure is None
    assert owner.runtime_status().finalized_session.session_id == "owned-session"


def test_strict_setup_rejects_preview_without_stopping_or_writing(tmp_path):
    config = tmp_path / "default.yaml"
    config.write_text((Path(__file__).parents[1] / "configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    rigs = tmp_path / "calibration/rigs"
    service = SetupWorkflowService(config, rigs, backend="sim", preserve_runtime_capture=True)
    initial = service.state
    files = set(service.root.iterdir())
    stopped = []
    register_capture(918273, rigs, lambda: stopped.append(True))
    try:
        assert not admission_status(rigs).permits_edit
        with pytest.raises(RuntimeError, match="explicitly"):
            service.update_settings("camera", {"width": 640})
        with pytest.raises(RuntimeError, match="explicitly"):
            service.finish()
        with pytest.raises(RuntimeError, match="explicitly"):
            begin_setup_capture(918274, rigs, stop_preview=False)
        assert stopped == []
        assert service.state == initial
        assert set(service.root.iterdir()) == files
    finally:
        release_capture(918273)
    assert admission_status(rigs).permits_edit


def test_runtime_capture_reservation_rejects_owned_setup(tmp_path):
    begin_setup_capture(918275, tmp_path, stop_preview=False)
    try:
        with pytest.raises(RuntimeError, match="Setup cameras"):
            register_capture(918276, tmp_path, lambda: pytest.fail("Must not stop setup"))
        assert not admission_status(tmp_path).capture_owned
    finally:
        end_setup_capture(918275)

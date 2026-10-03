"""Cancellation and timeout must reap actual one-shot tooling children."""

from concurrent.futures import CancelledError
from pathlib import Path
import subprocess
import sys
from threading import Event, Timer

import pytest

from app.services.tooling import SubprocessToolingService
from app.services.tooling import process_runner


@pytest.mark.parametrize("cancel", [True, False])
def test_blocked_worker_is_reaped_on_cancel_or_timeout(monkeypatch, tmp_path, cancel) -> None:
    original_popen = subprocess.Popen
    children = []

    def capture_child(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(process_runner.subprocess, "Popen", capture_child)
    cancel_event = Event()
    timer = Timer(0.1, cancel_event.set)
    if cancel:
        timer.start()
    command = [sys.executable, "-c", "import sys,time; sys.stdin.read(); time.sleep(60)"]
    try:
        with pytest.raises(CancelledError if cancel else subprocess.TimeoutExpired):
            process_runner.run_cancellable_worker(
                command, "{}", tmp_path, 5 if cancel else 0.1, cancel_event,
            )
    finally:
        timer.cancel()
        if cancel:
            timer.join()
    assert len(children) == 1
    assert children[0].poll() is not None
    assert all(pipe.closed for pipe in (children[0].stdin, children[0].stdout, children[0].stderr))


def test_precancelled_validation_does_not_launch_child(monkeypatch) -> None:
    cancel_event = Event()
    cancel_event.set()

    def unexpected_launch(*_args, **_kwargs):
        pytest.fail("Cancelled validation must not spawn a worker")

    monkeypatch.setattr(process_runner.subprocess, "Popen", unexpected_launch)
    with pytest.raises(CancelledError):
        SubprocessToolingService().validate_environment_with_cancellation(cancel_event)


def test_cancellable_validation_preserves_json_contract(monkeypatch, tmp_path: Path) -> None:
    from app.services.tooling import implementation

    monkeypatch.setattr(
        implementation, "worker_command",
        lambda *_args, **_kwargs: [
            sys.executable, "-c",
            "import json,sys; request=json.load(sys.stdin); "
            "assert request == {'task':'validate_environment','payload':{}}; "
            "print(json.dumps({'ok':True,'result':{'errors':[],'warnings':['test']}}))",
        ],
    )
    result = SubprocessToolingService(project_root=tmp_path).validate_environment_with_cancellation(Event())
    assert result.errors == []
    assert result.warnings == ["test"]

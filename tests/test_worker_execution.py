"""Source/frozen worker dispatch and actual process-deadline regressions."""

import json
import subprocess
import sys

import numpy as np
import pytest

from app.worker_process import worker_command
from app.services.analysis.fit_process import fit_in_process
from contracts import StereoObservation
from trajectory.contracts import FailureCode, TrajectoryFitRequest
from trajectory.serialization import decode_request, encode_request
from trajectory.camera_model import CameraModel


def test_frozen_workers_use_dedicated_executable(tmp_path, monkeypatch):
    gui = tmp_path / "PitchTracker.exe"
    worker = tmp_path / "PitchTrackerWorker.exe"
    worker.touch()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(gui))
    for task in ("camera_probe", "setup_capture", "tooling", "trajectory_fit"):
        assert worker_command(task) == [str(worker), task]
    worker.unlink()
    with pytest.raises(FileNotFoundError, match="reinstall"):
        worker_command("tooling")


def test_console_worker_health_never_constructs_a_gui():
    result = subprocess.run(
        worker_command("health"),
        capture_output=True,
        text=True,
        timeout=10,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["ok"]


def test_fit_request_preserves_camera_arrays_and_correlation():
    camera = CameraModel(1000.0, 1000.0, 640.0, 360.0, np.eye(3), np.zeros(3))
    request = TrajectoryFitRequest([], 0.0, camera_models={"left": camera}, correlation_id="pitch-a")
    restored = decode_request(json.loads(encode_request(request)))
    np.testing.assert_array_equal(restored.camera_models["left"].R, camera.R)
    assert restored.correlation_id == "pitch-a"
    envelope = json.loads(encode_request(request))
    envelope["correlation_id"] = "other-pitch"
    with pytest.raises(ValueError, match="correlation"):
        decode_request(envelope)


def test_timed_out_fit_child_is_reaped_and_next_fit_works(monkeypatch):
    import app.services.analysis.fit_process as module

    original_popen = subprocess.Popen
    children = []

    def capture_child(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        children.append(process)
        return process

    with monkeypatch.context() as context:
        context.setattr(subprocess, "Popen", capture_child)
        context.setattr(module, "worker_command", lambda task: [sys.executable, "-c", "import time; time.sleep(30)"])
        result = fit_in_process(TrajectoryFitRequest([], 0.0, deadline_seconds=0.2, correlation_id="stalled"))
    assert result.diagnostics.failure_codes == [FailureCode.DEADLINE_EXCEEDED]
    assert children and all(child.poll() is not None for child in children)
    observations = [
        StereoObservation(
            i * 20_000_000,
            (0.0, 0.0),
            (0.0, 0.0),
            0.0,
            3.0 - 16.087 * (i * 0.02) ** 2,
            8.0 - 88.0 * i * 0.02,
            1.0,
            confidence=1.0,
        )
        for i in range(8)
    ]
    result = fit_in_process(TrajectoryFitRequest(observations, 0.0, deadline_seconds=10.0, correlation_id="next"))
    assert result.samples
    assert not result.diagnostics.failure_codes


def test_worker_response_cannot_cross_pitch_generations(monkeypatch):
    import app.services.analysis.fit_process as module

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 0, json.dumps({"ok": True, "correlation_id": "stale"}), ""
        ),
    )
    result = fit_in_process(TrajectoryFitRequest([], 0.0, correlation_id="current"))
    assert result.diagnostics.failure_codes == [FailureCode.INVALID_INPUT]

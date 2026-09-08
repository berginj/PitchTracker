"""Opt-in frozen-artifact tests; synthetic inputs only, no physical cameras."""

import json
import os
from pathlib import Path
import subprocess

import pytest

from contracts import StereoObservation
from contracts.setup_capture import SetupCapturePurpose, SetupCaptureRequest
from trajectory.contracts import TrajectoryFitRequest
from trajectory.physics import PhysicsDragFitter
from trajectory.serialization import decode_result, encode_request


@pytest.fixture
def worker():
    directory = os.environ.get("PITCHTRACKER_PACKAGED_DIR")
    if not directory:
        pytest.skip("set PITCHTRACKER_PACKAGED_DIR to opt into frozen-artifact validation")
    path = Path(directory).resolve() / "PitchTrackerWorker.exe"
    assert path.is_file()
    return path


def run_worker(worker, task, payload=None, args=()):
    result = subprocess.run(
        [str(worker), task, *args],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30.0,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout


def test_frozen_health_and_probe_help_do_not_open_cameras(worker):
    assert json.loads(run_worker(worker, "health"))["ok"]
    assert "index" in run_worker(worker, "camera_probe", args=("--help",))


def test_frozen_fit_matches_source(worker):
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
    request = TrajectoryFitRequest(observations, 0.0, correlation_id="frozen-fit")
    payload = json.loads(run_worker(worker, "trajectory_fit", encode_request(request)))
    assert payload["ok"], payload
    assert payload["correlation_id"] == request.correlation_id
    fitted = decode_result(payload["result"])
    source = PhysicsDragFitter().fit_trajectory(request)
    assert not fitted.diagnostics.failure_codes
    assert fitted.samples[0].Vz == pytest.approx(source.samples[0].Vz, abs=1e-6)


def test_frozen_setup_capture_uses_only_simulator(worker, tmp_path):
    request = SetupCaptureRequest(
        "frozen-setup",
        SetupCapturePurpose.SYNC,
        "left",
        "right",
        Path("configs/default.yaml").resolve(),
        2,
        backend="sim",
        artifact_dir=tmp_path,
    )
    payload = json.loads(run_worker(worker, "setup_capture", json.dumps({"payload": request.to_payload()})))
    assert payload["ok"], payload
    assert len(payload["result"]["left_frames"]) == 2
    assert len(payload["result"]["right_frames"]) == 2


def test_frozen_tooling_dispatches_environment_validation(worker):
    payload = json.loads(run_worker(worker, "tooling", json.dumps({"task": "validate_environment", "payload": {}})))
    assert payload["ok"], payload
    assert "errors" in payload["result"]

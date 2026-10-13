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
def worker(tmp_path, monkeypatch):
    directory = os.environ.get("PITCHTRACKER_PACKAGED_DIR")
    if not directory:
        pytest.skip("set PITCHTRACKER_PACKAGED_DIR to opt into frozen-artifact validation")
    path = Path(directory).resolve() / "PitchTrackerWorker.exe"
    assert path.is_file()
    monkeypatch.setenv("PITCHTRACKER_DATA_DIR", str(tmp_path / "state"))
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
    request = {"task": "validate_environment", "payload": {"check_cameras": False}}
    payload = json.loads(run_worker(worker, "tooling", json.dumps(request)))
    assert payload["ok"], payload
    assert "errors" in payload["result"]


def test_frozen_comparison_retains_all_matrix_opportunities(worker, tmp_path):
    from tests.test_pipeline_comparison import dataset
    from contracts.pipeline_comparison import PipelineComparisonRequest

    source = dataset(tmp_path)
    request = PipelineComparisonRequest(source, tmp_path / "derived")
    lines = run_worker(worker, "pipeline_comparison", json.dumps(request.to_payload()) + "\n").splitlines()
    result = json.loads(lines[-1])
    assert result["message_type"] == "result", result
    report = json.loads(Path(result["report_path"]).read_text())
    assert report["status"] == "completed", report.get("error")
    assert len(report["results"]) == 12
    assert all(r["metrics"]["opportunities"] == 1 for r in report["results"])
    assert report["live_qualified"] is False and report["physical_claim_eligible"] is False


def test_frozen_onnx_worker_preserves_source_frame_identity(worker, tmp_path, monkeypatch):
    import numpy as np
    from tests.test_pipeline_comparison import write_synthetic_onnx
    from tests.test_baseballcv_adapter import model_bundle
    from contracts import Frame
    from contracts.model_bundle import file_hash
    from detect.supervised import SupervisedONNXDetector

    model = write_synthetic_onnx(tmp_path)
    bundle = model_bundle(tmp_path)
    payload = json.loads(bundle.manifest_path.read_text())
    payload.update(model_file=model.name, model_sha256=file_hash(model))
    bundle.manifest_path.write_text(json.dumps(payload))
    monkeypatch.setattr("detect.supervised.worker_command", lambda task: [str(worker), task])
    detector = SupervisedONNXDetector(bundle.manifest_path, deadline_seconds=2)
    image = np.zeros((480, 640, 3), np.uint8)
    try:
        values = detector.detect(Frame("frozen-left", 19, 1000, image, 640, 480, "BGR8"))
        assert len(values) == 1
        assert values[0].camera_id == "frozen-left" and values[0].frame_index == 19
        assert values[0].u == pytest.approx(320) and values[0].v == pytest.approx(240)
    finally:
        detector.close()

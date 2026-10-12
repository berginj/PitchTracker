"""Calibration artifact isolation and immutable frozen build provenance."""

import json
import importlib

import numpy as np

from app.services.tooling.worker_main import _handle_run_calibration
from contracts.tooling import CalibrationRequest


def test_calibration_worker_writes_requested_directory_without_rewriting_config(tmp_path, monkeypatch):
    config = tmp_path / "operator.yaml"
    config.write_text("operator: preserved\n")
    original = config.read_bytes()
    matrix = np.eye(3)
    updates = {
        "mtx_left": matrix, "mtx_right": matrix, "dist_left": np.zeros(5), "dist_right": np.zeros(5),
        "R": matrix, "T": np.array([[304.8], [0], [0]]), "img_size": (1280, 720),
        "baseline_ft": 1., "focal_length_px": 1000., "cx": 640., "cy": 360.,
        "rms_error_px": 0.4, "calibration_mode": "FULL",
    }
    monkeypatch.setattr(importlib.import_module("calib.quick_calibrate"), "_calibrate", lambda **_kwargs: updates)
    output = tmp_path / "revision"
    request = CalibrationRequest((), (), "9x6", 30., config, mode="full", write_updates=False, output_dir=output)
    _handle_run_calibration(request.to_payload())
    assert config.read_bytes() == original
    assert (output / "stereo_calibration.npz").exists()
    assert json.loads((output / "report.json").read_text())["calibration_mode"] == "FULL"
    assert not (tmp_path / "calibration").exists()


def test_frozen_build_identity_reads_bundled_revision_without_git(tmp_path, monkeypatch):
    from app.build_identity import current_source_revision
    monkeypatch.delenv("PITCHTRACKER_SOURCE_REVISION", raising=False)
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("app.runtime_paths.resource_root", lambda: tmp_path)
    payload = {"source_revision": "a" * 40, "working_tree_dirty": False}
    (tmp_path / "build_identity.json").write_text(json.dumps(payload))
    assert current_source_revision() == ("a" * 40, False)

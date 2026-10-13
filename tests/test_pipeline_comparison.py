"""Comparable opportunities, immutable inputs, cache isolation and worker shutdown."""

from dataclasses import replace
import csv
import json
from pathlib import Path
from threading import Event, Timer
from time import monotonic
import sys

import cv2
import numpy as np
import pytest
import yaml

from app.pipeline.recording.frame_timestamps import TIMESTAMP_COLUMNS, timestamp_row
from app.services.analysis.pipeline_comparison import execute_pipeline_comparison, run_pipeline_comparison
from app.services.analysis.comparison_inputs import load_dataset, validate_annotations
from app.services.analysis.comparison_qualification import admit_live_profile
from app.services.analysis.localization_calibration import estimate_localization_models
from configs.settings import load_config
from contracts import Frame, Detection
from contracts.model_bundle import file_hash
from contracts.pipeline_comparison import PipelineComparisonRequest, VARIANTS
from detect.supervised import SupervisedONNXDetector, DetectorUnavailable
from tests.test_baseballcv_adapter import model_bundle


def truth(index, camera):
    t = index / 60
    xyz = np.array([t, 0.5 - 16.087 * t**2, 60 - 88 * t])
    center = (320 + 500 * (xyz[0] - (1.0 if camera == "right" else 0)) / xyz[2], 240 + 500 * xyz[1] / xyz[2])
    return center, xyz


def dataset(tmp_path, count=22):
    root = tmp_path / "source"
    root.mkdir()
    raw = yaml.safe_load(Path("configs/default.yaml").read_text(encoding="utf-8"))
    raw["camera"].update(width=640, height=480)
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(raw))
    k = np.array([[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]])
    np.savez(
        tmp_path / "stereo.npz",
        mtx_left=k,
        mtx_right=k,
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([-304.8, 0, 0]),
        img_size=np.array([640, 480]),
        production_ready=True,
    )
    polygon = [[0, 0], [640, 0], [640, 480], [0, 480]]
    (tmp_path / "roi.json").write_text(json.dumps({"lane": polygon, "plate": polygon}))
    transform = np.eye(4)
    transform[1, 3] = 2.5
    (tmp_path / "field.json").write_text(
        json.dumps({"matrix_4x4": transform.tolist(), "rms_residual_ft": 0, "fixture_id": "synthetic"})
    )
    image = np.zeros((480, 640, 3), np.uint8)
    labels = []
    for camera in ("left", "right"):
        writer = cv2.VideoWriter(str(root / f"session_{camera}.avi"), cv2.VideoWriter_fourcc(*"MJPG"), 60, (640, 480))
        assert writer.isOpened()
        with (root / f"session_{camera}_timestamps.csv").open("w", newline="") as stream:
            csv_writer = csv.writer(stream)
            csv_writer.writerow(TIMESTAMP_COLUMNS)
            for index in range(count):
                frame = Frame(camera, index, 1_000_000_000 + index * 16_666_667, image, 640, 480, "BGR8", "test")
                writer.write(image)
                csv_writer.writerow(timestamp_row(frame, index, "accepted"))
                center, xyz = truth(index, camera)
                labels.append(
                    {
                        "camera_id": camera,
                        "frame_index": index,
                        "timestamp_ns": frame.t_capture_monotonic_ns,
                        "center_px": list(center),
                        "visibility": "visible",
                        "opportunity_id": "pitch-1",
                        "xyz_ft": [float(xyz[0]), float(xyz[1] + 2.5), float(xyz[2])],
                    }
                )
        writer.release()
    (tmp_path / "labels.json").write_text(
        json.dumps(
            {
                "schema_version": "comparison_annotations.v1",
                "human_reviewed": True,
                "opportunities": [{"id": "pitch-1", "start_ns": 1_000_000_000, "end_ns": 2_000_000_000}],
                "frames": labels,
            }
        )
    )
    entry = {
        "id": "synthetic",
        "root": "source",
        "split": "development",
        "ball_type": "baseball",
        "config": "config.yaml",
        "calibration": "stereo.npz",
        "roi": "roi.json",
        "field_transform": "field.json",
        "annotations": "labels.json",
        "pixel_covariances": {
            p: [[0.25, 0], [0, 0.25]] for p in ("classical_a", "classical_b", "baseballcv_box", "baseballcv_refined")
        },
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"schema_version": "comparison_dataset.v1", "sessions": [entry]}))
    return path


class SyntheticDetector:
    calls = 0
    regions_seen = []

    def __init__(self, *args, localization="box", **kwargs):
        self.localization = localization
        if len(args) > 2:
            type(self).regions_seen.append(args[2])

    def detect(self, frame):
        type(self).calls += 1
        center, xyz = truth(frame.frame_index, frame.camera_id)
        return [
            Detection(
                frame.camera_id,
                frame.frame_index,
                frame.t_capture_monotonic_ns,
                *center,
                4.0,
                0.9,
                localization_method="synthetic",
                radius_basis="component_area",
            )
        ]

    def close(self):
        pass


def test_all_twelve_variants_conserve_opportunities_and_resume_cache(tmp_path, monkeypatch):
    source = dataset(tmp_path)
    bundle_dir = tmp_path / "model"
    bundle_dir.mkdir()
    bundle = model_bundle(bundle_dir)
    before = {str(p): file_hash(p) for p in tmp_path.rglob("*") if p.is_file()}
    monkeypatch.setattr("app.services.analysis.pipeline_comparison.ClassicalDetector", SyntheticDetector)
    monkeypatch.setattr("app.services.analysis.pipeline_comparison.SupervisedONNXDetector", SyntheticDetector)
    request = PipelineComparisonRequest(source, tmp_path / "derived", bundle.manifest_path)
    result = execute_pipeline_comparison(request)
    assert result.report["status"] == "completed", result.report.get("error")
    assert len(result.report["results"]) == 12
    assert SyntheticDetector.regions_seen and not any(SyntheticDetector.regions_seen)
    assert {r["variant"] for r in result.report["results"]} == set(VARIANTS)
    for row in result.report["results"]:
        assert row["status"] == "COMPLETED", row.get("reason")
        assert row["metrics"]["opportunities"] == 1
        assert len(row["metrics"]["outcomes"]) == 1
        assert row["metrics"]["frames_offered"] == 44
        assert row["metrics"]["false_stereo_matches"] == 0
        assert row["metrics"]["target_error_ft"]["count"] > 0
    assert result.report["physical_claim_eligible"] is False
    assert all(not r["quality_passed"] for r in result.report["quality_assessments"])
    assert result.report["monocular_results"][0]["status"] == "UNAVAILABLE"
    calls = SyntheticDetector.calls
    resumed = execute_pipeline_comparison(replace(request, job_id="resume"))
    assert resumed.report["status"] == "completed"
    assert all(r["cache_reused"] for r in resumed.report["results"])
    assert SyntheticDetector.calls == calls
    assert all(file_hash(Path(p)) == h for p, h in before.items())
    models = estimate_localization_models(result.report_path)
    assert models["models"]


def test_missing_model_is_a_terminal_outcome_for_each_variant(tmp_path, monkeypatch):
    source = dataset(tmp_path)
    request = PipelineComparisonRequest(source, tmp_path / "derived", variants=("baseballcv_box:greedy_v1",))
    report = execute_pipeline_comparison(request).report
    assert report["status"] == "completed"
    row = report["results"][0]
    assert row["status"] == "UNAVAILABLE"
    assert row["metrics"]["outcomes"][0]["status"] == "UNAVAILABLE"
    assert not report["quality_assessments"][0]["quality_passed"]


def test_captured_output_and_unreviewed_labels_are_rejected(tmp_path):
    source = dataset(tmp_path)
    with pytest.raises(ValueError, match="captured"):
        load_dataset(source, tmp_path / "source" / "results")
    labels = json.loads((tmp_path / "labels.json").read_text())
    labels["human_reviewed"] = False
    with pytest.raises(ValueError, match="human"):
        validate_annotations(labels)


def test_live_admission_rejects_unqualified_model(tmp_path):
    config = load_config(Path("configs/default.yaml"))
    config = replace(config, detector=replace(config.detector, type="ml", model_format="yolo_v11"))
    with pytest.raises(ValueError, match="qualification"):
        admit_live_profile(config)


def test_cancelled_subprocess_preserves_partial_report(tmp_path):
    source = dataset(tmp_path)
    cancel = Event()
    timer = Timer(0.1, cancel.set)
    timer.start()
    start = monotonic()
    try:
        result = run_pipeline_comparison(PipelineComparisonRequest(source, tmp_path / "derived"), cancel)
        assert result.report["status"] == "cancelled"
        assert monotonic() - start < 5
    finally:
        timer.cancel()


def test_blocked_detector_is_killed_and_its_next_frame_recovers(tmp_path, monkeypatch):
    bundle = model_bundle(tmp_path)
    script = tmp_path / "blocked.py"
    script.write_text(
        "import json,sys,time\nsetup=json.loads(sys.stdin.readline())\n"
        "print(json.dumps({'ok':True,'model_sha256':"
        + repr(bundle.model_sha256)
        + ", 'bundle_sha256':"
        + repr(bundle.bundle_sha256)
        + "}),flush=True)\n"
        "sys.stdin.readline()\ntime.sleep(30)\n"
    )
    monkeypatch.setattr("detect.supervised.worker_command", lambda task: [sys.executable, str(script)])
    detector = SupervisedONNXDetector(bundle.manifest_path, deadline_seconds=0.05)
    image = np.zeros((20, 20), np.uint8)
    try:
        started = monotonic()
        with pytest.raises(DetectorUnavailable, match="deadline"):
            detector.detect(Frame("left", 1, 10, image, 20, 20, "GRAY8"))
        assert detector._process is None
        assert monotonic() - started < 4
        marker = tmp_path / "recovered"
        script.write_text(
            "import json,sys\nsetup=json.loads(sys.stdin.readline())\n"
            "print(json.dumps({'ok':True,'model_sha256':"
            + repr(bundle.model_sha256)
            + ", 'bundle_sha256':"
            + repr(bundle.bundle_sha256)
            + "}),flush=True)\n"
            "request=json.loads(sys.stdin.readline())\n"
            "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('done')\n"
            "print(json.dumps({'ok':True,'token':request['token'],'detections':[]}),flush=True)\n"
        )
        detector.deadline_seconds = 2
        assert detector.detect(Frame("left", 2, 20, image, 20, 20, "GRAY8")) == []
        assert marker.is_file()
    finally:
        detector.close()


def write_synthetic_onnx(tmp_path):
    onnx = pytest.importorskip("onnx")
    from onnx import helper, numpy_helper, TensorProto

    nodes = [
        helper.make_node("GlobalAveragePool", ["image"], ["average"]),
        helper.make_node("Flatten", ["average"], ["flat"], axis=1),
        helper.make_node("Gemm", ["flat", "weights", "bias"], ["values"], transB=1),
        helper.make_node("Reshape", ["values", "shape"], ["output"]),
    ]
    graph = helper.make_graph(
        nodes,
        "synthetic",
        [helper.make_tensor_value_info("image", TensorProto.FLOAT, [1, 3, 640, 640])],
        [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 5, 1])],
        [
            numpy_helper.from_array(np.zeros((5, 3), np.float32), "weights"),
            numpy_helper.from_array(np.array([320, 320, 8, 8, 0.9], np.float32), "bias"),
            numpy_helper.from_array(np.array([1, 5, 1], np.int64), "shape"),
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 12)])
    model.ir_version = 8
    onnx.save(model, tmp_path / "actual.onnx")
    return tmp_path / "actual.onnx"


def test_real_onnx_worker_preserves_frame_identity_and_closes(tmp_path):
    write_synthetic_onnx(tmp_path)
    bundle = model_bundle(tmp_path)
    payload = json.loads(bundle.manifest_path.read_text())
    payload.update(model_file="actual.onnx", model_sha256=file_hash(tmp_path / "actual.onnx"))
    bundle.manifest_path.write_text(json.dumps(payload))
    detector = SupervisedONNXDetector(bundle.manifest_path, deadline_seconds=2)
    image = np.zeros((480, 640, 3), np.uint8)
    try:
        first = detector.detect(Frame("serial-left", 11, 1000, image, 640, 480, "BGR8"))
        process = detector._process
        second = detector.detect(Frame("serial-right", 12, 2000, image, 640, 480, "BGR8"))
        assert first[0].u == pytest.approx(320) and first[0].v == pytest.approx(240)
        assert second[0].camera_id == "serial-right" and second[0].t_capture_monotonic_ns == 2000
        assert process is detector._process
    finally:
        detector.close()
    assert process.poll() is not None

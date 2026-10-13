"""Independent quality gates, trial accounting, geometry and desktop entry points."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

import numpy as np
import pytest

from app.events.event_bus import EventBus
from app.events.event_types import FrameCapturedEvent
from app.services.analysis.comparison_annotations import save_annotation_revision, bind_annotation_revision
from app.services.analysis.comparison_cache import CachedDetector
from app.services.analysis.comparison_inputs import load_dataset
from app.services.analysis.comparison_qualification import (
    assess_quality,
    configuration_binding,
    qualify_profile,
    admit_live_profile,
    validate_timing_journal,
)
from app.services.analysis.comparison_rig import rig_binding, admit_live_rig
from app.services.analysis.detector_trial import DetectorTrial
from configs.settings import load_config
from contracts import Frame
from contracts.model_bundle import file_hash
from contracts.pipeline_comparison import PipelineComparisonResult
from tests.test_baseballcv_adapter import model_bundle, matcher, det
from tests.test_pipeline_comparison import dataset, SyntheticDetector


def quality_report(config_path):
    metrics = {
        "positive_labels": 80,
        "opportunities": 40,
        "completed_opportunities": 40,
        "center_error_px": {"count": 80, "p95": 2.0},
        "target_error_ft": {"count": 24, "p95": 0.2},
        "surveyed_target_ids": [f"target-{i}" for i in range(12)],
        "false_stereo_matches": 0,
        "false_candidates": 0,
        "extra_attempts": [],
        "unverified_stereo_matches": 0,
        "stereo_recall": 0.98,
        "recall": 0.99,
        "strata": {"nominal": {"positive": 80, "detected": 80, "center_error_px": {"p95": 2.0}}},
    }
    baseline = {
        "session_id": "held-out",
        "ball_type": "baseball",
        "split": "evaluation",
        "variant": "classical_a:greedy_v1",
        "status": "COMPLETED",
        "metrics": metrics,
        "required_strata": ["nominal"],
        "config_path": str(config_path),
        "rig_binding": "geometry",
    }
    candidate = deepcopy(baseline)
    candidate["variant"] = "baseballcv_box:global_v3"
    candidate["metrics"]["center_error_px"]["p95"] = 1.6
    return {
        "status": "completed",
        "results": [baseline, candidate],
        "inputs": {},
        "implementation": {"test": "synthetic"},
    }


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"false_stereo_matches": 1}, "FALSE_STEREO_MATCH_REGRESSION"),
        ({"unverified_stereo_matches": 1}, "UNVERIFIED_STEREO_MATCHES"),
        ({"stereo_recall": 0.95}, "STEREO_COVERAGE_REGRESSION"),
        ({"recall": 0.95}, "DETECTION_COVERAGE_REGRESSION"),
        ({"completed_opportunities": 38}, "PITCH_COVERAGE_REGRESSION"),
        ({"surveyed_target_ids": ["one-target"]}, "DISTINCT_SURVEYED_TARGETS_MISSING"),
        ({"target_error_ft": {"count": 24, "p95": 0.3}}, "MEASUREMENT_ERROR_REGRESSION"),
        ({"strata": {}}, "REQUIRED_STRATA_MISSING"),
    ],
)
def test_quality_gates_preserve_measurement_and_coverage(change, reason):
    report = quality_report("unused.yaml")
    assert assess_quality(report)[0]["quality_passed"]
    report["results"][1]["metrics"].update(change)
    assessment = assess_quality(report)[0]
    assert not assessment["quality_passed"] and reason in assessment["reasons"]
    assert assessment["physical_claim_eligible"] is False


def test_receipt_binds_config_rig_and_current_evidence(tmp_path, monkeypatch):
    bundle = model_bundle(tmp_path)
    config_path = Path("configs/default.yaml").resolve()
    config = load_config(config_path)
    report = quality_report(config_path)
    report["model"] = {"bundle_sha256": bundle.bundle_sha256}
    timing = {
        "schema_version": "detector_sustained_run.v1",
        "configuration_binding": configuration_binding(config, bundle, "baseballcv_box:global_v3"),
        "implementation": report["implementation"],
        "rig_binding": "geometry",
        "bundle_sha256": bundle.bundle_sha256,
        "created_utc": "2026-10-13T12:00:00+00:00",
        "duration_seconds": 900,
        "recording_enabled": True,
        "source_kind": "operator_capture",
        "cameras": [
            {
                "camera_id": c,
                "offered": config.camera.fps * 900,
                "processed": config.camera.fps * 900,
                "roundtrip_p95_ms": 2,
                "pipeline_p95_ms": 3,
            }
            for c in ("left", "right")
        ],
    }
    report_path, timing_path = tmp_path / "report.json", tmp_path / "timing.json"
    report_path.write_text(json.dumps(report))
    timing_path.write_text(json.dumps(timing))
    monkeypatch.setattr(
        "app.services.analysis.pipeline_comparison.comparison_fingerprint", lambda: report["implementation"]
    )
    monkeypatch.setattr(
        "app.services.analysis.comparison_qualification.validate_timing_journal", lambda _: {"source": "hash"}
    )
    receipt = qualify_profile(report_path, timing_path, config, bundle.manifest_path, "baseballcv_box:global_v3")
    report["results"][1]["localization_override"] = True
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="localization covariance"):
        qualify_profile(report_path, timing_path, config, bundle.manifest_path, "baseballcv_box:global_v3")
    report["results"][1].pop("localization_override")
    report_path.write_text(json.dumps(report))
    assert receipt["rig_binding"] == "geometry" and receipt["physical_claim_eligible"] is False
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    selected = replace(
        config,
        stereo=replace(config.stereo, association_mode="global_v3"),
        detector=replace(
            config.detector,
            type="ml",
            model_format="yolo_v11",
            model_path=str(bundle.manifest_path),
            qualification_path=str(path),
            model_input_size=list(bundle.input_size),
            model_conf_threshold=bundle.confidence_threshold,
            model_class_id=bundle.ball_class_id,
        ),
    )
    admit_live_profile(selected)
    with pytest.raises(ValueError, match="config"):
        admit_live_profile(replace(selected, camera=replace(selected.camera, fps=30)))
    timing["rig_binding"] = "changed"
    timing_path.write_text(json.dumps(timing))
    with pytest.raises(ValueError, match="evidence"):
        admit_live_profile(selected)


def test_actual_rig_binding_changes_with_geometry_and_camera_assignment(tmp_path):
    source = dataset(tmp_path)
    sessions, _, _ = load_dataset(source, tmp_path / "derived")
    regions = json.loads((tmp_path / "roi.json").read_text())
    transform = json.loads((tmp_path / "field.json").read_text())
    identities = {"left": "left", "right": "right"}
    expected = sessions[0]["rig_binding"]
    assert expected == rig_binding(tmp_path / "stereo.npz", regions, transform, identities)
    assert expected != rig_binding(tmp_path / "stereo.npz", regions, transform, {"left": "right", "right": "left"})
    transform["matrix_4x4"][0][3] += 0.1
    assert expected != rig_binding(tmp_path / "stereo.npz", regions, transform, identities)
    config = load_config(tmp_path / "config.yaml")
    # Classical admission remains unaffected by unavailable research artifacts.
    admit_live_rig(config, None, {}, {}, {})


def test_experimental_stereo_is_not_promoted_without_a_qualified_profile():
    from app.services.orchestrator.pipeline_orchestrator import PipelineOrchestrator

    config = load_config(Path("configs/default.yaml"))
    experimental = replace(config, stereo=replace(config.stereo, association_mode="global_v3"))
    with pytest.raises(ValueError, match="comparison-only"):
        admit_live_profile(experimental)
    pipeline = PipelineOrchestrator(backend="sim")
    pipeline._config, pipeline._capturing = config, True
    with pytest.raises(ValueError, match="idle"):
        pipeline.reload_config(experimental)
    assert pipeline._config == config
    pipeline._config = experimental
    with pytest.raises(ValueError, match="idle"):
        pipeline.update_mound_distance(70)
    assert pipeline._config == experimental
    pipeline._capturing = False


def test_explicit_covariance_survives_zero_legacy_sigma_and_rejects_invalid_matrix():
    geometry = matcher()
    geometry._geometry = replace(geometry._geometry, pixel_sigma_px=0)
    result = geometry.triangulate(geometry.match(det("left", 330), det("right", 280)))
    assert np.array(result.covariance)[2, 2] > 0
    with pytest.raises(ValueError, match="symmetric"):
        geometry.triangulate(geometry.match(det("left", 330, covariance=((1, 4), (0, 1))), det("right", 280)))


def test_cache_corruption_and_label_revisions_preserve_sources(tmp_path):
    source = dataset(tmp_path)
    labels_path = tmp_path / "labels.json"
    before = file_hash(labels_path)
    labels = json.loads(labels_path.read_text())
    output = save_annotation_revision(labels_path, tmp_path / "new-labels.json", labels)
    updated = bind_annotation_revision(source, "synthetic", output, tmp_path / "new-study.json")
    assert json.loads(updated.read_text())["sessions"][0]["annotations"] == str(output)
    assert file_hash(labels_path) == before
    with pytest.raises(ValueError, match="new"):
        save_annotation_revision(labels_path, labels_path, labels)
    image = np.zeros((480, 640), np.uint8)
    frame = Frame("left", 1, 10, image, 640, 480, "GRAY8", "epoch")
    cache = CachedDetector(SyntheticDetector(), tmp_path / "cache", {"camera_id": "left"}, 1)
    cache.detect(frame)
    cache.commit()
    payload = json.loads(cache.path.read_text())
    next(iter(payload["rows"].values()))["detections"][0]["camera_id"] = "other-camera"
    cache.path.write_text(json.dumps(payload))
    loaded = CachedDetector(SyntheticDetector(), tmp_path / "cache", {"camera_id": "left"}, 1)
    assert not loaded.reused


def test_trial_conserves_frames_and_requires_recording_and_stable_epoch(tmp_path, monkeypatch):
    dataset(tmp_path)
    bundle_dir = tmp_path / "model"
    bundle_dir.mkdir()
    bundle = model_bundle(bundle_dir)
    closed = []

    class Worker:
        last_roundtrip_ms = 1.0

        def __init__(self, *args, **kwargs):
            pass

        def detect(self, frame):
            return []

        def close(self):
            closed.append(self)

    class Shadow:
        def __init__(self, *args):
            pass

        def process(self, *args):
            pass

        def close(self):
            pass

    monkeypatch.setattr("app.services.analysis.detector_trial.SupervisedONNXDetector", Worker)
    monkeypatch.setattr("app.services.analysis.detector_trial.ShadowStereoPipeline", Shadow)
    bus = EventBus()
    recording = [True]
    trial = DetectorTrial(
        bus,
        load_config(tmp_path / "config.yaml"),
        bundle.manifest_path,
        "baseballcv_box:global_v3",
        tmp_path / "trial.json",
        lambda: recording[0],
        tmp_path / "source",
        "sim",
        tmp_path / "stereo.npz",
        tmp_path / "roi.json",
        "left",
        "right",
        json.loads((tmp_path / "field.json").read_text()),
    )
    trial.start()
    image = np.zeros((480, 640, 3), np.uint8)
    for camera in ("left", "right"):
        for i in range(20):
            frame = Frame(camera, i, 1000 + i, image, 640, 480, "BGR8", "one")
            bus.publish(FrameCapturedEvent(camera, frame, frame.t_capture_monotonic_ns))
    recording[0] = False
    frame = Frame("left", 21, 2000, image, 640, 480, "BGR8", "two")
    bus.publish(FrameCapturedEvent("left", frame, 2000))
    path = trial.stop()
    report = json.loads(path.read_text())
    rows = [json.loads(line) for line in Path(report["frame_outcomes_path"]).read_text().splitlines()]
    assert len(rows) == sum(c["offered"] for c in report["cameras"]) == 41
    assert len({(r["camera_id"], r["frame_index"]) for r in rows}) == 41
    assert not report["recording_enabled"] and report["source_kind"] == "simulator_capture"
    assert len(closed) == 2 and all(not t.is_alive() for t in trial.threads)
    assert not report["physical_claim_eligible"]
    bus.publish(FrameCapturedEvent("left", frame, 2000))
    assert len(trial.rows) == 41


def test_journal_reconciles_recorded_identities_and_detects_tampering(tmp_path):
    dataset(tmp_path, count=2)
    rows = [
        {
            "camera_id": c,
            "frame_index": i,
            "timestamp_ns": 1_000_000_000 + i * 16_666_667,
            "capture_epoch": "test",
            "status": "PROCESSED",
            "roundtrip_ms": 2,
            "pipeline_ms": 3,
        }
        for c in ("left", "right")
        for i in range(2)
    ]
    journal = tmp_path / "frames.jsonl"
    journal.write_text("\n".join(json.dumps(r) for r in rows))
    timing = {
        "frame_outcomes_path": str(journal),
        "frame_outcomes_sha256": file_hash(journal),
        "source_session": str(tmp_path / "source"),
        "cameras": [
            {"camera_id": c, "offered": 2, "processed": 2, "roundtrip_p95_ms": 2.0, "pipeline_p95_ms": 3.0}
            for c in ("left", "right")
        ],
    }
    assert len(validate_timing_journal(timing)) == 2
    timing["cameras"][0]["offered"] = 3
    with pytest.raises(ValueError, match="conserve"):
        validate_timing_journal(timing)
    journal.write_text(journal.read_text() + "\n" + json.dumps(rows[0]))
    with pytest.raises(ValueError, match="changed"):
        validate_timing_journal(timing)


def test_monocular_adapter_is_local_and_keeps_its_measurement_basis(tmp_path):
    from research.baseballcv_local_worker import analyze_local_video, deny_network, sanitize

    pandas = SimpleNamespace(DataFrame=lambda rows: SimpleNamespace(empty=False))
    video = tmp_path / "input.avi"
    video.write_bytes(b"local-video")
    weight = tmp_path / "ball.pt"
    weight.write_bytes(b"synthetic-weight")
    models = {
        alias: {"path": str(weight), "sha256": file_hash(weight)}
        for alias in ("phc_detector", "glove_tracking", "ball_trackingv4")
    }
    module, scraper = SimpleNamespace(YOLO=lambda path: path), SimpleNamespace()

    class Analyzer:
        def __init__(self, **kwargs):
            pass

        def analyze(self, *args, **kwargs):
            assert module.LoadTools().load_model("ball_trackingv4") == str(weight)
            assert not scraper.BaseballSavVideoScraper.from_date_range().play_ids_df.empty
            assert module.YOLO(weight) == str(weight)
            with pytest.raises(ValueError, match="Undeclared"):
                module.YOLO("would-download.pt")
            return [{"ball_glove_frame": np.int64(12), "distance": float("nan")}]

    module.DistanceToZone = Analyzer
    rows = analyze_local_video(
        module, scraper, pandas, {"video": str(video), "models": models, "output_dir": str(tmp_path / "derived")}
    )
    assert sanitize(rows) == [{"ball_glove_frame": 12, "distance": None}]
    mirror = tmp_path / "derived" / "savant_videos" / "local_0_0.mp4"
    mirror.write_bytes(b"derived-only")
    assert video.read_bytes() == b"local-video"
    with pytest.raises(RuntimeError, match="disabled"):
        deny_network()


def test_review_dialog_starts_its_worker_and_returns_result(tmp_path, monkeypatch):
    from PySide6 import QtWidgets
    from ui.review.pipeline_comparison_dialog import PipelineComparisonDialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls = []

    def run(request, cancel, progress):
        calls.append(request)
        return PipelineComparisonResult({"status": "completed", "results": []}, tmp_path / "report.json")

    monkeypatch.setattr("ui.review.pipeline_comparison_dialog.run_pipeline_comparison", run)
    dialog = PipelineComparisonDialog()
    dialog.fields["dataset"].setText(str(tmp_path / "study.json"))
    dialog.fields["output"].setText(str(tmp_path / "derived"))
    started = monotonic()
    dialog._run()
    assert len(calls) == 1 and monotonic() - started < 3
    assert "completed" in dialog.details.toPlainText() and dialog.task is None
    dialog.close()
    app.processEvents()


def test_profile_selection_is_one_pending_generation_and_recording_blocks_edits(tmp_path):
    from app.services.analysis.comparison_selection import select_classical_profile
    from app.services.setup_workflow.runtime_access import reserve_recording, release_recording
    from tests.test_guided_setup_workflow import _new_workflow

    workflow = _new_workflow(tmp_path)
    initial = workflow.generation
    workflow.update_detector_profile({"mode": "MODE_B"}, "global_v2")
    assert workflow.generation == initial + 1
    assert workflow.config.detector.mode == "MODE_B"
    assert workflow.config.stereo.association_mode == "global_v2"
    assert workflow.state["changed"]
    select_classical_profile(workflow)
    assert workflow.generation == initial + 2
    assert workflow.config.detector.mode == "MODE_A" and workflow.config.stereo.association_mode == "greedy_v1"
    # Reserve against an independent directory with no unfinished setup checks.
    root = tmp_path / "recording-rigs"
    workflow.rigs.base_dir = root
    reserve_recording(1234567, root, None)
    try:
        with pytest.raises(RuntimeError, match="recording"):
            select_classical_profile(workflow)
        assert workflow.generation == initial + 2
    finally:
        release_recording(1234567)


def test_coaching_trial_controls_start_and_stop_workers(tmp_path, monkeypatch):
    from PySide6 import QtWidgets
    from ui.coaching.detector_trial_dialog import open_detector_trial

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    bundle = model_bundle(tmp_path)
    calls = []
    host = QtWidgets.QWidget()
    host._service = SimpleNamespace(
        start_detector_trial=lambda *args: calls.append("start"),
        stop_detector_trial=lambda: calls.append("stop"),
    )
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **kw: (str(bundle.manifest_path), ""))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **kw: (str(tmp_path / "trial.json"), ""))

    class Task:
        def __init__(self, parent, title, operation):
            self.started = False
            self.worker = SimpleNamespace(error=None, result=None, start=self.start)
            self.operation = operation

        def start(self):
            self.started = True
            from threading import Event

            self.worker.result = self.operation(Event())

        def exec(self):
            assert self.started

    def drive(dialog):
        buttons = {b.text(): b for b in dialog.findChildren(QtWidgets.QPushButton)}
        buttons["Start timing trial…"].click()
        buttons["Stop and save timings"].click()
        return 0

    monkeypatch.setattr("ui.coaching.detector_trial_dialog.ToolingTaskDialog", Task)
    monkeypatch.setattr(QtWidgets.QDialog, "exec", drive)
    open_detector_trial(host)
    assert calls == ["start", "stop"]
    host.close()
    app.processEvents()

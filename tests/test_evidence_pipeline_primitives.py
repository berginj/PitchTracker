from __future__ import annotations

import threading
from pathlib import Path

import pytest

from app.monitoring.rig_drift import RigDriftMonitor
from app.pipeline.corrections import correct_camera_time_offset, record_fitted_camera_time_offset
from app.pipeline.recording.evidence_package import EvidencePackageWriter, load_evidence_package
from app.pipeline.recording.pitch_recorder import PitchRecorder
from calib.ground_truth import ValidationCase, summarize_validation
from contracts import Detection, QualityAssessment, QUALITY_REJECTED
from contracts import StereoObservation
from configs.settings import load_config
from trajectory.mode_validation import ModeResult, compare_modes
from trajectory.tracklets import TrackletBuilder
from ui.coaching.diagnostics_view import present_quality


def test_bounded_correction_records_rejection_without_changing_raw_value() -> None:
    result = correct_camera_time_offset(10_000_000, 4.0, max_abs_offset_ms=1.0, correction_id="c1")
    assert result.corrected_timestamp_ns == 10_000_000
    assert result.record.status == "REJECTED"


def test_fitted_offset_record_does_not_claim_capture_timestamps_were_rewritten() -> None:
    record = record_fitted_camera_time_offset(
        0.4,
        prior_offset_ms=0.0,
        max_abs_offset_ms=1.0,
        correction_id="fit-1",
    )
    assert record.status == "APPLIED"
    assert record.parameters["capture_timestamps_mutated"] is False
    assert record.corrected_value == {"fitted_offset_ms": 0.4}


def test_drift_monitor_requires_repeated_bad_windows_and_hysteresis() -> None:
    monitor = RigDriftMonitor(
        "epipolar_px",
        warn_threshold=1,
        fail_threshold=2,
        recovery_threshold=0.5,
        window_size=3,
        required_bad_windows=2,
    )
    assert monitor.update(3).state == "PASS"
    assert monitor.update(3).state == "FAIL"
    assert monitor.update(0).state == "FAIL"
    assert monitor.update(0).state == "FAIL"
    assert monitor.update(0).state == "PASS"


def test_evidence_package_round_trip_and_integrity(tmp_path: Path) -> None:
    writer = EvidencePackageWriter(tmp_path, "pitch-1", {"rig_profile_id": "rig-1"})
    writer.add("pairs", {"pair_id": "p1", "skew_ms": 0.2})
    manifest = writer.write()
    loaded = load_evidence_package(manifest)
    assert loaded["manifest"]["schema_version"] == "evidence_package.v2"
    assert loaded["streams"]["pairs"][0]["pair_id"] == "p1"
    pairs_file = next(
        filename
        for filename, descriptor in loaded["manifest"]["files"].items()
        if descriptor.get("stream") == "pairs"
    )
    (manifest.parent / pairs_file).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        load_evidence_package(manifest)


def test_evidence_writes_are_serialized_and_keep_prior_generation_readable(tmp_path: Path) -> None:
    writer = EvidencePackageWriter(tmp_path, "pitch-1", {"rig_profile_id": "rig-1"})
    writer.add("pairs", {"pair_id": "initial"})
    manifest = writer.write()
    prior_manifest = manifest.parent / "prior_manifest.json"
    prior_manifest.write_bytes(manifest.read_bytes())

    errors: list[Exception] = []

    def append_and_write(index: int) -> None:
        try:
            writer.add("pairs", {"pair_id": f"p{index}"})
            writer.write()
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=append_and_write, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(load_evidence_package(manifest)["streams"]["pairs"]) == 9
    assert load_evidence_package(prior_manifest)["streams"]["pairs"] == [{"pair_id": "initial"}]
    assert list(manifest.parent.glob("*.tmp")) == []


def test_pitch_evidence_distinguishes_raw_and_field_observations(tmp_path: Path) -> None:
    recorder = PitchRecorder(load_config(Path("configs/default.yaml")), tmp_path, "pitch-1")
    raw = StereoObservation(1, (10, 20), (8, 20), 1.0, 2.0, 40.0, 0.9, confidence=0.8)
    field = StereoObservation(1, (10, 20), (8, 20), -0.5, 3.0, 39.0, 0.9, confidence=0.8)
    recorder.add_observation(raw)
    recorder.add_analysis_observations([field], coordinate_frame="field", rig_profile_id="rig-1")
    recorder.close(force=True)

    package = load_evidence_package(recorder.get_pitch_dir() / "evidence" / "manifest.json")
    assert package["streams"]["observations_3d"][0]["coordinate_frame"] == "camera"
    assert package["streams"]["analysis_observations"][0]["coordinate_frame"] == "field"
    assert package["streams"]["analysis_observations"][0]["rig_profile_id"] == "rig-1"


def test_tracklets_use_time_aware_motion_gate() -> None:
    builder = TrackletBuilder(max_speed_px_s=500)
    first = Detection("left", 1, 0, 10, 10, 3, 0.9)
    second = Detection("left", 2, 100_000_000, 20, 10, 3, 0.9)
    assert len(builder.update("left", [first])) == 1
    tracks = builder.update("left", [second])
    assert len(tracks) == 1
    assert len(tracks[0].detections) == 2


def test_tracklets_reject_candidates_after_finite_time_gap() -> None:
    builder = TrackletBuilder(max_speed_px_s=500, max_time_gap_ns=250_000_000)
    first = Detection("left", 1, 0, 10, 10, 3, 0.9)
    delayed = Detection("left", 2, 10_000_000_000, 11, 10, 3, 0.9)
    builder.update("left", [first])
    tracks = builder.update("left", [delayed])
    delayed_track = next(track for track in tracks if track.last is delayed)
    assert len(delayed_track.detections) == 1


def test_tracklet_ids_do_not_depend_on_detector_candidate_order() -> None:
    low = Detection("left", 1, 0, 10, 10, 3, 0.9)
    high = Detection("left", 1, 0, 20, 10, 3, 0.9)
    forward = TrackletBuilder(max_speed_px_s=500).update("left", [low, high])
    reverse = TrackletBuilder(max_speed_px_s=500).update("left", [high, low])
    assert [(track.tracklet_id, track.last.u) for track in forward] == [
        (track.tracklet_id, track.last.u) for track in reverse
    ]


def test_mode_comparison_never_auto_promotes() -> None:
    result = compare_modes(
        {
            "stereo_3d": ModeResult("stereo_3d", True, (0, 2, 0), 90, 1, 0.2),
            "ray_graph": ModeResult("ray_graph", True, (0.1, 2, 0), 91, 0.5, 0.1),
        },
        primary_mode="stereo_3d",
    )
    assert result["promotion_decision"] == "REQUIRES_GROUND_TRUTH"


def test_mode_comparison_suppresses_deltas_for_unconverged_results() -> None:
    result = compare_modes(
        {
            "stereo_3d": ModeResult("stereo_3d", True, (0, 2, 0), 90, 1, 0.2),
            "ray_graph": ModeResult("ray_graph", False, (4, 5, 0), 120, 10, 5),
        },
        primary_mode="stereo_3d",
    )
    comparison = result["comparisons"]["ray_graph"]
    assert comparison["plate_delta_ft"] is None
    assert comparison["speed_delta_mph"] is None


def test_ground_truth_keeps_rejections_in_denominator() -> None:
    report = summarize_validation(
        [
            ValidationCase("a", 90, 91, (0, 2), (0.1, 2), True),
            ValidationCase("b", 90, None, (0, 2), None, False),
        ],
        dataset_id="field-1",
    )
    assert report["sample_count"] == 2
    assert report["rejected_rate"] == 0.5
    assert report["claim_ready"] is False


def test_coaching_diagnostics_are_collapsed_by_default() -> None:
    assessment = QualityAssessment("a", "pitch", QUALITY_REJECTED, metrics={"skew": 4.2})
    collapsed = present_quality(assessment)
    expanded = present_quality(assessment, details_expanded=True)
    assert collapsed.detail_rows == ()
    assert collapsed.show_measurements is False
    assert expanded.detail_rows == (("skew", "4.2"),)

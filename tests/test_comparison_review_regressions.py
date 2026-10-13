"""Regression cases found while reviewing experimental detector admission."""

from copy import deepcopy
from dataclasses import replace
import json
import shutil
from types import SimpleNamespace

import numpy as np
import pytest

from app.services.analysis.comparison_inputs import load_dataset
from app.services.analysis.comparison_metrics import ComparisonAudit
from app.services.analysis.comparison_qualification import assess_quality, validate_timing_journal
from app.services.analysis.trial_pipeline import ShadowStereoPipeline
from configs.settings import load_config
from contracts import Detection, Frame
from contracts.evidence import AssociationEdgeEvidence, TriangulationDecisionEvidence
from contracts.model_bundle import file_hash
from tests.test_comparison_admission import quality_report
from tests.test_pipeline_comparison import dataset
from trajectory.tracklets_v2 import PredictiveTrackletBuilder


@pytest.mark.parametrize("copied", [False, True])
def test_development_and_evaluation_cannot_reuse_recordings(tmp_path, copied):
    source = dataset(tmp_path, count=2)
    payload = json.loads(source.read_text())
    evaluation = deepcopy(payload["sessions"][0])
    evaluation.update(id="held-out", split="evaluation")
    if copied:
        shutil.copytree(tmp_path / "source", tmp_path / "copied-source")
        evaluation["root"] = "copied-source"
    payload["sessions"].append(evaluation)
    source.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="distinct captured|disjoint"):
        load_dataset(source, tmp_path / "derived")


def _audit(left_identity, right_identity):
    labels = []
    for camera, identity in zip(("left", "right"), (left_identity, right_identity)):
        labels.append({
            "camera_id": camera, "frame_index": 0, "visibility": "visible", "center_px": [4, 4],
            "xyz_ft": [1, 2, 3], **identity,
        })
    audit = ComparisonAudit({
        "annotation": {"frames": labels, "opportunities": []},
        "transform": {"matrix_4x4": np.eye(4).tolist()},
    })
    for camera in ("left", "right"):
        frame = Frame(camera, 0, 100, np.zeros((8, 8), np.uint8), 8, 8, "GRAY8")
        detection = Detection(camera, 0, 100, 4, 4, 2, 1, candidate_id=camera)
        audit.frame(frame, [detection])
    edge = AssociationEdgeEvidence("edge", "left", "right", True, "ASSIGNED", 0, 0, 1)
    observation = TriangulationDecisionEvidence("observation", "edge", "ACCEPTED", (1, 2, 3))
    audit.association(SimpleNamespace(
        pair_id="pair", timestamp_ns=100, primary_algorithm="global_v3", edges=(edge,), triangulations=(observation,),
    ))
    return audit


@pytest.mark.parametrize("opportunity", [None, "pitch"])
def test_different_surveyed_targets_are_false_stereo_matches(opportunity):
    audit = _audit(
        {"target_id": "target-a", "opportunity_id": opportunity},
        {"target_id": "target-b", "opportunity_id": opportunity},
    )
    assert audit.false_matches == 1 and audit.correct_matches == 0
    assert not audit.target_errors and audit.paired_positive == 0


def test_same_target_without_pitch_identity_is_verified():
    audit = _audit({"target_id": "target"}, {"target_id": "target"})
    assert audit.correct_matches == audit.paired_positive == 1
    assert audit.target_errors == [0] and audit.target_ids == {"target"}


@pytest.mark.parametrize("left", [{}, {"target_id": "target"}])
def test_centers_without_shared_truth_identity_are_unverified(left):
    audit = _audit(left, {})
    assert audit.unverified_matches == 1 and audit.correct_matches == 0
    assert audit.paired_positive == 0


def test_disjoint_pitch_labels_do_not_inflate_stereo_recall_denominator():
    audit = _audit({"opportunity_id": "pitch-a"}, {"opportunity_id": "pitch-b"})
    assert audit.false_matches == 1 and audit.paired_positive == 0


@pytest.mark.parametrize("changes,reason", [
    ({"false_candidates": 1}, "FALSE_CANDIDATE_REGRESSION"),
    ({"extra_attempts": [{"status": "ESTIMATED"}]}, "EXTRA_PITCH_REGRESSION"),
])
def test_quality_admission_rejects_additional_false_positives(changes, reason):
    report = quality_report("unused.yaml")
    report["results"][1]["metrics"].update(changes)
    result = assess_quality(report)[0]
    assert not result["quality_passed"] and reason in result["reasons"]


def test_timing_cannot_qualify_one_camera_twice(tmp_path):
    dataset(tmp_path, count=2)
    rows = [{
        "camera_id": "left", "capture_epoch": "test", "frame_index": i,
        "timestamp_ns": 1_000_000_000 + i * 16_666_667, "status": "PROCESSED",
        "roundtrip_ms": 2, "pipeline_ms": 3,
    } for i in range(2)]
    journal = tmp_path / "frames.jsonl"
    journal.write_text("\n".join(json.dumps(row) for row in rows))
    camera = {"camera_id": "left", "offered": 2, "processed": 2, "roundtrip_p95_ms": 2, "pipeline_p95_ms": 3}
    timing = {
        "source_session": str(tmp_path / "source"), "frame_outcomes_path": str(journal),
        "frame_outcomes_sha256": file_hash(journal), "cameras": [camera, deepcopy(camera)],
    }
    with pytest.raises(ValueError, match="both distinct"):
        validate_timing_journal(timing)


def test_shadow_trial_uses_the_selected_stereo_tracker(tmp_path):
    dataset(tmp_path, count=2)
    config = load_config(tmp_path / "config.yaml")
    config = replace(config, stereo=replace(config.stereo, association_mode="greedy_v1"))
    shadow = ShadowStereoPipeline(
        config, "baseballcv_box:global_v3", tmp_path / "stereo.npz", tmp_path / "roi.json", "left", "right",
    )
    try:
        assert isinstance(shadow.candidates.builder, PredictiveTrackletBuilder)
    finally:
        shadow.close()

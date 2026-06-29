"""Tests for durable evidence contracts."""

from __future__ import annotations

import json

import pytest

from contracts import Candidate2DEvidence, Observation3DEvidence, PitchVerdictEvidence, StereoMatchEvidence


def test_candidate_2d_evidence_round_trips_json_payload() -> None:
    evidence = Candidate2DEvidence(
        candidate_id="left-0001-00",
        camera_id="left",
        frame_index=1,
        t_capture_monotonic_ns=123,
        center_px=(640.5, 360.25),
        radius_px=4.0,
        confidence=0.85,
        detector="classical",
        diagnostics={"area_px": 42.0},
    )

    restored = Candidate2DEvidence.from_payload(json.loads(json.dumps(evidence.to_payload())))

    assert restored == evidence
    assert evidence.to_payload()["center_px"] == [640.5, 360.25]
    assert evidence.to_payload()["schema_version"] == "evidence.v1"


def test_stereo_match_evidence_round_trips_rejection_reasons() -> None:
    evidence = StereoMatchEvidence(
        match_id="match-0001",
        left_candidate_id="left-0001-00",
        right_candidate_id="right-0001-00",
        t_ns=456,
        left_px=(640.0, 360.0),
        right_px=(610.0, 361.0),
        epipolar_error_px=1.0,
        score=0.8,
        status="REJECTED",
        rejection_reasons=["EPIPOLAR_ERROR"],
    )

    restored = StereoMatchEvidence.from_payload(json.loads(json.dumps(evidence.to_payload())))

    assert restored == evidence
    assert restored.rejection_reasons == ["EPIPOLAR_ERROR"]


def test_observation_3d_evidence_round_trips_covariance_and_depth_sigma() -> None:
    evidence = Observation3DEvidence(
        observation_id="obs-0001",
        match_id="match-0001",
        t_ns=789,
        xyz_ft=(0.1, 2.5, 50.0),
        quality=0.75,
        confidence=0.65,
        covariance=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 4.0)),
        depth_sigma_ft=2.0,
        diagnostics={"epipolar_error_px": 0.3},
    )

    payload = evidence.to_payload()
    restored = Observation3DEvidence.from_payload(json.loads(json.dumps(payload)))

    assert restored == evidence
    assert payload["xyz_ft"] == [0.1, 2.5, 50.0]
    assert payload["covariance"][2][2] == 4.0


def test_pitch_verdict_evidence_round_trips_warnings_and_rejections() -> None:
    evidence = PitchVerdictEvidence(
        pitch_id="pitch_00001",
        status="REJECT",
        observation_ids=["obs-0001", "obs-0002"],
        model_name="physics_drag",
        plate_crossing_xyz_ft=(0.0, 2.5, 0.0),
        confidence=0.25,
        expected_error_ft=1.2,
        rejection_reasons=["HIGH_DEPTH_UNCERTAINTY"],
        warning_reasons=["LARGE_OBSERVATION_GAP"],
        diagnostics={"observation_quality_status": "REJECT"},
    )

    restored = PitchVerdictEvidence.from_payload(json.loads(json.dumps(evidence.to_payload())))

    assert restored == evidence
    assert restored.plate_crossing_xyz_ft == (0.0, 2.5, 0.0)


def test_evidence_defaults_are_independent_lists_and_dicts() -> None:
    first = Candidate2DEvidence("a", "left", 0, 0, (1.0, 2.0), 3.0, 0.9, "classical")
    second = Candidate2DEvidence("b", "right", 0, 0, (1.0, 2.0), 3.0, 0.9, "classical")

    assert first.rejection_reasons is not second.rejection_reasons
    assert first.diagnostics is not second.diagnostics
    assert first.to_payload()["rejection_reasons"] == []
    assert second.to_payload()["diagnostics"] == {}


def test_evidence_rejects_malformed_vectors() -> None:
    payload = {
        "candidate_id": "bad",
        "camera_id": "left",
        "frame_index": 0,
        "t_capture_monotonic_ns": 0,
        "center_px": [1.0],
        "radius_px": 3.0,
        "confidence": 0.5,
        "detector": "classical",
    }

    with pytest.raises(ValueError):
        Candidate2DEvidence.from_payload(payload)

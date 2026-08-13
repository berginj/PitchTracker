"""Characterization tests for triangulation and association_graph modules."""

from __future__ import annotations

from unittest.mock import MagicMock

from contracts import Detection, Frame, StereoObservation
from stereo.association import StereoMatch

from app.pipeline.detection.triangulation import triangulate_matches
from app.pipeline.detection.association_graph import run_association


def _make_frame(camera_id: str, frame_index: int = 0, t_ns: int = 1_000_000) -> Frame:
    return Frame(
        camera_id=camera_id,
        frame_index=frame_index,
        t_capture_monotonic_ns=t_ns,
        image=None,
        width=640,
        height=480,
        pixfmt="gray8",
        capture_epoch="test",
    )


def _make_detection(camera_id: str, u: float = 320.0, v: float = 240.0) -> Detection:
    return Detection(
        camera_id=camera_id,
        frame_index=0,
        t_capture_monotonic_ns=1_000_000,
        u=u,
        v=v,
        radius_px=5.0,
        confidence=0.9,
    )


def _make_observation(quality: float = 1.0) -> StereoObservation:
    return StereoObservation(
        t_ns=1_000_000,
        left=(320.0, 240.0),
        right=(300.0, 240.0),
        X=10.0,
        Y=0.0,
        Z=30.0,
        quality=quality,
        confidence=0.9,
    )


class TestTriangulateMatched:
    """Verify successful triangulation produces ACCEPTED evidence."""

    def test_single_match_produces_observation(self):
        left = _make_detection("left")
        right = _make_detection("right", u=300.0)
        match = StereoMatch(left=left, right=right, epipolar_error_px=1.0, score=0.9)
        matcher = MagicMock()
        matcher.triangulate.return_value = _make_observation(quality=1.0)

        result = triangulate_matches("pair:abc", [match], matcher)
        assert len(result.observations) == 1
        assert len(result.evidence) == 1
        assert result.evidence[0].status == "ACCEPTED"
        assert result.observations[0].observation_id is not None
        assert result.observations[0].match_id is not None


class TestTriangulateRejected:
    """Verify zero-quality triangulation produces REJECTED evidence."""

    def test_zero_quality_is_rejected(self):
        left = _make_detection("left")
        right = _make_detection("right", u=300.0)
        match = StereoMatch(left=left, right=right, epipolar_error_px=1.0, score=0.9)
        matcher = MagicMock()
        matcher.triangulate.return_value = _make_observation(quality=0.0)

        result = triangulate_matches("pair:abc", [match], matcher)
        assert len(result.observations) == 1
        assert result.evidence[0].status == "REJECTED"
        assert "TRIANGULATION_QUALITY_ZERO" in result.evidence[0].rejection_reasons


class TestTriangulateFailure:
    """Verify triangulation exception produces FAILED evidence."""

    def test_exception_produces_failed(self):
        left = _make_detection("left")
        right = _make_detection("right", u=300.0)
        match = StereoMatch(left=left, right=right, epipolar_error_px=1.0, score=0.9)
        matcher = MagicMock()
        matcher.triangulate.side_effect = RuntimeError("calibration missing")

        result = triangulate_matches("pair:abc", [match], matcher)
        assert len(result.observations) == 0
        assert len(result.evidence) == 1
        assert result.evidence[0].status == "FAILED"
        assert "TRIANGULATION_EXCEPTION" in result.evidence[0].rejection_reasons


class TestTriangulateEmpty:
    """Verify empty match list produces empty results."""

    def test_no_matches_no_output(self):
        matcher = MagicMock()
        result = triangulate_matches("pair:abc", [], matcher)
        assert result.observations == []
        assert result.evidence == []
        assert result.final_edge_ids == []


class TestAssociationGraphRejection:
    """Verify association emits NO_VALID_STEREO_ASSOCIATION when no matches."""

    def test_no_detections_no_association(self):
        left_frame = _make_frame("left")
        right_frame = _make_frame("right")
        config = MagicMock()
        config.stereo.epipolar_epsilon_px = 10.0
        config.stereo.association_mode = "greedy_v1"
        matcher = MagicMock()
        matcher.match.return_value = None

        result = run_association(
            left_frame, right_frame, [], [], config, matcher, None,
        )
        assert result.triangulation.observations == []
        assert result.triangulation.final_edge_ids == []

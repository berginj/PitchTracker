"""Tests for app.pipeline.utils module."""

from __future__ import annotations


from app.contracts import PitchSummary
from app.pipeline.utils import (
    build_session_summary,
    build_stereo_matches,
    gate_detections,
    stats_to_dict,
)
from capture.camera_device import CameraStats
from contracts import Detection
from detect.lane import LaneGate, LaneRoi


def _detection(camera_id: str, u: float, v: float) -> Detection:
    """Build a Detection at a pixel location for the given camera."""
    return Detection(
        camera_id=camera_id,
        frame_index=0,
        t_capture_monotonic_ns=1000,
        u=u,
        v=v,
        radius_px=10.0,
        confidence=0.9,
    )


class TestStatsToDict:
    """Tests for stats_to_dict()."""

    def test_converts_stats_to_dict(self):
        """Test converting CameraStats to dictionary."""
        stats = CameraStats(
            fps_avg=30.0,
            fps_instant=29.5,
            jitter_p95_ms=2.0,
            dropped_frames=5,
            queue_depth=1,
            capture_latency_ms=8.0,
        )
        result = stats_to_dict(stats)

        assert result == {
            "fps_avg": 30.0,
            "fps_instant": 29.5,
            "jitter_p95_ms": 2.0,
            "dropped_frames": 5.0,
            "queue_depth": 1.0,
            "capture_latency_ms": 8.0,
        }


class TestGateDetections:
    """Tests for gate_detections()."""

    def test_returns_all_when_no_gate(self):
        """With no gate, detections pass through unfiltered."""
        detections = [_detection("left", 100, 100)]
        result = gate_detections(None, detections)
        assert result == detections

    def test_filters_detections_through_gate(self):
        """Test filters detections through lane gate."""
        roi = LaneRoi(polygon=[(0.0, 0.0), (640.0, 0.0), (640.0, 480.0), (0.0, 480.0)])
        gate = LaneGate(roi_by_camera={"left": roi})

        # Detection inside the ROI polygon
        inside = _detection("left", 320, 240)
        # Detection outside the ROI polygon
        outside = _detection("left", 1000, 1000)

        result = gate_detections(gate, [inside, outside])
        assert inside in result
        assert outside not in result


class TestBuildStereoMatches:
    """Tests for build_stereo_matches()."""

    def test_builds_matches_from_detections(self):
        """Test builds stereo matches from left and right detections."""
        left_dets = [_detection("left", 100, 100)]
        right_dets = [_detection("right", 90, 100)]

        # Equal v-coordinates fall within the epipolar tolerance -> one match.
        result = build_stereo_matches(left_dets, right_dets)
        assert isinstance(result, list)
        assert len(result) == 1


class TestBuildSessionSummary:
    """Tests for build_session_summary()."""

    def test_builds_summary_with_no_pitches(self):
        """Test builds session summary with no pitches."""
        summary = build_session_summary("session-001", [])

        assert summary.session_id == "session-001"
        assert summary.pitch_count == 0
        assert summary.strikes == 0
        assert summary.balls == 0
        assert summary.heatmap == [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        assert summary.pitches == []

    def test_builds_summary_with_pitches(self):
        """Test builds session summary with pitches."""
        pitches = [
            PitchSummary(
                pitch_id="pitch-001",
                t_start_ns=1000,
                t_end_ns=2000,
                is_strike=True,
                zone_row=1,
                zone_col=1,
                run_in=2.5,
                rise_in=1.0,
                speed_mph=85.0,
                rotation_rpm=2000.0,
                sample_count=30,
            ),
            PitchSummary(
                pitch_id="pitch-002",
                t_start_ns=3000,
                t_end_ns=4000,
                is_strike=False,
                zone_row=0,
                zone_col=0,
                run_in=-1.5,
                rise_in=3.0,
                speed_mph=82.0,
                rotation_rpm=1800.0,
                sample_count=25,
            ),
        ]

        summary = build_session_summary("session-001", pitches)

        assert summary.session_id == "session-001"
        assert summary.pitch_count == 2
        assert summary.strikes == 1
        assert summary.balls == 1
        assert summary.pitches == pitches
        # Heatmap should have one strike at (1,1)
        assert summary.heatmap[1][1] == 1

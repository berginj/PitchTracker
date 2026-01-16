"""Utility functions for pipeline service."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from capture.camera_device import CameraStats
from detect.lane import LaneGate
from stereo.association import StereoMatch

# Import from parent module to avoid circular dependency
# These are part of the public API and defined in pipeline_service.py
if False:  # TYPE_CHECKING equivalent
    from app.pipeline_service import PitchSummary, SessionSummary


def stats_to_dict(stats: CameraStats) -> Dict[str, float]:
    """Convert camera stats to dictionary.

    Args:
        stats: Camera statistics object

    Returns:
        Dictionary with camera stats as floats
    """
    return {
        "fps_avg": stats.fps_avg,
        "fps_instant": stats.fps_instant,
        "jitter_p95_ms": stats.jitter_p95_ms,
        "dropped_frames": float(stats.dropped_frames),
        "queue_depth": float(stats.queue_depth),
        "capture_latency_ms": stats.capture_latency_ms,
    }


def gate_detections(lane_gate: Optional[LaneGate], detections: Iterable) -> list:
    """Filter detections through lane gate.

    Args:
        lane_gate: Optional lane gate to filter detections
        detections: Iterable of detections to filter

    Returns:
        List of detections (filtered if gate provided, otherwise all detections)
    """
    if lane_gate is None:
        return list(detections)
    return lane_gate.filter_detections(detections)


def build_stereo_matches(
    left_detections: Iterable, right_detections: Iterable
) -> list[StereoMatch]:
    """Build stereo match candidates from left/right detections.

    Creates all possible stereo pairs between left and right detections
    with epipolar error and confidence scores.

    Args:
        left_detections: Detections from left camera
        right_detections: Detections from right camera

    Returns:
        List of StereoMatch candidates
    """
    matches: list[StereoMatch] = []
    for left in left_detections:
        for right in right_detections:
            matches.append(
                StereoMatch(
                    left=left,
                    right=right,
                    epipolar_error_px=abs(left.v - right.v),
                    score=min(left.confidence, right.confidence),
                )
            )
    return matches


def build_session_summary(session_id: str, pitches: List) -> Dict:
    """Build session summary from pitch list.

    Aggregates pitch data into session-level statistics including
    strike/ball counts and heatmap of pitch locations.

    Args:
        session_id: Session identifier
        pitches: List of PitchSummary objects

    Returns:
        Dictionary with session summary data
    """
    heatmap = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    strikes = 0
    balls = 0
    for pitch in pitches:
        if pitch.is_strike:
            strikes += 1
        else:
            balls += 1
        if pitch.zone_row and pitch.zone_col:
            row = max(1, min(3, pitch.zone_row))
            row = 3 - row  # Flip Y-axis for display
            col = max(1, min(3, pitch.zone_col)) - 1
            heatmap[row][col] += 1

    # Import here to avoid circular dependency
    from app.pipeline_service import SessionSummary

    return SessionSummary(
        session_id=session_id,
        pitch_count=len(pitches),
        strikes=strikes,
        balls=balls,
        heatmap=heatmap,
        pitches=list(pitches),
    )

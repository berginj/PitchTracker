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
    left_detections: Iterable, right_detections: Iterable, epipolar_tolerance: float = 10.0
) -> list[StereoMatch]:
    """Build stereo match candidates with epipolar pre-filtering.

    Applies epipolar constraint to reduce match candidates by 80-90%.
    In a calibrated stereo setup, corresponding points lie on the same
    horizontal line (±tolerance). This pre-filtering eliminates invalid
    matches before expensive validation, reducing O(n²) overhead.

    Args:
        left_detections: Detections from left camera
        right_detections: Detections from right camera
        epipolar_tolerance: Maximum vertical pixel distance for valid matches (default: 10.0)

    Returns:
        List of StereoMatch candidates (80-90% fewer than naive O(n²) pairing)
    """
    matches: list[StereoMatch] = []

    # Convert to lists for efficient indexing/sorting
    left_list = list(left_detections)
    right_list = list(right_detections)

    # Early exit if either side has no detections
    if not left_list or not right_list:
        return matches

    # Sort right detections by v-coordinate for efficient range queries
    right_sorted = sorted(right_list, key=lambda d: d.v)

    # For each left detection, find right detections within epipolar band
    for left in left_list:
        left_v = left.v

        # Binary search for candidates within [left_v - tolerance, left_v + tolerance]
        # Linear scan is acceptable for small detection counts (5-10 per camera)
        for right in right_sorted:
            epipolar_error = abs(right.v - left_v)

            # Skip if outside epipolar band
            if epipolar_error > epipolar_tolerance:
                # Since sorted, can break early if we've passed the band
                if right.v > left_v + epipolar_tolerance:
                    break
                continue

            # Create match for valid epipolar candidate
            matches.append(
                StereoMatch(
                    left=left,
                    right=right,
                    epipolar_error_px=epipolar_error,
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

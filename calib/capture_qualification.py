"""Pure capture qualification metrics used by setup and session preflight."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np

from app.monitoring.error_budget import ErrorBudget
from contracts import QualityAssessment


@dataclass(frozen=True)
class CaptureQualification:
    requested_mode: dict[str, object]
    negotiated_mode: dict[str, object]
    frame_count_left: int
    frame_count_right: int
    paired_count: int
    expected_frames: int
    achieved_fps_left: float
    achieved_fps_right: float
    jitter_p95_ms_left: float
    jitter_p95_ms_right: float
    pair_skew_p95_ms: float
    pair_skew_p99_ms: float
    frame_drop_rate: float
    unmatched_frame_rate: float
    controls_verified: bool
    assessment: QualityAssessment


def qualify_capture(
    left_timestamps_ns: Iterable[int],
    right_timestamps_ns: Iterable[int],
    pair_skews_ns: Iterable[int],
    *,
    requested_mode: Mapping[str, object],
    negotiated_mode: Mapping[str, object],
    expected_frames: int,
    controls_verified: bool,
    budget: ErrorBudget,
    qualification_id: str,
) -> CaptureQualification:
    left = np.asarray(tuple(left_timestamps_ns), dtype=np.int64)
    right = np.asarray(tuple(right_timestamps_ns), dtype=np.int64)
    skew_ms = np.asarray(tuple(pair_skews_ns), dtype=float) / 1e6
    pair_count = int(skew_ms.size)
    total_frames = int(left.size + right.size)
    expected_total = max(int(expected_frames) * 2, 1)
    drop_rate = max(0.0, 1.0 - total_frames / expected_total)
    unmatched_rate = max(0.0, 1.0 - (pair_count * 2) / max(total_frames, 1))
    achieved_fps_left = _fps(left)
    achieved_fps_right = _fps(right)
    jitter_left = _jitter(left)
    jitter_right = _jitter(right)
    requested_fps = float(requested_mode.get("fps") or 0.0)
    metrics = {
        "pair_skew_p95_ms": _percentile(skew_ms, 95),
        "pair_skew_p99_ms": _percentile(skew_ms, 99),
        "frame_drop_rate": drop_rate,
        "unmatched_frame_rate": unmatched_rate,
        "mode_mismatch": 0.0 if dict(requested_mode) == dict(negotiated_mode) else 1.0,
        "controls_unverified": 0.0 if controls_verified else 1.0,
        "fps_shortfall_ratio_left": _shortfall_ratio(achieved_fps_left, requested_fps),
        "fps_shortfall_ratio_right": _shortfall_ratio(achieved_fps_right, requested_fps),
        "jitter_p95_ms_left": jitter_left,
        "jitter_p95_ms_right": jitter_right,
    }
    assessment = budget.assess("capture_qualification", metrics, assessment_id=qualification_id)
    return CaptureQualification(
        requested_mode=dict(requested_mode),
        negotiated_mode=dict(negotiated_mode),
        frame_count_left=int(left.size),
        frame_count_right=int(right.size),
        paired_count=pair_count,
        expected_frames=int(expected_frames),
        achieved_fps_left=achieved_fps_left,
        achieved_fps_right=achieved_fps_right,
        jitter_p95_ms_left=jitter_left,
        jitter_p95_ms_right=jitter_right,
        pair_skew_p95_ms=metrics["pair_skew_p95_ms"],
        pair_skew_p99_ms=metrics["pair_skew_p99_ms"],
        frame_drop_rate=drop_rate,
        unmatched_frame_rate=unmatched_rate,
        controls_verified=controls_verified,
        assessment=assessment,
    )


def _fps(timestamps: np.ndarray) -> float:
    if timestamps.size < 2:
        return 0.0
    duration_s = float(timestamps[-1] - timestamps[0]) / 1e9
    return 0.0 if duration_s <= 0 else float(timestamps.size - 1) / duration_s


def _jitter(timestamps: np.ndarray) -> float:
    if timestamps.size < 3:
        return 0.0
    intervals_ms = np.diff(timestamps).astype(float) / 1e6
    return _percentile(np.abs(intervals_ms - np.median(intervals_ms)), 95)


def _percentile(values: np.ndarray, percentile: float) -> float:
    return 0.0 if values.size == 0 else float(np.percentile(values, percentile))


def _shortfall_ratio(actual_fps: float, requested_fps: float) -> float:
    if requested_fps <= 0:
        return 0.0
    return max(0.0, 1.0 - actual_fps / requested_fps)


__all__ = ["CaptureQualification", "qualify_capture"]

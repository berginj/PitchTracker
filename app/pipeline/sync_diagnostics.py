"""Camera synchronization diagnostics for fast ball tracking."""

from __future__ import annotations

from typing import Iterable

import numpy as np


MPH_TO_FT_PER_SEC = 1.4666666667
IN_PER_FT = 12.0


def summarize_sync_quality(
    deltas_ns: Iterable[int],
    total_paired: int,
    dropped_sync: int,
    max_speed_mph: float = 60.0,
) -> dict:
    """Summarize stereo timing skew in milliseconds and ball-travel inches."""
    deltas = list(deltas_ns)
    total = total_paired + dropped_sync
    drop_rate = (dropped_sync / max(total, 1)) * 100.0
    if not deltas:
        return {
            "mean_delta_ms": 0.0,
            "p95_delta_ms": 0.0,
            "max_delta_ms": 0.0,
            "mean_motion_in_at_max_speed": 0.0,
            "p95_motion_in_at_max_speed": 0.0,
            "max_motion_in_at_max_speed": 0.0,
            "max_speed_mph": float(max_speed_mph),
            "sync_quality": "UNKNOWN",
            "sync_recommendation": "No paired frames available yet.",
            "total_paired": total_paired,
            "dropped_sync": dropped_sync,
            "drop_rate_pct": 0.0,
        }

    deltas_ms = np.asarray(deltas, dtype=np.float64) / 1e6
    mean_delta = float(np.mean(deltas_ms))
    p95_delta = float(np.percentile(deltas_ms, 95))
    max_delta = float(np.max(deltas_ms))
    mean_motion = _motion_inches(mean_delta, max_speed_mph)
    p95_motion = _motion_inches(p95_delta, max_speed_mph)
    max_motion = _motion_inches(max_delta, max_speed_mph)
    quality, recommendation = _classify_sync(p95_motion, max_motion, drop_rate)
    return {
        "mean_delta_ms": mean_delta,
        "p95_delta_ms": p95_delta,
        "max_delta_ms": max_delta,
        "mean_motion_in_at_max_speed": mean_motion,
        "p95_motion_in_at_max_speed": p95_motion,
        "max_motion_in_at_max_speed": max_motion,
        "max_speed_mph": float(max_speed_mph),
        "sync_quality": quality,
        "sync_recommendation": recommendation,
        "total_paired": total_paired,
        "dropped_sync": dropped_sync,
        "drop_rate_pct": float(drop_rate),
    }


def _motion_inches(delta_ms: float, speed_mph: float) -> float:
    return float(speed_mph * MPH_TO_FT_PER_SEC * (delta_ms / 1000.0) * IN_PER_FT)


def _classify_sync(p95_motion_in: float, max_motion_in: float, drop_rate_pct: float) -> tuple[str, str]:
    if p95_motion_in <= 4.0 and max_motion_in <= 6.0 and drop_rate_pct <= 2.0:
        return "GOOD", "Timing skew is within the practical software tolerance for 30-60 mph tracking."
    if p95_motion_in <= 8.0 and max_motion_in <= 12.0 and drop_rate_pct <= 10.0:
        return "WARN", "Timing skew can affect plate location; prefer frame-index pairing or lower exposure latency."
    return (
        "POOR",
        "Timing skew is large enough to corrupt stereo geometry; use hardware sync/global shutter if possible.",
    )

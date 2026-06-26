"""Setup-time left/right camera synchronization check (setup state-machine step 3).

This is distinct from ``app.pipeline.sync_diagnostics`` (which monitors sync
quality *during* a live session). Here we take two streams of per-camera frame
capture timestamps gathered during setup, pair them, and decide whether the
measured timing skew is small enough to trust stereo geometry at the target
pitch speed.

The cameras in the target rig are two independent USB UVC global-shutter
cameras (no hardware trigger), so timestamps are host receive times. This check
surfaces the *actual* skew rather than assuming it is negligible.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

from contracts.setup import (
    SYNC_VERDICT_GOOD,
    SYNC_VERDICT_POOR,
    SYNC_VERDICT_UNKNOWN,
    SYNC_VERDICT_WARN,
    SyncCheckResult,
)

# Convert mph -> ft/s and ft -> in so we can express timing skew as the distance
# a ball travels during the skew window.
_MPH_TO_FT_PER_SEC = 1.4666666667
_IN_PER_FT = 12.0


def _motion_inches(delta_ms: float, speed_mph: float) -> float:
    """Inches a ball at ``speed_mph`` travels during ``delta_ms`` milliseconds."""
    return float(speed_mph * _MPH_TO_FT_PER_SEC * (delta_ms / 1000.0) * _IN_PER_FT)


def pair_timestamps(
    left_ts_ns: Sequence[int],
    right_ts_ns: Sequence[int],
    tolerance_ns: int,
) -> Tuple[List[int], int]:
    """Greedily pair two sorted timestamp streams by nearest neighbor.

    Uses a two-pointer merge: at each step the closest left/right pair is
    emitted (if within ``tolerance_ns``) and both pointers advance; otherwise
    the earlier timestamp is dropped as unpaired and its pointer advances.

    Args:
        left_ts_ns: Left camera frame timestamps (monotonic ns).
        right_ts_ns: Right camera frame timestamps (monotonic ns).
        tolerance_ns: Maximum absolute delta to accept a pairing.

    Returns:
        ``(deltas_ns, unpaired_count)`` where ``deltas_ns`` are the absolute
        timestamp deltas of accepted pairs and ``unpaired_count`` counts frames
        on either side that could not be paired within tolerance.
    """
    left = sorted(int(t) for t in left_ts_ns)
    right = sorted(int(t) for t in right_ts_ns)

    deltas: List[int] = []
    unpaired = 0
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        delta = abs(left[i] - right[j])
        if delta <= tolerance_ns:
            deltas.append(delta)
            i += 1
            j += 1
        elif left[i] < right[j]:
            # Left frame has no right partner within tolerance.
            unpaired += 1
            i += 1
        else:
            unpaired += 1
            j += 1

    # Any remaining frames on either side are unpaired.
    unpaired += (len(left) - i) + (len(right) - j)
    return deltas, unpaired


def _classify(
    p95_motion_in: float,
    max_motion_in: float,
    unpaired_fraction: float,
) -> Tuple[str, bool, str]:
    """Map measured skew to a verdict, pass flag, and recommendation."""
    if p95_motion_in <= 4.0 and max_motion_in <= 6.0 and unpaired_fraction <= 0.02:
        return (
            SYNC_VERDICT_GOOD,
            True,
            "Timing skew is within practical software tolerance for 30-60 mph tracking.",
        )
    if p95_motion_in <= 8.0 and max_motion_in <= 12.0 and unpaired_fraction <= 0.10:
        return (
            SYNC_VERDICT_WARN,
            True,
            "Timing skew is marginal; lower exposure latency or reduce per-camera "
            "jitter before relying on plate location.",
        )
    return (
        SYNC_VERDICT_POOR,
        False,
        "Timing skew is large enough to corrupt stereo geometry; reduce exposure, "
        "balance USB bandwidth across controllers, or use hardware-synchronized cameras.",
    )


def check_sync(
    left_ts_ns: Sequence[int],
    right_ts_ns: Sequence[int],
    tolerance_ms: float,
    max_speed_mph: float = 60.0,
) -> SyncCheckResult:
    """Measure left/right timestamp skew and produce a :class:`SyncCheckResult`.

    Args:
        left_ts_ns: Left camera frame capture timestamps (monotonic ns).
        right_ts_ns: Right camera frame capture timestamps (monotonic ns).
        tolerance_ms: Pairing tolerance in milliseconds (e.g. the configured
            ``StereoConfig.pairing_tolerance_ms``).
        max_speed_mph: Pitch speed used to convert timing skew to ball motion.

    Returns:
        A populated :class:`SyncCheckResult`. When there are no paired frames
        the verdict is ``UNKNOWN`` and ``passed`` is ``False``.
    """
    tolerance_ms = float(tolerance_ms)
    tolerance_ns = int(tolerance_ms * 1e6)
    deltas_ns, unpaired = pair_timestamps(left_ts_ns, right_ts_ns, tolerance_ns)

    if not deltas_ns:
        return SyncCheckResult(
            sample_count=0,
            unpaired_count=unpaired,
            mean_delta_ms=0.0,
            p95_delta_ms=0.0,
            max_delta_ms=0.0,
            jitter_ms=0.0,
            max_motion_in=0.0,
            tolerance_ms=tolerance_ms,
            max_speed_mph=float(max_speed_mph),
            verdict=SYNC_VERDICT_UNKNOWN,
            passed=False,
            recommendation="No frames could be paired within tolerance; check that both cameras stream.",
        )

    deltas_ms = np.asarray(deltas_ns, dtype=np.float64) / 1e6
    mean_delta = float(np.mean(deltas_ms))
    p95_delta = float(np.percentile(deltas_ms, 95))
    max_delta = float(np.max(deltas_ms))
    jitter = float(np.std(deltas_ms))

    total = len(deltas_ns) + unpaired
    unpaired_fraction = unpaired / max(total, 1)

    p95_motion = _motion_inches(p95_delta, max_speed_mph)
    max_motion = _motion_inches(max_delta, max_speed_mph)
    verdict, passed, recommendation = _classify(p95_motion, max_motion, unpaired_fraction)

    return SyncCheckResult(
        sample_count=len(deltas_ns),
        unpaired_count=unpaired,
        mean_delta_ms=mean_delta,
        p95_delta_ms=p95_delta,
        max_delta_ms=max_delta,
        jitter_ms=jitter,
        max_motion_in=max_motion,
        tolerance_ms=tolerance_ms,
        max_speed_mph=float(max_speed_mph),
        verdict=verdict,
        passed=passed,
        recommendation=recommendation,
    )

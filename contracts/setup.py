"""Typed result contracts for the stereo-rig setup state machine.

These dataclasses are durable, JSON-serializable records produced by the
individual setup steps (sync check, focus/exposure lock, overlap validation,
coarse rectification, ...). Keeping them as frozen contracts lets each setup
step be unit-tested in isolation with synthetic inputs and lets the wizard
persist a coherent setup profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

# Sync-check verdicts (ordered worst -> best is not implied; treat as labels).
SYNC_VERDICT_GOOD = "GOOD"
SYNC_VERDICT_WARN = "WARN"
SYNC_VERDICT_POOR = "POOR"
SYNC_VERDICT_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SyncCheckResult:
    """Result of the setup-time left/right timestamp synchronization check.

    Produced from two streams of per-camera frame capture timestamps (host
    monotonic nanoseconds). It reports the measured pairing skew and whether it
    is small enough to trust stereo geometry at the target pitch speed.

    Attributes:
        sample_count: Number of left/right frames that were paired.
        unpaired_count: Frames that could not be paired within the tolerance.
        mean_delta_ms: Mean absolute left/right timestamp delta, milliseconds.
        p95_delta_ms: 95th-percentile absolute delta, milliseconds.
        max_delta_ms: Maximum absolute delta, milliseconds.
        jitter_ms: Standard deviation of the deltas, milliseconds.
        max_motion_in: Ball travel (inches) implied by max_delta at max_speed_mph.
        tolerance_ms: Pairing tolerance used for the check, milliseconds.
        max_speed_mph: Pitch speed used to convert timing skew to ball motion.
        verdict: One of SYNC_VERDICT_{GOOD,WARN,POOR,UNKNOWN}.
        passed: True when the verdict is acceptable to proceed (GOOD or WARN).
        recommendation: Human-readable guidance for the operator.
    """

    sample_count: int
    unpaired_count: int
    mean_delta_ms: float
    p95_delta_ms: float
    max_delta_ms: float
    jitter_ms: float
    max_motion_in: float
    tolerance_ms: float
    max_speed_mph: float
    verdict: str
    passed: bool
    recommendation: str = ""

    def to_payload(self) -> Dict[str, object]:
        """Return a JSON-serializable dict for manifests/reports."""
        return {
            "sample_count": self.sample_count,
            "unpaired_count": self.unpaired_count,
            "mean_delta_ms": self.mean_delta_ms,
            "p95_delta_ms": self.p95_delta_ms,
            "max_delta_ms": self.max_delta_ms,
            "jitter_ms": self.jitter_ms,
            "max_motion_in": self.max_motion_in,
            "tolerance_ms": self.tolerance_ms,
            "max_speed_mph": self.max_speed_mph,
            "verdict": self.verdict,
            "passed": self.passed,
            "recommendation": self.recommendation,
        }

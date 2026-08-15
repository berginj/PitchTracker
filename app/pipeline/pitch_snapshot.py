"""Pitch-state value objects and snapshot assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from contracts import Frame, RayObservation, StereoObservation


class PitchPhase(Enum):
    """Pitch tracking phases with clear transitions."""

    INACTIVE = "inactive"
    RAMP_UP = "ramp_up"
    ACTIVE = "active"
    ENDING = "ending"
    FINALIZED = "finalized"


@dataclass
class PitchConfig:
    """Configuration for pitch detection."""

    min_active_frames: int = 5
    end_gap_frames: int = 10
    use_plate_gate: bool = True
    min_observations: int = 3
    min_duration_ms: float = 100.0
    pre_roll_ms: float = 300.0
    frame_rate: float = 30.0

    @property
    def frame_period_ns(self) -> int:
        """Calculate nanoseconds per frame."""
        return int(1_000_000_000 / self.frame_rate)

    @property
    def pre_roll_ns(self) -> int:
        """Pre-roll duration in nanoseconds."""
        return int(self.pre_roll_ms * 1_000_000)

    @property
    def min_duration_ns(self) -> int:
        """Minimum pitch duration in nanoseconds."""
        return int(self.min_duration_ms * 1_000_000)


@dataclass
class PitchData:
    """Pitch data copied for safe transfer outside the state machine."""

    pitch_index: int
    phase: PitchPhase
    start_ns: int
    end_ns: int
    first_detection_ns: int
    last_detection_ns: int
    observations: list[StereoObservation] = field(default_factory=list)
    ray_observations: list[RayObservation] = field(default_factory=list)
    pre_roll_frames: list[tuple[str, Frame]] = field(default_factory=list)
    active_frame_count: int = 0
    gap_frame_count: int = 0

    def duration_ns(self) -> int:
        """Calculate pitch duration."""
        return self.last_detection_ns - self.first_detection_ns if self.last_detection_ns > 0 else 0

    def is_valid(self, config: PitchConfig) -> tuple[bool, str]:
        """Check if pitch data is valid for finalization."""
        stereo_count = len(self.observations)
        ray_count = len(self.ray_observations)
        if stereo_count < config.min_observations and ray_count < config.min_observations:
            return (
                False,
                f"Too few observations: stereo={stereo_count}, rays={ray_count} < {config.min_observations}",
            )

        duration = self.duration_ns()
        if duration < config.min_duration_ns:
            return False, f"Too short: {duration / 1_000_000:.1f}ms < {config.min_duration_ms}ms"

        if self.start_ns < 0:
            return False, "Invalid start timestamp"

        return True, "Valid"


def assemble_pitch_snapshot(
    *,
    pitch_index: int,
    phase: PitchPhase,
    start_ns: int,
    end_ns: int,
    first_detection_ns: int,
    last_detection_ns: int,
    observations: Iterable[StereoObservation],
    ray_observations: Iterable[RayObservation],
    pre_roll_frames: Iterable[tuple[str, Frame]] = (),
    active_frame_count: int,
    gap_frame_count: int,
) -> PitchData:
    """Copy state-owned collections into a callback-safe pitch snapshot."""
    return PitchData(
        pitch_index=pitch_index,
        phase=phase,
        start_ns=start_ns,
        end_ns=end_ns,
        first_detection_ns=first_detection_ns,
        last_detection_ns=last_detection_ns,
        observations=list(observations),
        ray_observations=list(ray_observations),
        pre_roll_frames=list(pre_roll_frames),
        active_frame_count=active_frame_count,
        gap_frame_count=gap_frame_count,
    )

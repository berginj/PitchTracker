"""Robust pitch state machine with proper thread safety and data capture.

This is an improved version that addresses critical issues:
- Thread-safe operations
- Pre-roll buffering
- Ramp-up observation capture
- Accurate timing calculations
- Error handling
- State pattern design
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from contracts import Frame, StereoObservation

logger = logging.getLogger(__name__)


class PitchPhase(Enum):
    """Pitch tracking phases with clear transitions."""
    INACTIVE = "inactive"
    RAMP_UP = "ramp_up"  # Collecting initial detections
    ACTIVE = "active"    # Pitch confirmed, recording
    ENDING = "ending"    # Post-roll period
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
    frame_rate: float = 30.0  # FPS for timing calculations

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
    """Immutable pitch data for thread-safe transfer."""
    pitch_index: int
    phase: PitchPhase
    start_ns: int
    end_ns: int
    first_detection_ns: int
    last_detection_ns: int
    observations: List[StereoObservation] = field(default_factory=list)
    pre_roll_frames: List[tuple[str, Frame]] = field(default_factory=list)
    active_frame_count: int = 0
    gap_frame_count: int = 0

    def duration_ns(self) -> int:
        """Calculate pitch duration."""
        return self.last_detection_ns - self.first_detection_ns if self.last_detection_ns > 0 else 0

    def is_valid(self, config: PitchConfig) -> tuple[bool, str]:
        """Check if pitch data is valid for finalization."""
        if len(self.observations) < config.min_observations:
            return False, f"Too few observations: {len(self.observations)} < {config.min_observations}"

        duration = self.duration_ns()
        if duration < config.min_duration_ns:
            return False, f"Too short: {duration / 1_000_000:.1f}ms < {config.min_duration_ms}ms"

        if self.start_ns <= 0:
            return False, "Invalid start timestamp"

        return True, "Valid"


class PitchStateMachineV2:
    """Robust pitch state machine with thread safety and accurate data capture.

    Key improvements:
    - Thread-safe with RLock for all state access
    - Pre-roll buffering before pitch detection
    - Ramp-up observation capture
    - Accurate start/end timing
    - Error handling with state recovery
    - Minimum duration/observation filtering
    """

    def __init__(self, config: PitchConfig):
        """Initialize pitch state machine.

        Args:
            config: Pitch detection configuration
        """
        self._config = config
        self._lock = threading.RLock()

        # State
        self._phase = PitchPhase.INACTIVE
        self._pitch_index = 0

        # Timing
        self._first_detection_ns = 0
        self._last_detection_ns = 0
        self._active_frame_count = 0
        self._gap_frame_count = 0

        # Data collection
        self._observations: List[StereoObservation] = []
        self._ramp_up_observations: List[StereoObservation] = []

        # Pre-roll buffers (per camera)
        self._pre_roll_frames: dict[str, deque] = {
            "left": deque(maxlen=100),  # ~3 seconds at 30fps
            "right": deque(maxlen=100),
        }

        # Callbacks with error recovery
        self._on_pitch_start: Optional[Callable[[int, PitchData], None]] = None
        self._on_pitch_end: Optional[Callable[[PitchData], None]] = None

        # Event log for debugging
        self._event_log: deque = deque(maxlen=1000)

    def set_callbacks(
        self,
        on_pitch_start: Optional[Callable[[int, PitchData], None]] = None,
        on_pitch_end: Optional[Callable[[PitchData], None]] = None,
    ) -> None:
        """Set callbacks for pitch events.

        Args:
            on_pitch_start: Called when pitch starts, receives (pitch_index, PitchData)
            on_pitch_end: Called when pitch ends, receives PitchData
        """
        with self._lock:
            self._on_pitch_start = on_pitch_start
            self._on_pitch_end = on_pitch_end

    def buffer_frame(self, label: str, frame: Frame) -> None:
        """Buffer frame for pre-roll capture.

        This should be called for EVERY frame, not just when pitch is active.

        Args:
            label: Camera label ("left" or "right")
            frame: Frame to buffer
        """
        with self._lock:
            if label not in self._pre_roll_frames:
                logger.warning(f"Unknown camera label: {label}")
                return

            buffer = self._pre_roll_frames[label]
            buffer.append(frame)

            # Trim to pre-roll window
            cutoff_ns = frame.t_capture_monotonic_ns - self._config.pre_roll_ns
            while buffer and buffer[0].t_capture_monotonic_ns < cutoff_ns:
                buffer.popleft()

    def add_observation(self, obs: StereoObservation) -> None:
        """Add observation to current pitch.

        Safe to call at any time - will be stored appropriately based on phase.

        Args:
            obs: Stereo observation to add
        """
        with self._lock:
            if self._phase == PitchPhase.ACTIVE:
                self._observations.append(obs)
            elif self._phase == PitchPhase.RAMP_UP:
                self._ramp_up_observations.append(obs)
            # INACTIVE/ENDING/FINALIZED: observation is ignored

    def update(
        self,
        frame_ns: int,
        lane_count: int,
        plate_count: int,
        obs_count: int,
    ) -> None:
        """Update pitch state based on detection counts.

        Thread-safe state transitions.

        Args:
            frame_ns: Frame timestamp in nanoseconds
            lane_count: Number of detections in lane gate
            plate_count: Number of detections in plate gate
            obs_count: Number of stereo observations
        """
        with self._lock:
            # Determine if frame has relevant activity
            active = self._is_frame_active(lane_count, plate_count, obs_count)

            # Log event
            self._log_event("update", {
                "frame_ns": frame_ns,
                "phase": self._phase.value,
                "active": active,
                "obs_count": obs_count,
            })

            # State machine transitions
            if active:
                self._handle_active_frame(frame_ns)
            else:
                self._handle_inactive_frame(frame_ns)

    def force_end(self, current_ns: Optional[int] = None) -> None:
        """Force end current pitch if active.

        Args:
            current_ns: Current timestamp (uses last detection if not provided)
        """
        with self._lock:
            if self._phase in (PitchPhase.ACTIVE, PitchPhase.RAMP_UP):
                end_ns = current_ns or self._last_detection_ns or int(time.monotonic_ns())
                self._log_event("force_end", {"end_ns": end_ns})
                self._transition_to_finalized(end_ns)

    def reset(self) -> None:
        """Reset state machine for new session."""
        with self._lock:
            self._log_event("reset", {})
            self._phase = PitchPhase.INACTIVE
            self._pitch_index = 0
            self._first_detection_ns = 0
            self._last_detection_ns = 0
            self._active_frame_count = 0
            self._gap_frame_count = 0
            self._observations.clear()
            self._ramp_up_observations.clear()
            for buffer in self._pre_roll_frames.values():
                buffer.clear()

    def get_phase(self) -> PitchPhase:
        """Get current phase (thread-safe)."""
        with self._lock:
            return self._phase

    def get_pitch_index(self) -> int:
        """Get current pitch index (thread-safe)."""
        with self._lock:
            return self._pitch_index

    def update_config(self, config: PitchConfig) -> bool:
        """Update configuration.

        Args:
            config: New configuration

        Returns:
            True if updated, False if rejected (e.g., during active pitch)
        """
        with self._lock:
            if self._phase != PitchPhase.INACTIVE:
                logger.warning(f"Cannot update config during {self._phase.value} phase")
                return False

            self._config = config
            self._log_event("config_updated", {"config": config})
            return True

    # Private methods

    def _is_frame_active(self, lane_count: int, plate_count: int, obs_count: int) -> bool:
        """Determine if frame has relevant activity."""
        if self._config.use_plate_gate:
            return plate_count > 0 or obs_count > 0
        else:
            return lane_count > 0

    def _handle_active_frame(self, frame_ns: int) -> None:
        """Handle frame with detections."""
        self._gap_frame_count = 0
        self._active_frame_count += 1
        self._last_detection_ns = frame_ns

        # Track first detection
        if self._first_detection_ns == 0:
            self._first_detection_ns = frame_ns

        # State transitions
        if self._phase == PitchPhase.INACTIVE:
            self._transition_to_ramp_up(frame_ns)

        elif self._phase == PitchPhase.RAMP_UP:
            if self._active_frame_count >= self._config.min_active_frames:
                # Check minimum duration
                duration_ns = frame_ns - self._first_detection_ns
                if duration_ns >= self._config.min_duration_ns:
                    self._transition_to_active(frame_ns)
                else:
                    self._log_event("duration_check_failed", {
                        "duration_ms": duration_ns / 1_000_000,
                        "required_ms": self._config.min_duration_ms,
                    })

        elif self._phase == PitchPhase.ACTIVE:
            # Continue recording
            pass

        elif self._phase == PitchPhase.ENDING:
            # Activity resumed, cancel ending
            self._log_event("ending_cancelled", {"frame_ns": frame_ns})
            self._phase = PitchPhase.ACTIVE

    def _handle_inactive_frame(self, frame_ns: int) -> None:
        """Handle frame without detections."""
        if self._phase == PitchPhase.INACTIVE:
            # Reset counters
            self._active_frame_count = 0
            self._first_detection_ns = 0

        elif self._phase == PitchPhase.RAMP_UP:
            # False start, reset
            self._log_event("ramp_up_failed", {"frames": self._active_frame_count})
            self._phase = PitchPhase.INACTIVE
            self._active_frame_count = 0
            self._gap_frame_count = 0
            self._first_detection_ns = 0
            self._last_detection_ns = 0
            self._ramp_up_observations.clear()

        elif self._phase == PitchPhase.ACTIVE:
            # Start gap counting
            self._gap_frame_count += 1
            if self._gap_frame_count >= self._config.end_gap_frames:
                self._transition_to_finalized(frame_ns)

        elif self._phase == PitchPhase.ENDING:
            # Continue waiting for post-roll
            pass

    def _transition_to_ramp_up(self, frame_ns: int) -> None:
        """Transition from INACTIVE to RAMP_UP."""
        self._log_event("transition", {"to": "RAMP_UP", "frame_ns": frame_ns})
        self._phase = PitchPhase.RAMP_UP

    def _transition_to_active(self, frame_ns: int) -> None:
        """Transition from RAMP_UP to ACTIVE."""
        self._log_event("transition", {"to": "ACTIVE", "frame_ns": frame_ns})
        self._phase = PitchPhase.ACTIVE
        self._pitch_index += 1

        # Promote ramp-up observations to main observations
        self._observations.extend(self._ramp_up_observations)
        self._ramp_up_observations.clear()

        # Calculate actual start time (backtrack to first detection)
        start_ns = self._first_detection_ns

        # Capture pre-roll frames
        pre_roll_frames = self._capture_pre_roll()

        # Build pitch data
        pitch_data = PitchData(
            pitch_index=self._pitch_index,
            phase=self._phase,
            start_ns=start_ns,
            end_ns=0,  # Not ended yet
            first_detection_ns=self._first_detection_ns,
            last_detection_ns=self._last_detection_ns,
            observations=list(self._observations),
            pre_roll_frames=pre_roll_frames,
            active_frame_count=self._active_frame_count,
            gap_frame_count=0,
        )

        # Notify callback with error handling
        if self._on_pitch_start:
            try:
                self._on_pitch_start(self._pitch_index, pitch_data)
            except Exception as e:
                logger.error(f"Pitch start callback failed: {e}", exc_info=True)
                # Revert state
                self._phase = PitchPhase.RAMP_UP
                self._pitch_index -= 1
                self._observations.clear()
                self._observations.extend(pitch_data.observations)
                return

    def _transition_to_finalized(self, frame_ns: int) -> None:
        """Transition to FINALIZED and invoke end callback."""
        self._log_event("transition", {"to": "FINALIZED", "frame_ns": frame_ns})

        # Use last detection time, not current frame
        end_ns = self._last_detection_ns or frame_ns

        # Build final pitch data
        pitch_data = PitchData(
            pitch_index=self._pitch_index,
            phase=PitchPhase.FINALIZED,
            start_ns=self._first_detection_ns,
            end_ns=end_ns,
            first_detection_ns=self._first_detection_ns,
            last_detection_ns=self._last_detection_ns,
            observations=list(self._observations),
            pre_roll_frames=[],  # Already delivered at start
            active_frame_count=self._active_frame_count,
            gap_frame_count=self._gap_frame_count,
        )

        # Validate pitch data
        is_valid, reason = pitch_data.is_valid(self._config)
        if not is_valid:
            logger.warning(f"Pitch {self._pitch_index} rejected: {reason}")
            self._reset_for_next_pitch()
            return

        # Transition to finalized
        self._phase = PitchPhase.FINALIZED

        # Notify callback with error handling
        if self._on_pitch_end:
            try:
                self._on_pitch_end(pitch_data)
            except Exception as e:
                logger.error(f"Pitch end callback failed: {e}", exc_info=True)
                # State already finalized, can't revert

        # Reset for next pitch
        self._reset_for_next_pitch()

    def _capture_pre_roll(self) -> List[tuple[str, Frame]]:
        """Capture pre-roll frames from buffers.

        Returns:
            List of (camera_label, frame) tuples
        """
        pre_roll = []
        for label, buffer in self._pre_roll_frames.items():
            for frame in buffer:
                pre_roll.append((label, frame))
        return pre_roll

    def _reset_for_next_pitch(self) -> None:
        """Reset state for next pitch while maintaining session state."""
        self._phase = PitchPhase.INACTIVE
        self._first_detection_ns = 0
        self._last_detection_ns = 0
        self._active_frame_count = 0
        self._gap_frame_count = 0
        self._observations.clear()
        self._ramp_up_observations.clear()
        # Note: Don't reset pitch_index or pre-roll buffers

    def _log_event(self, event_type: str, data: dict) -> None:
        """Log event for debugging."""
        self._event_log.append({
            "timestamp": time.monotonic_ns(),
            "type": event_type,
            "data": data,
        })

    def get_event_log(self) -> List[dict]:
        """Get event log for debugging (thread-safe)."""
        with self._lock:
            return list(self._event_log)

"""Pitch state machine for tracking pitch lifecycle and transitions."""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from contracts import StereoObservation

logger = logging.getLogger(__name__)


class PitchStateMachine:
    """Manages pitch state transitions and detection lifecycle.

    Tracks pitch activity based on detection counts and triggers
    pitch start/end events based on configurable thresholds.

    State transitions:
    - inactive → active: When min_active_frames threshold is met
    - active → ending: When end_gap_frames of inactivity is detected
    - ending → inactive: After pitch is finalized
    """

    def __init__(
        self,
        min_active_frames: int,
        end_gap_frames: int,
        use_plate_gate: bool,
    ):
        """Initialize pitch state machine.

        Args:
            min_active_frames: Minimum frames with detections to start pitch
            end_gap_frames: Gap frames without detections to end pitch
            use_plate_gate: Whether to use plate gate (vs lane gate only)
        """
        self._min_active_frames = min_active_frames
        self._end_gap_frames = end_gap_frames
        self._use_plate_gate = use_plate_gate

        # State
        self._active = False
        self._active_frames = 0
        self._gap_frames = 0
        self._pitch_index = 0
        self._start_ns = 0
        self._end_ns = 0

        # Observations for current pitch
        self._observations: List[StereoObservation] = []

        # Callbacks
        self._on_pitch_start: Optional[Callable[[int, int], None]] = None
        self._on_pitch_end: Optional[Callable[[int, int, List[StereoObservation]], None]] = None

    def set_pitch_start_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set callback for pitch start.

        Args:
            callback: Function called when pitch starts, receives (pitch_index, start_ns)
        """
        self._on_pitch_start = callback

    def set_pitch_end_callback(
        self, callback: Callable[[int, int, List[StereoObservation]], None]
    ) -> None:
        """Set callback for pitch end.

        Args:
            callback: Function called when pitch ends, receives (end_ns, pitch_index, observations)
        """
        self._on_pitch_end = callback

    def update(self, frame_ns: int, lane_count: int, plate_count: int, obs_count: int) -> None:
        """Update pitch state based on detection counts.

        Args:
            frame_ns: Frame timestamp in nanoseconds
            lane_count: Number of detections in lane gate
            plate_count: Number of detections in plate gate
            obs_count: Number of stereo observations
        """
        # Determine if frame is "active" (has relevant detections)
        if self._use_plate_gate:
            active = plate_count > 0 or obs_count > 0
        else:
            active = lane_count > 0

        if active:
            # Reset gap counter
            self._gap_frames = 0
            self._active_frames += 1
            self._end_ns = frame_ns

            # Check if we should start a pitch
            if not self._active and self._active_frames >= self._min_active_frames:
                self._start_pitch(frame_ns)
        else:
            # No detections in this frame
            if self._active:
                # Pitch is active, count gap frames
                self._gap_frames += 1
                if self._gap_frames >= self._end_gap_frames:
                    # End gap threshold reached, finalize pitch
                    self._finalize_pitch(frame_ns)
            else:
                # Not active, reset active frame counter
                self._active_frames = 0

    def add_observation(self, obs: StereoObservation) -> None:
        """Add observation to current pitch.

        Args:
            obs: Stereo observation to add
        """
        if self._active:
            self._observations.append(obs)

    def is_active(self) -> bool:
        """Check if pitch is currently active.

        Returns:
            True if pitch is active, False otherwise
        """
        return self._active

    def get_pitch_index(self) -> int:
        """Get current pitch index.

        Returns:
            Pitch index (0-based)
        """
        return self._pitch_index

    def reset(self) -> None:
        """Reset state machine for new session."""
        self._active = False
        self._active_frames = 0
        self._gap_frames = 0
        self._pitch_index = 0
        self._start_ns = 0
        self._end_ns = 0
        self._observations = []

    def force_end(self) -> None:
        """Force end current pitch if active."""
        if self._active:
            self._finalize_pitch(self._end_ns or 0)

    def update_config(self, min_active_frames: int, end_gap_frames: int, use_plate_gate: bool) -> None:
        """Update configuration.

        Args:
            min_active_frames: Minimum frames with detections to start pitch
            end_gap_frames: Gap frames without detections to end pitch
            use_plate_gate: Whether to use plate gate
        """
        self._min_active_frames = min_active_frames
        self._end_gap_frames = end_gap_frames
        self._use_plate_gate = use_plate_gate

    def _start_pitch(self, frame_ns: int) -> None:
        """Start a new pitch.

        Args:
            frame_ns: Frame timestamp when pitch started
        """
        self._active = True
        self._start_ns = frame_ns
        self._pitch_index += 1
        self._observations = []

        # Notify callback
        if self._on_pitch_start:
            self._on_pitch_start(self._pitch_index, frame_ns)

    def _finalize_pitch(self, frame_ns: int) -> None:
        """Finalize current pitch.

        Args:
            frame_ns: Frame timestamp when pitch ended
        """
        self._active = False
        self._active_frames = 0
        self._gap_frames = 0
        self._end_ns = frame_ns

        # Notify callback with observations
        if self._on_pitch_end:
            self._on_pitch_end(frame_ns, self._pitch_index, list(self._observations))

        # Clear observations
        self._observations = []

"""Pitch event coordination for the pipeline orchestrator.

Handles observation routing, pitch state machine callbacks, field-coordinate
transforms, and EventBus subscription lifecycle. Extracted from
PipelineOrchestrator to keep that file under 500 lines.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional, TYPE_CHECKING

from app.events.event_bus import EventBus
from app.events.event_types import (
    ObservationDetectedEvent,
    PitchEndEvent,
    PitchStartEvent,
    RayObservationDetectedEvent,
    StereoFrameProcessedEvent,
)
from app.pipeline.pitch_tracking_v2 import PitchData, PitchStateMachineV2
from app.services.rig_profile import RigProfile
from configs.settings import AppConfig
from contracts import StereoObservation
from log_config.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class EventCoordinator:
    """Routes observations to the pitch state machine and publishes lifecycle events.

    This collaborator is owned by ``PipelineOrchestrator`` and must not be used
    independently.  It holds references to the EventBus, pitch tracker, rig
    profile, and config that the orchestrator provides.
    """

    def __init__(
        self,
        event_bus: EventBus,
    ) -> None:
        self._event_bus = event_bus
        self._pitch_tracker: Optional[PitchStateMachineV2] = None
        self._active_rig_profile: Optional[RigProfile] = None
        self._config: Optional[AppConfig] = None
        self._latest_observation: Optional[StereoObservation] = None

    # --- Mutable state setters (called by orchestrator) ---

    def set_pitch_tracker(self, tracker: Optional[PitchStateMachineV2]) -> None:
        self._pitch_tracker = tracker

    def set_rig_profile(self, profile: Optional[RigProfile]) -> None:
        self._active_rig_profile = profile

    def set_config(self, config: Optional[AppConfig]) -> None:
        self._config = config

    @property
    def latest_observation(self) -> Optional[StereoObservation]:
        return self._latest_observation

    # --- Event handlers ---

    def on_observation_detected(self, event: ObservationDetectedEvent) -> None:
        """Feed stereo observations to the pitch state machine."""
        try:
            observation = self._to_field_coordinates(event.observation)
            self._latest_observation = observation
            if self._pitch_tracker is not None:
                self._pitch_tracker.add_observation(observation)
        except Exception as e:
            logger.error(f"Error handling observation: {e}", exc_info=True)

    def on_ray_observation_detected(self, event: RayObservationDetectedEvent) -> None:
        """Handle per-camera ray observations when ray trajectory modes are enabled."""
        try:
            if not self._ray_modes_enabled() or self._pitch_tracker is None:
                return
            self._pitch_tracker.add_ray_observation(event.observation)
        except Exception as e:
            logger.error(f"Error handling ray observation: {e}", exc_info=True)

    def on_stereo_frame_processed(self, event: StereoFrameProcessedEvent) -> None:
        """Advance pitch lifecycle exactly once for each processed pair."""
        try:
            if self._pitch_tracker is None:
                return
            self._pitch_tracker.update(
                frame_ns=event.timestamp_ns,
                lane_count=event.lane_count,
                plate_count=event.plate_count,
                obs_count=len(event.observations),
            )
        except Exception as e:
            logger.error(f"Error handling stereo frame pair: {e}", exc_info=True)

    def on_pitch_start(self, pitch_index: int, pitch_data: PitchData) -> None:
        """Publish PitchStartEvent to EventBus."""
        try:
            event = PitchStartEvent(
                pitch_id=make_pitch_id(pitch_index),
                pitch_index=pitch_index,
                timestamp_ns=pitch_data.start_ns,
            )
            self._event_bus.publish(event)
            logger.info(f"Pitch started: {pitch_index}")
        except Exception as e:
            logger.error(f"Error handling pitch start: {e}", exc_info=True)

    def on_pitch_end(self, pitch_data: PitchData) -> None:
        """Publish PitchEndEvent to EventBus."""
        try:
            event = PitchEndEvent(
                pitch_id=make_pitch_id(pitch_data.pitch_index),
                observations=pitch_data.observations,
                timestamp_ns=pitch_data.end_ns,
                duration_ns=pitch_data.duration_ns(),
                ray_observations=pitch_data.ray_observations,
                coordinate_frame=(
                    "field"
                    if self._active_rig_profile
                    and self._active_rig_profile.field_transform.get("matrix_4x4")
                    else "camera"
                ),
                rig_profile_id=(
                    self._active_rig_profile.profile_id
                    if self._active_rig_profile
                    else None
                ),
            )
            self._event_bus.publish(event)
            logger.info(
                f"Pitch ended: {pitch_data.pitch_index}, "
                f"{len(pitch_data.observations)} observations"
            )
        except Exception as e:
            logger.error(f"Error handling pitch end: {e}", exc_info=True)

    # --- Subscription lifecycle ---

    def subscribe(self) -> None:
        """Subscribe to observation and frame events on the EventBus."""
        self._event_bus.subscribe(
            ObservationDetectedEvent, self.on_observation_detected
        )
        self._event_bus.subscribe(
            RayObservationDetectedEvent, self.on_ray_observation_detected
        )
        self._event_bus.subscribe(
            StereoFrameProcessedEvent, self.on_stereo_frame_processed
        )
        logger.info("PipelineOrchestrator subscribed to ObservationDetectedEvent")

    def unsubscribe(self) -> None:
        """Unsubscribe from observation and frame events."""
        self._event_bus.unsubscribe(
            ObservationDetectedEvent, self.on_observation_detected
        )
        self._event_bus.unsubscribe(
            RayObservationDetectedEvent, self.on_ray_observation_detected
        )
        self._event_bus.unsubscribe(
            StereoFrameProcessedEvent, self.on_stereo_frame_processed
        )
        logger.info(
            "PipelineOrchestrator unsubscribed from ObservationDetectedEvent"
        )

    # --- Helpers ---

    def _to_field_coordinates(
        self, observation: StereoObservation
    ) -> StereoObservation:
        """Apply the active rig's validated camera-to-field transform."""
        if self._active_rig_profile is None:
            return observation
        matrix = (self._active_rig_profile.field_transform or {}).get(
            "matrix_4x4"
        )
        if not matrix:
            return observation
        point = (observation.X, observation.Y, observation.Z, 1.0)
        transformed = [
            sum(float(matrix[row][col]) * point[col] for col in range(4))
            for row in range(3)
        ]
        covariance = observation.covariance
        transformed_covariance = covariance
        if covariance is not None:
            rotation = [
                [float(matrix[row][col]) for col in range(3)]
                for row in range(3)
            ]
            rotated = [
                [
                    sum(
                        rotation[row][i]
                        * float(covariance[i][j])
                        * rotation[col][j]
                        for i in range(3)
                        for j in range(3)
                    )
                    for col in range(3)
                ]
                for row in range(3)
            ]
            transformed_covariance = tuple(
                tuple(value for value in row) for row in rotated
            )
        return replace(
            observation,
            X=transformed[0],
            Y=transformed[1],
            Z=transformed[2],
            covariance=transformed_covariance,
        )

    def _ray_modes_enabled(self) -> bool:
        if self._config is None or getattr(self._config, "trajectory", None) is None:
            return False
        modes = [
            self._config.trajectory.primary_mode,
            *self._config.trajectory.compare_modes,
        ]
        return any(mode.startswith("ray_") for mode in modes)

    def _ray_modes_drive_pitch(self) -> bool:
        return bool(
            self._config is not None
            and getattr(self._config, "trajectory", None) is not None
            and self._config.trajectory.primary_mode.startswith("ray_")
        )


def make_pitch_id(pitch_index: int) -> str:
    """Format a pitch index into the canonical pitch ID string."""
    return f"pitch_{pitch_index:05d}"

"""Stereo, ray, and evidence event publication collaborator."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, List

from app.events.event_metadata import make_event_metadata
from app.events.event_types import (
    FrameProcessingOpportunityEvent,
    FrameProcessingOutcomeEvent,
    ObservationDetectedEvent,
    PairingOutcomeEvent,
    RayObservationDetectedEvent,
    StereoAssociationOutcomeEvent,
    StereoFrameProcessedEvent,
)
from app.pipeline.detection.decision_ids import stereo_pair_id
from contracts import Detection, Frame, RayObservation, StereoObservation
from contracts.evidence import PairingOutcomeEvidence
from log_config.logger import get_logger
from stereo.association import pair_timing

if TYPE_CHECKING:
    from app.services.detection.implementation import DetectionServiceImpl

logger = get_logger(__name__)


class DetectionEventPublisher:
    """Publish detection decisions without owning pipeline algorithms."""

    def __init__(self, service: DetectionServiceImpl) -> None:
        self._service = service

    def publish_frame_opportunity(self, event: FrameProcessingOpportunityEvent) -> None:
        self._service._event_bus.publish(
            replace(event, bindings=self._service._decision_bindings("detection_pipeline", "2"))
        )

    def publish_frame_outcome(self, event: FrameProcessingOutcomeEvent) -> None:
        self._service._event_bus.publish(
            replace(event, bindings=self._service._decision_bindings("detection_pipeline", "2"))
        )

    def on_pairing_outcome(self, outcome: PairingOutcomeEvidence) -> None:
        service = self._service
        timestamp_ns = (
            outcome.left_timestamp_ns
            if outcome.left_timestamp_ns is not None
            else outcome.right_timestamp_ns or 0
        )
        with service._lock:
            service._pairing_frame_count += outcome.frame_count
            if outcome.status == "UNMATCHED":
                reason = outcome.reason_codes[0] if outcome.reason_codes else "UNSPECIFIED"
                service._pairing_unmatched_counts[reason] += outcome.frame_count
            session_id = service._session_id
        service._event_bus.publish(
            PairingOutcomeEvent(
                outcome,
                bindings=service._decision_bindings(f"{outcome.pairing_mode}_pairing", "2"),
                metadata=make_event_metadata(
                    "PairingOutcomeEvent",
                    correlation_id=outcome.outcome_id,
                    timestamp_ns=timestamp_ns,
                    session_id=session_id,
                ),
            )
        )

    def on_association_outcome(self, event: StereoAssociationOutcomeEvent) -> None:
        service = self._service
        version = "2" if event.primary_algorithm == "global_v2" else "1"
        with service._lock:
            session_id = service._session_id
        service._event_bus.publish(
            replace(
                event,
                bindings=service._decision_bindings(event.primary_algorithm, version),
                metadata=make_event_metadata(
                    "StereoAssociationOutcomeEvent",
                    correlation_id=event.pair_id,
                    timestamp_ns=event.timestamp_ns,
                    session_id=session_id,
                ),
            )
        )

    def on_stereo_pair(
        self,
        left_frame: Frame,
        right_frame: Frame,
        left_detections: List[Detection],
        right_detections: List[Detection],
        observations: List[StereoObservation],
        lane_count: int,
        plate_count: int,
    ) -> None:
        try:
            self._publish_stereo_pair(
                left_frame,
                right_frame,
                left_detections,
                right_detections,
                observations,
                lane_count,
                plate_count,
            )
        except Exception as exc:
            logger.error(f"Error handling stereo pair: {exc}", exc_info=True)

    def _publish_stereo_pair(
        self,
        left_frame: Frame,
        right_frame: Frame,
        left_detections: List[Detection],
        right_detections: List[Detection],
        observations: List[StereoObservation],
        lane_count: int,
        plate_count: int,
    ) -> None:
        service = self._service
        timing = pair_timing(
            left_frame.t_capture_monotonic_ns,
            right_frame.t_capture_monotonic_ns,
            int(getattr(service._config.stereo, "time_sync_offset_ns", 0)),
        )
        pair_skew_ms = timing.adjusted_skew_ns / 1e6
        service._last_drift_status = service._sync_drift_monitor.update(pair_skew_ms)
        reasons = _pair_rejection_reasons(
            pair_skew_ms,
            float(service._config.stereo.pairing_tolerance_ms),
            left_detections,
            right_detections,
            observations,
        )
        pair_id = stereo_pair_id(left_frame, right_frame)
        with service._lock:
            service._pair_count += 1
            service._pair_rejection_counts.update(reasons)
            session_id = service._session_id
        service._event_bus.publish(
            StereoFrameProcessedEvent(
                pair_id=pair_id,
                timestamp_ns=timing.timestamp_ns,
                left_timestamp_ns=left_frame.t_capture_monotonic_ns,
                right_timestamp_ns=right_frame.t_capture_monotonic_ns,
                left_frame_index=left_frame.frame_index,
                right_frame_index=right_frame.frame_index,
                lane_count=lane_count,
                plate_count=plate_count,
                observations=tuple(observations),
                rejection_reasons=tuple(reasons),
                adjusted_left_timestamp_ns=timing.adjusted_left_ns,
                adjusted_right_timestamp_ns=timing.adjusted_right_ns,
                time_sync_offset_ns=timing.right_offset_ns,
                metadata=make_event_metadata(
                    "StereoFrameProcessedEvent",
                    correlation_id=pair_id,
                    timestamp_ns=timing.timestamp_ns,
                    session_id=session_id,
                ),
            )
        )
        self._publish_observations(observations, pair_id, session_id)

    def _publish_observations(
        self, observations: List[StereoObservation], pair_id: str, session_id: str | None
    ) -> None:
        service = self._service
        for observation in observations:
            with service._lock:
                service._latest_observations.append(observation)
                callbacks = list(service._observation_callbacks)
            service._event_bus.publish(
                ObservationDetectedEvent(
                    observation=observation,
                    timestamp_ns=observation.t_ns,
                    confidence=observation.confidence,
                    metadata=make_event_metadata(
                        "ObservationDetectedEvent",
                        correlation_id=pair_id,
                        timestamp_ns=observation.t_ns,
                        session_id=session_id,
                    ),
                )
            )
            for callback in callbacks:
                try:
                    callback(observation)
                except Exception as exc:
                    logger.error(f"Observation callback error: {exc}", exc_info=True)
        with service._lock:
            service._observation_count += len(observations)

    def on_ray_observations(
        self,
        camera_id: str,
        frame: Frame,
        observations: List[RayObservation],
        lane_count: int,
        plate_count: int,
    ) -> None:
        del lane_count, plate_count
        service = self._service
        try:
            with service._lock:
                session_id = service._session_id
            for observation in observations:
                service._event_bus.publish(
                    RayObservationDetectedEvent(
                        observation=observation,
                        timestamp_ns=observation.t_ns,
                        confidence=observation.confidence,
                        metadata=make_event_metadata(
                            "RayObservationDetectedEvent",
                            correlation_id=f"{camera_id}_{frame.frame_index}",
                            timestamp_ns=observation.t_ns,
                            camera_id=camera_id,
                            session_id=session_id,
                        ),
                    )
                )
        except Exception as exc:
            logger.error(f"Error handling ray observations: {exc}", exc_info=True)


def _pair_rejection_reasons(pair_skew_ms, tolerance_ms, left, right, observations) -> list[str]:
    if pair_skew_ms > tolerance_ms:
        return ["PAIR_SKEW_OUT_OF_TOLERANCE"]
    if not left and not right:
        return ["NO_CANDIDATES"]
    if not observations:
        return ["NO_VALID_STEREO_ASSOCIATION"]
    return []

"""Frame detection and tracklet enrichment collaborator."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, List

from app.pipeline.detection.decision_ids import canonicalize_detection_ids
from contracts import Detection, Frame
from log_config.logger import get_logger

if TYPE_CHECKING:
    from app.events.event_types import FrameCapturedEvent
    from app.services.detection.implementation import DetectionServiceImpl

logger = get_logger(__name__)


class DetectionFrameHandler:
    """Handle asynchronous frame input and detection results."""

    def __init__(self, service: DetectionServiceImpl) -> None:
        self._service = service

    def on_frame_captured(self, event: FrameCapturedEvent) -> None:
        try:
            self._service.process_frame(event.camera_id, event.frame)
        except Exception as exc:
            logger.error(f"Error handling frame capture: {exc}", exc_info=True)

    def detect_frame(self, camera_id: str, frame: Frame) -> List[Detection]:
        service = self._service
        detector = service._left_detector if camera_id == "left" else service._right_detector
        if detector is None:
            raise RuntimeError(f"Detector is not configured for {camera_id} camera")
        detections = canonicalize_detection_ids(frame, detector.detect(frame))
        with service._lock:
            service._detection_count += len(detections)
        return detections

    def on_stereo_result(self, camera_id: str, frame: Frame, detections: List[Detection]) -> None:
        service = self._service
        try:
            if service._processor is None:
                return
            enriched = self._enrich_detections(camera_id, detections)
            detections[:] = enriched
            eligible = [item for item in enriched if item.association_eligible]
            service._processor.process_detection_result(camera_id, frame, eligible)
        except Exception as exc:
            logger.error(f"Error processing stereo result: {exc}", exc_info=True)
            raise

    def _enrich_detections(self, camera_id: str, detections: List[Detection]) -> List[Detection]:
        service = self._service
        with service._tracklet_lock:
            previous_ids = {track.tracklet_id for track in service._tracklet_builder.active(camera_id)}
            tracks, decisions = service._tracklet_builder.update_with_decisions(camera_id, detections)
            current_ids = {track.tracklet_id for track in tracks}
            service._tracklet_updates += len(detections)
            service._tracklet_starts += len(current_ids - previous_ids)
        min_length = max(1, int(service._config.detector.min_consecutive))
        track_lengths = {track.tracklet_id: len(track.detections) for track in tracks}
        decision_by_candidate = {decision.candidate_id: decision for decision in decisions}
        return [
            _enrich_detection(detection, decision_by_candidate, track_lengths, min_length)
            for detection in detections
        ]


def _enrich_detection(detection, decision_by_candidate, track_lengths, min_length):
    decision = decision_by_candidate.get(detection.candidate_id)
    tracklet_id = None if decision is None else decision.tracklet_id
    eligible = bool(tracklet_id is not None and track_lengths.get(tracklet_id, 0) >= min_length)
    return replace(
        detection,
        tracklet_id=tracklet_id,
        tracklet_action=None if decision is None else decision.action,
        association_eligible=eligible,
        rejection_reasons=() if eligible else ("TRACKLET_RAMP_UP",),
    )

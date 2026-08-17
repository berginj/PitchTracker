"""EventBus handlers and subscription management for RecordingService."""

from __future__ import annotations

from typing import Dict

from app.events.event_types import (
    FrameCapturedEvent,
    FrameProcessingOpportunityEvent,
    FrameProcessingOutcomeEvent,
    ObservationDetectedEvent,
    PairingOutcomeEvent,
    PitchAnalyzedEvent,
    PitchEndEvent,
    PitchStartEvent,
    StereoAssociationOutcomeEvent,
    StereoFrameProcessedEvent,
)
from log_config.logger import get_logger
from app.services.recording.state import RecordingServiceState

logger = get_logger(__name__)


class EventHandlersMixin(RecordingServiceState):
    """EventBus event handlers and subscription lifecycle."""

    def _on_frame_captured(self: "RecordingServiceState", event: FrameCapturedEvent) -> None:
        """Handle FrameCapturedEvent from EventBus."""
        try:
            self.record_frame(event.camera_id, event.frame)
        except Exception as e:
            logger.error(f"Error recording frame: {e}", exc_info=True)

    def _on_observation_detected(
        self: "RecordingServiceState", event: ObservationDetectedEvent
    ) -> None:
        """Handle ObservationDetectedEvent from EventBus."""
        try:
            if self._pitch_active:
                self.record_observation(event.observation)
        except Exception as e:
            logger.error(f"Error recording observation: {e}", exc_info=True)

    def _on_stereo_frame_processed(
        self: "RecordingServiceState", event: StereoFrameProcessedEvent
    ) -> None:
        """Record pair-level timing and rejection evidence for the active pitch."""
        try:
            with self._lock:
                recorder = self._pitch_recorder if self._pitch_active else None
            if recorder is not None:
                recorder.add_stereo_pair(event)
        except Exception as e:
            logger.error(f"Error recording stereo-pair evidence: {e}", exc_info=True)

    def _on_decision_evidence(self: "RecordingServiceState", event) -> None:
        """Queue required replay evidence without doing disk I/O on its publisher."""
        with self._lock:
            journal = self._decision_journal
        if journal is None:
            return
        try:
            result = journal.submit_event(event, required=True)
        except Exception:
            logger.exception("Decision evidence journal submission failed")
            with self._lock:
                self._decision_evidence_incomplete = True
            return
        if not result.accepted:
            with self._lock:
                self._decision_evidence_incomplete = True
            logger.error(
                "Required decision evidence was not journaled at sequence %s",
                result.sequence,
            )

    def _on_pitch_start(self: "RecordingServiceState", event: PitchStartEvent) -> None:
        """Handle PitchStartEvent from EventBus."""
        try:
            with self._lock:
                self._pitch_lifecycle_metadata[event.pitch_id] = {
                    "pitch_start": event.metadata.to_dict(),
                }
            self.start_pitch(event.pitch_id)
        except Exception as e:
            logger.error(f"Error starting pitch recording: {e}", exc_info=True)

    def _on_pitch_end(self: "RecordingServiceState", event: PitchEndEvent) -> None:
        """Handle PitchEndEvent from EventBus."""
        try:
            logger.debug("PitchEndEvent received for %s", event.pitch_id)
            with self._lock:
                lifecycle = self._pitch_lifecycle_metadata.get(event.pitch_id)
                if lifecycle is not None:
                    lifecycle["pitch_end"] = event.metadata.to_dict()
                recorder = (
                    self._pitch_recorder
                    if self._pitch_active and self._current_pitch_id == event.pitch_id
                    else None
                )
            if recorder is not None:
                recorder.add_analysis_observations(
                    list(event.observations),
                    coordinate_frame=event.coordinate_frame,
                    rig_profile_id=event.rig_profile_id,
                )
                recorder.end_pitch(event.timestamp_ns)
        except Exception as e:
            logger.error(f"Error handling pitch end: {e}", exc_info=True)

    def _on_pitch_analyzed(self: "RecordingServiceState", event: PitchAnalyzedEvent) -> None:
        """Handle PitchAnalyzedEvent from EventBus."""
        try:
            with self._lock:
                recorder = None
                if self._pitch_active and self._current_pitch_id == event.pitch_id:
                    recorder = self._pitch_recorder
                if recorder is None:
                    recorder = self._completed_pitch_recorders.get(event.pitch_id)
                lifecycle = self._pitch_lifecycle_metadata.pop(event.pitch_id, {})

            if recorder is None:
                logger.warning(
                    "No pitch recorder available for analyzed pitch %s", event.pitch_id
                )
                return

            lifecycle["pitch_analyzed"] = event.metadata.to_dict()
            self._validate_lifecycle_metadata(event.pitch_id, lifecycle)
            recorder.write_manifest(
                event.summary,
                self._config_path,
                event_metadata=lifecycle,
            )

            with self._lock:
                self._completed_pitch_recorders.pop(event.pitch_id, None)
        except Exception as e:
            logger.error(f"Error writing pitch manifest: {e}", exc_info=True)

    def _validate_lifecycle_metadata(
        self: "RecordingServiceState", pitch_id: str, lifecycle: Dict[str, dict]
    ) -> None:
        """Log warnings if session_id/pitch_id are inconsistent across lifecycle."""
        session_ids = set()
        pitch_ids = set()
        for phase in ("pitch_start", "pitch_end", "pitch_analyzed"):
            meta = lifecycle.get(phase)
            if meta is None:
                continue
            sid = meta.get("session_id")
            pid = meta.get("pitch_id")
            if sid is not None:
                session_ids.add(sid)
            if pid is not None:
                pitch_ids.add(pid)
        if len(session_ids) > 1:
            logger.warning(
                "Pitch %s lifecycle has inconsistent session_ids: %s",
                pitch_id,
                session_ids,
            )
        if len(pitch_ids) > 1:
            logger.warning(
                "Pitch %s lifecycle has inconsistent pitch_ids: %s",
                pitch_id,
                pitch_ids,
            )

    def _subscribe_to_events(self: "RecordingServiceState") -> None:
        """Subscribe to EventBus events."""
        if self._subscribed:
            return

        self._event_bus.subscribe(FrameCapturedEvent, self._on_frame_captured)
        self._event_bus.subscribe(ObservationDetectedEvent, self._on_observation_detected)
        self._event_bus.subscribe(PitchStartEvent, self._on_pitch_start)
        self._event_bus.subscribe(PitchEndEvent, self._on_pitch_end)
        self._event_bus.subscribe(PitchAnalyzedEvent, self._on_pitch_analyzed)
        self._event_bus.subscribe(
            StereoFrameProcessedEvent, self._on_stereo_frame_processed
        )
        self._event_bus.subscribe(
            FrameProcessingOpportunityEvent, self._on_decision_evidence
        )
        self._event_bus.subscribe(FrameProcessingOutcomeEvent, self._on_decision_evidence)
        self._event_bus.subscribe(PairingOutcomeEvent, self._on_decision_evidence)
        self._event_bus.subscribe(
            StereoAssociationOutcomeEvent, self._on_decision_evidence
        )

        self._subscribed = True
        logger.info("RecordingService subscribed to EventBus")

    def _unsubscribe_from_events(self: "RecordingServiceState") -> None:
        """Unsubscribe from EventBus events."""
        if not self._subscribed:
            return

        self._event_bus.unsubscribe(FrameCapturedEvent, self._on_frame_captured)
        self._event_bus.unsubscribe(
            ObservationDetectedEvent, self._on_observation_detected
        )
        self._event_bus.unsubscribe(PitchStartEvent, self._on_pitch_start)
        self._event_bus.unsubscribe(PitchEndEvent, self._on_pitch_end)
        self._event_bus.unsubscribe(PitchAnalyzedEvent, self._on_pitch_analyzed)
        self._event_bus.unsubscribe(
            StereoFrameProcessedEvent, self._on_stereo_frame_processed
        )
        self._event_bus.unsubscribe(
            FrameProcessingOpportunityEvent, self._on_decision_evidence
        )
        self._event_bus.unsubscribe(
            FrameProcessingOutcomeEvent, self._on_decision_evidence
        )
        self._event_bus.unsubscribe(PairingOutcomeEvent, self._on_decision_evidence)
        self._event_bus.unsubscribe(
            StereoAssociationOutcomeEvent, self._on_decision_evidence
        )

        self._subscribed = False
        logger.info("RecordingService unsubscribed from EventBus")

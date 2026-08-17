"""Pitch terminal analysis — converts PitchEndEvent into exactly-one terminal result.

This module owns the analysis-side event handler logic: invoking PitchAnalyzer,
constructing unavailable verdicts, publishing PitchAnalyzedEvent through the
EventBus, and coordinating with SessionAggregator and RefinementAccumulator.

Thread-safety: _publish_terminal_summary acquires the service lock via the
aggregator; callers must pass the lock explicitly.
"""

from __future__ import annotations

import threading
from typing import Optional

from app.contracts import PitchSummary
from app.events.event_bus import EventBus
from app.events.event_metadata import make_event_metadata
from app.events.event_types import PitchAnalyzedEvent, PitchEndEvent
from app.pipeline.analysis.pitch_summary import PitchAnalyzer
from app.services.analysis.refinement import RefinementAccumulator
from app.services.analysis.session_aggregation import SessionAggregator
from contracts.quality import MeasurementStatus
from log_config.logger import get_logger

logger = get_logger(__name__)


class PitchTerminalHandler:
    """Handles pitch end events and publishes exactly-one terminal result."""

    def __init__(
        self,
        event_bus: EventBus,
        analyzer: PitchAnalyzer,
        aggregator: SessionAggregator,
        refiner: RefinementAccumulator,
        lock: threading.Lock,
    ) -> None:
        self._event_bus = event_bus
        self._analyzer = analyzer
        self._aggregator = aggregator
        self._refiner = refiner
        self._lock = lock

    def handle_pitch_end(self, event: PitchEndEvent) -> None:
        """Analyze pitch and publish terminal result.

        Called from the analysis worker thread.
        """
        if not event.observations:
            logger.warning(
                "Pitch %s has no observations; publishing unavailable verdict",
                event.pitch_id,
            )
            self._publish_unavailable_result(event, "NO_OBSERVATIONS")
            return

        try:
            summary = self._analyzer.analyze_pitch(
                pitch_id=event.pitch_id,
                start_ns=event.timestamp_ns - event.duration_ns,
                end_ns=event.timestamp_ns,
                observations=event.observations,
                ray_observations=event.ray_observations,
            )
            self._publish_terminal_summary(event, summary)
        except Exception as exc:
            logger.error("Error analyzing pitch %s: %s", event.pitch_id, exc, exc_info=True)
            try:
                self._publish_unavailable_result(
                    event,
                    "ANALYSIS_PIPELINE_EXCEPTION",
                    exception_type=type(exc).__name__,
                )
            except Exception:
                logger.exception(
                    "Failed to publish unavailable verdict for pitch %s", event.pitch_id
                )
            raise

        # Online refinement is advisory; failure must not create a second terminal result.
        if self._refiner.enabled and summary.trajectory_confidence:
            try:
                self._refiner.accumulate(summary, event)
            except Exception as ref_error:
                logger.warning("Error accumulating trajectory for refinement: %s", ref_error)

    def _publish_unavailable_result(
        self,
        event: PitchEndEvent,
        reason_code: str,
        *,
        exception_type: Optional[str] = None,
    ) -> bool:
        """Publish a claim-free terminal result for an unanalyzable pitch."""
        diagnostics = {
            "reason_codes": [reason_code],
            "analysis_terminal_status": "UNAVAILABLE",
            "strike_available": False,
            "speed_available": False,
            "movement_available": False,
            "movement_validated": False,
            "plate_crossing_available": False,
            "claim_fields_suppressed": [
                "is_strike",
                "speed_mph",
                "run_in",
                "rise_in",
                "plate_crossing",
            ],
        }
        if exception_type:
            diagnostics["exception_type"] = exception_type
        summary = PitchSummary(
            pitch_id=event.pitch_id,
            t_start_ns=max(0, event.timestamp_ns - event.duration_ns),
            t_end_ns=event.timestamp_ns,
            is_strike=False,
            zone_row=None,
            zone_col=None,
            run_in=0.0,
            rise_in=0.0,
            speed_mph=None,
            rotation_rpm=None,
            sample_count=len(event.observations),
            observation_quality_status="UNAVAILABLE",
            observation_rejection_reasons=[reason_code],
            measurement_status=MeasurementStatus.UNAVAILABLE,
            speed_source=None,
            correction_records=[],
            quality_diagnostics=diagnostics,
        )
        return self._publish_terminal_summary(event, summary)

    def _publish_terminal_summary(self, event: PitchEndEvent, summary: PitchSummary) -> bool:
        """Atomically aggregate and publish exactly one terminal event per pitch."""
        with self._lock:
            if self._aggregator.is_duplicate(event.pitch_id):
                logger.warning(
                    "Ignoring duplicate terminal analysis result for pitch %s",
                    event.pitch_id,
                )
                return False

            session_summary = self._aggregator.aggregate(
                event.pitch_id, summary, list(event.observations)
            )

        sid = session_summary.session_id if session_summary else None
        self._event_bus.publish(
            PitchAnalyzedEvent(
                pitch_id=event.pitch_id,
                summary=summary,
                session_summary=session_summary,
                metadata=make_event_metadata(
                    "PitchAnalyzedEvent",
                    correlation_id=event.pitch_id,
                    timestamp_ns=event.timestamp_ns,
                    pitch_id=event.pitch_id,
                    session_id=sid,
                ),
            )
        )
        logger.info(
            "Pitch analysis terminal result: pitch=%s status=%s reasons=%s",
            event.pitch_id,
            summary.measurement_status,
            (summary.quality_diagnostics or {}).get("reason_codes", []),
        )
        return True

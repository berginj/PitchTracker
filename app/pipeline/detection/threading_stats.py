"""Runtime statistics and terminal conservation for detection threading."""

import logging
from typing import Dict, Optional

from app.events.event_types import FrameProcessingOpportunityEvent, FrameProcessingOutcomeEvent
from app.pipeline.detection.decision_ids import frame_decision_id
from app.pipeline.detection.threading_items import FrameWorkItem
from contracts import Detection

logger = logging.getLogger(__name__)


class DetectionStatsMixin:
    """Expose counters and conserve every offered frame opportunity."""

    def get_error_stats(self) -> Dict[str, int]:
        with self._detection_error_lock:
            return self._detection_errors.copy()

    def get_runtime_stats(self) -> dict:
        with self._detection_error_lock:
            attempts = self._processing_attempts.copy()
            failures = self._processing_failures.copy()
            queue_attempts = self._queue_attempts.copy()
            queue_drops = self._frames_dropped.copy()
            offered = self._opportunity_sequence
            terminal = len(self._terminal_opportunities)
            outstanding = len(self._open_opportunities)
            terminal_outcomes = dict(self._terminal_outcomes)

        stages = {
            name: {
                "attempts": attempts.get(name, 0),
                "failures": failures.get(name, 0),
                "queue_attempts": queue_attempts.get(name, 0),
                "queue_drops": queue_drops.get(name, 0),
                "failure_rate": _rate_payload(failures.get(name, 0), attempts.get(name, 0)),
                "queue_drop_rate": _rate_payload(queue_drops.get(name, 0), queue_attempts.get(name, 0)),
            }
            for name in ("left", "right", "results")
        }
        stages["frame_conservation"] = {
            "offered": offered,
            "terminal": terminal,
            "outstanding": outstanding,
            "balanced": offered == terminal + outstanding,
            "terminal_outcomes": terminal_outcomes,
        }
        return stages

    def _publish_opportunity(self, work: FrameWorkItem) -> None:
        callback = self._frame_opportunity_callback
        if callback is None:
            return
        frame = work.frame
        try:
            callback(
                FrameProcessingOpportunityEvent(
                    opportunity_id=work.opportunity_id,
                    frame_id=frame_decision_id(frame),
                    camera_id=frame.camera_id,
                    frame_index=frame.frame_index,
                    timestamp_ns=frame.t_capture_monotonic_ns,
                )
            )
        except Exception:
            logger.exception("Frame opportunity callback failed")

    def _finish_opportunity(
        self,
        work: FrameWorkItem,
        status: str,
        *,
        detections: Optional[list[Detection]] = None,
        reason_codes: tuple[str, ...] = (),
    ) -> None:
        with self._detection_error_lock:
            if work.opportunity_id in self._terminal_opportunities:
                return
            if work.opportunity_id not in self._open_opportunities:
                return
            self._terminal_opportunities.add(work.opportunity_id)
            self._terminal_outcomes[status] += 1
            self._open_opportunities.pop(work.opportunity_id, None)
        callback = self._frame_outcome_callback
        if callback is None:
            return
        frame = work.frame
        try:
            callback(
                FrameProcessingOutcomeEvent(
                    opportunity_id=work.opportunity_id,
                    frame_id=frame_decision_id(frame),
                    camera_id=frame.camera_id,
                    frame_index=frame.frame_index,
                    timestamp_ns=frame.t_capture_monotonic_ns,
                    status=status,
                    detections=tuple(detections or ()),
                    reason_codes=tuple(reason_codes),
                )
            )
        except Exception:
            logger.exception("Frame terminal-outcome callback failed")


def _rate_payload(numerator: int, denominator: int) -> dict:
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "value": (float(numerator) / float(denominator)) if denominator > 0 else None,
    }

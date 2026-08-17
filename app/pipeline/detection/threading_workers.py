"""Worker and result-consumer loops for detection threading."""

import logging
import queue
import time
from typing import Any

from app.events import ErrorCategory, ErrorSeverity, publish_error
from app.pipeline.detection.threading_items import DetectionResultItem

logger = logging.getLogger(__name__)


class _DetectionState:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)


class DetectionWorkerMixin(_DetectionState):
    """Run per-camera/shared detection workers and result callbacks."""

    def _detection_loop_per_camera(self, label: str, source: queue.Queue) -> None:
        while self._detection_running:
            try:
                work = source.get(timeout=0.2)
            except queue.Empty:
                continue

            self._process_work_item(label, work)

    def _detection_loop_pool(self) -> None:
        while self._detection_running:
            handled = False
            for label in ("left", "right"):
                if not self._detection_running:
                    return

                with self._detector_busy_lock:
                    if self._detector_busy.get(label, False):
                        continue
                    source = self._left_detect_queue if label == "left" else self._right_detect_queue
                    try:
                        work = source.get_nowait()
                    except queue.Empty:
                        continue
                    self._detector_busy[label] = True

                self._process_work_item(label, work)
                with self._detector_busy_lock:
                    self._detector_busy[label] = False
                handled = True

            if not handled:
                time.sleep(0.005)

    def _process_work_item(self, label, work) -> None:
        detections = self._detect_frame(label, work.frame)
        if detections is None:
            self._finish_opportunity(work, "DETECTOR_FAILED", reason_codes=("DETECTOR_EXCEPTION",))
            return

        result = self._queue_put_drop_oldest(
            self._detect_result_queue,
            DetectionResultItem(work, detections),
            queue_name="results",
        )
        if isinstance(result.displaced, DetectionResultItem):
            self._finish_opportunity(
                result.displaced.work,
                "RESULT_QUEUE_DROPPED",
                detections=result.displaced.detections,
                reason_codes=("DROP_OLDEST",),
            )
        if not result.accepted:
            self._finish_opportunity(
                work,
                "RESULT_QUEUE_DROPPED",
                detections=detections,
                reason_codes=("QUEUE_RETRY_FAILED",),
            )

    def _stereo_loop(self) -> None:
        while self._detection_running:
            try:
                result = self._detect_result_queue.get(timeout=0.2)
            except queue.Empty:
                self._check_adaptive_queue_sizing()
                continue

            self._process_detection_result(result)
            self._check_adaptive_queue_sizing()

    def _process_detection_result(self, result: DetectionResultItem) -> None:
        label = result.work.label
        frame = result.work.frame
        detections = result.detections
        if self._stereo_callback is None:
            self._finish_opportunity(
                result.work,
                "RESULT_PROCESSING_FAILED",
                detections=detections,
                reason_codes=("STEREO_CALLBACK_MISSING",),
            )
            return

        with self._detection_error_lock:
            self._processing_attempts["results"] += 1
        try:
            self._stereo_callback(label, frame, detections)
        except Exception as exc:
            with self._detection_error_lock:
                self._processing_failures["results"] += 1
            logger.exception("Detection result processing failed for %s camera", label)
            publish_error(
                category=ErrorCategory.DETECTION,
                severity=ErrorSeverity.ERROR,
                message=f"Detection result processing failed for {label} camera",
                source="DetectionThreadPool.results",
                exception=exc,
                camera=label,
            )
            self._finish_opportunity(
                result.work,
                "RESULT_PROCESSING_FAILED",
                detections=detections,
                reason_codes=(exc.__class__.__name__,),
            )
        else:
            self._finish_opportunity(result.work, "PROCESSING_COMPLETE", detections=detections)

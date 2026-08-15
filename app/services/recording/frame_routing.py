"""Frame routing and writer stats for RecordingService."""

from __future__ import annotations

from typing import TYPE_CHECKING

from contracts import Frame
from log_config.logger import get_logger

if TYPE_CHECKING:
    from app.services.recording.implementation import RecordingServiceImpl

logger = get_logger(__name__)


class FrameRoutingMixin:
    """Frame recording, worker sync callback, and stats."""

    def record_frame(self: "RecordingServiceImpl", camera_id: str, frame: Frame) -> None:
        """Record a frame to current session.

        Frames are queued for bounded asynchronous writing. If the queue is
        full, the frame is dropped explicitly and recorded in worker metrics.
        """
        with self._lock:
            if not self._session_active:
                raise RuntimeError("No session active")
            if self._session_paused:
                return
        if not self._frame_worker.submit((camera_id, frame)):
            logger.warning(
                "Recording queue full; dropping newest frame camera=%s index=%s",
                camera_id,
                frame.frame_index,
            )

    def _record_frame_sync(self: "RecordingServiceImpl", item) -> None:
        """Perform codec and CSV I/O on the recording worker thread."""
        camera_id, frame = item
        with self._lock:
            if not self._session_active or self._session_recorder is None:
                return
            self._session_recorder.write_frame(camera_id, frame)

            # Buffer for pre-roll (always buffer even if no pitch active)
            self._pre_roll_buffer[camera_id].append(frame)

            # Write to pitch recorder if active (state read at processing
            # time — ordering is guaranteed by FIFO control commands).
            pitch_recorder = self._pitch_recorder if self._pitch_active else None
            if pitch_recorder is not None:
                pitch_recorder.write_frame(camera_id, frame)

                # Check if post-roll complete
                if pitch_recorder.should_close() and pitch_recorder is self._pitch_recorder:
                    self._stop_pitch_internal()

    def get_frame_writer_stats(self: "RecordingServiceImpl") -> dict:
        """Expose queue, loss, and failure rates for quality diagnostics."""
        stats = self._frame_worker.stats()
        attempted = stats.submitted + stats.dropped
        return {
            "submitted": stats.submitted,
            "written": stats.written,
            "dropped": stats.dropped,
            "failed": stats.failed,
            "queue_depth": stats.queue_depth,
            "drop_rate": stats.dropped / max(attempted, 1),
            "failure_rate": stats.failed / max(stats.submitted, 1),
            "drop_policy": "drop_newest",
        }

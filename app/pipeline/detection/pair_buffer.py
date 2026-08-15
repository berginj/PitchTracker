"""Stereo frame pair buffering and temporal matching."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import List, Tuple

from configs.settings import AppConfig
from contracts import Detection, Frame
from contracts.evidence import PairingOutcomeEvidence
from stereo.association import PairTiming, pair_timing

from app.pipeline.detection.decision_ids import frame_decision_id, stereo_pair_id
from app.pipeline.sync_diagnostics import summarize_sync_quality

logger = logging.getLogger(__name__)


class PairBuffer:
    """Buffer left/right frames and emit temporally matched stereo pairs.

    Thread-safe: both capture threads call :meth:`push` concurrently.
    The heavy per-pair processing is returned to the caller to run outside the lock.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._maxlen = 6

        self._left_buffer: deque[Tuple[Frame, list[Detection]]] = deque()
        self._right_buffer: deque[Tuple[Frame, list[Detection]]] = deque()
        self._pending_outcomes: list[PairingOutcomeEvidence] = []

        # Sync monitoring
        self._frame_deltas_ns: deque[int] = deque(maxlen=100)
        self._raw_frame_deltas_ns: deque[int] = deque(maxlen=100)
        self._total_paired_frames = 0
        self._dropped_frames_sync = 0
        self._last_sync_warning_time = 0.0
        self._frame_index_pairing_warned = False

    def push(
        self, label: str, frame: Frame, detections: list[Detection]
    ) -> Tuple[
        List[Tuple[Frame, Frame, list[Detection], list[Detection]]],
        Tuple[PairingOutcomeEvidence, ...],
    ]:
        """Buffer a frame and return any matched pairs plus pairing outcomes.

        Must be called from either capture thread. Returns matched pairs and
        accumulated pairing outcomes so caller can process outside the lock.
        """
        with self._lock:
            if label == "left":
                if len(self._left_buffer) >= self._maxlen:
                    dropped_frame, _ = self._left_buffer.popleft()
                    self._record_unmatched(dropped_frame, "BUFFER_EVICTED")
                self._left_buffer.append((frame, detections))
            else:
                if len(self._right_buffer) >= self._maxlen:
                    dropped_frame, _ = self._right_buffer.popleft()
                    self._record_unmatched(dropped_frame, "BUFFER_EVICTED")
                self._right_buffer.append((frame, detections))

            matched_pairs = self._match()
            outcomes = tuple(self._pending_outcomes)
            self._pending_outcomes.clear()

        return matched_pairs, outcomes

    def flush(self, reason: str = "FLUSHED_ON_STOP") -> Tuple[PairingOutcomeEvidence, ...]:
        """Give every buffered frame an explicit terminal unmatched outcome."""
        with self._lock:
            while self._left_buffer:
                frame, _ = self._left_buffer.popleft()
                self._record_unmatched(frame, reason)
            while self._right_buffer:
                frame, _ = self._right_buffer.popleft()
                self._record_unmatched(frame, reason)
            outcomes = tuple(self._pending_outcomes)
            self._pending_outcomes.clear()
        return outcomes

    def get_sync_stats(self) -> dict:
        """Get timestamp synchronization statistics."""
        adjusted = summarize_sync_quality(
            self._frame_deltas_ns,
            self._total_paired_frames,
            self._dropped_frames_sync,
        )
        raw = summarize_sync_quality(
            self._raw_frame_deltas_ns,
            self._total_paired_frames,
            self._dropped_frames_sync,
        )
        adjusted.update(
            {
                "timing_basis": "right_timestamp_plus_configured_offset",
                "time_sync_offset_ns": self._time_sync_offset_ns(),
                "raw_mean_delta_ms": raw["mean_delta_ms"],
                "raw_p95_delta_ms": raw["p95_delta_ms"],
                "raw_max_delta_ms": raw["max_delta_ms"],
            }
        )
        return adjusted

    def update_config(self, config: AppConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _time_sync_offset_ns(self) -> int:
        if self._config is None:
            return 0
        return int(getattr(self._config.stereo, "time_sync_offset_ns", 0))

    def _pair_timing(self, left_frame: Frame, right_frame: Frame) -> PairTiming:
        return pair_timing(
            left_frame.t_capture_monotonic_ns,
            right_frame.t_capture_monotonic_ns,
            self._time_sync_offset_ns(),
        )

    def _match(self) -> List[Tuple[Frame, Frame, list[Detection], list[Detection]]]:
        """Match stereo pairs. Must be called under lock."""
        pairs: List[Tuple[Frame, Frame, list[Detection], list[Detection]]] = []
        if self._config and self._config.stereo.use_frame_index_pairing:
            if not self._frame_index_pairing_warned:
                logger.warning(
                    "use_frame_index_pairing is enabled: frame-index pairing assumes both "
                    "cameras keep lockstep counters and desyncs permanently on any dropped "
                    "frame. Prefer timestamp pairing unless cameras are hardware-synchronized."
                )
                self._frame_index_pairing_warned = True
            self._match_by_frame_index(pairs)
        else:
            self._match_by_timestamp(pairs)
        return pairs

    def _match_by_frame_index(
        self, pairs: List[Tuple[Frame, Frame, list[Detection], list[Detection]]]
    ) -> None:
        while self._left_buffer and self._right_buffer:
            left_frame, left_dets = self._left_buffer[0]
            right_frame, right_dets = self._right_buffer[0]
            left_idx = left_frame.frame_index
            right_idx = right_frame.frame_index
            tolerance = 1
            if self._config is not None:
                tolerance = self._config.stereo.frame_index_tolerance
            index_diff = abs(left_idx - right_idx)

            if index_diff > tolerance:
                self._dropped_frames_sync += 1
                if left_idx < right_idx:
                    self._left_buffer.popleft()
                    self._record_unmatched(left_frame, "INDEX_BEHIND")
                    logger.debug(f"Dropped left frame (index {left_idx} vs {right_idx})")
                else:
                    self._right_buffer.popleft()
                    self._record_unmatched(right_frame, "INDEX_BEHIND")
                    logger.debug(f"Dropped right frame (index {right_idx} vs {left_idx})")
                continue

            timing = self._pair_timing(left_frame, right_frame)
            self._record_pair_timing(timing)
            self._total_paired_frames += 1
            if timing.adjusted_skew_ns > 50_000_000:
                logger.warning(
                    f"Frame index match (left={left_idx}, right={right_idx}) "
                    f"but large timestamp delta: {timing.adjusted_skew_ns / 1e6:.1f}ms"
                )
            if self._total_paired_frames % 100 == 0:
                self._check_sync_quality()
            self._left_buffer.popleft()
            self._right_buffer.popleft()
            self._record_paired(left_frame, right_frame, pairing_mode="frame_index")
            pairs.append((left_frame, right_frame, left_dets, right_dets))

    def _match_by_timestamp(
        self, pairs: List[Tuple[Frame, Frame, list[Detection], list[Detection]]]
    ) -> None:
        while self._left_buffer and self._right_buffer:
            left_frame, left_dets = self._left_buffer[0]
            right_frame, right_dets = self._right_buffer[0]
            timing = self._pair_timing(left_frame, right_frame)
            delta = timing.adjusted_skew_ns
            tolerance = 0
            if self._config is not None:
                tolerance = int(self._config.stereo.pairing_tolerance_ms * 1e6)

            if tolerance > 0 and delta > tolerance:
                self._dropped_frames_sync += 1
                if timing.adjusted_left_ns < timing.adjusted_right_ns:
                    self._left_buffer.popleft()
                    self._record_unmatched(left_frame, "TIMESTAMP_BEHIND")
                    logger.debug(
                        f"Dropped left frame (delta={delta / 1e6:.1f}ms exceeds tolerance)"
                    )
                else:
                    self._right_buffer.popleft()
                    self._record_unmatched(right_frame, "TIMESTAMP_BEHIND")
                    logger.debug(
                        f"Dropped right frame (delta={delta / 1e6:.1f}ms exceeds tolerance)"
                    )
                continue

            self._record_pair_timing(timing)
            self._total_paired_frames += 1
            if self._total_paired_frames % 100 == 0:
                self._check_sync_quality()
            self._left_buffer.popleft()
            self._right_buffer.popleft()
            self._record_paired(left_frame, right_frame, pairing_mode="timestamp")
            pairs.append((left_frame, right_frame, left_dets, right_dets))

    def _record_pair_timing(self, timing: PairTiming) -> None:
        self._raw_frame_deltas_ns.append(timing.raw_skew_ns)
        self._frame_deltas_ns.append(timing.adjusted_skew_ns)

    def _record_unmatched(self, frame: Frame, reason: str) -> None:
        frame_id = frame_decision_id(frame)
        is_left = frame.camera_id == "left"
        self._pending_outcomes.append(
            PairingOutcomeEvidence(
                outcome_id=f"pairing:{frame_id}:{reason}",
                status="UNMATCHED",
                left_frame_id=frame_id if is_left else None,
                right_frame_id=None if is_left else frame_id,
                left_timestamp_ns=frame.t_capture_monotonic_ns if is_left else None,
                right_timestamp_ns=None if is_left else frame.t_capture_monotonic_ns,
                pairing_mode="frame_index"
                if self._config and self._config.stereo.use_frame_index_pairing
                else "timestamp",
                reason_codes=(reason,),
            )
        )

    def _record_paired(self, left: Frame, right: Frame, *, pairing_mode: str) -> None:
        timing = self._pair_timing(left, right)
        pid = stereo_pair_id(left, right)
        self._pending_outcomes.append(
            PairingOutcomeEvidence(
                outcome_id=f"pairing:{pid}",
                status="PAIRED",
                left_frame_id=frame_decision_id(left),
                right_frame_id=frame_decision_id(right),
                left_timestamp_ns=timing.raw_left_ns,
                right_timestamp_ns=timing.raw_right_ns,
                adjusted_left_timestamp_ns=timing.adjusted_left_ns,
                adjusted_right_timestamp_ns=timing.adjusted_right_ns,
                raw_pair_skew_ns=timing.raw_skew_ns,
                pair_skew_ns=timing.adjusted_skew_ns,
                pairing_mode=pairing_mode,
            )
        )

    def _check_sync_quality(self) -> None:
        if not self._frame_deltas_ns:
            return
        current_time = time.monotonic()
        if current_time - self._last_sync_warning_time < 60.0:
            return
        stats = summarize_sync_quality(
            self._frame_deltas_ns,
            self._total_paired_frames,
            self._dropped_frames_sync,
        )
        if stats["sync_quality"] in {"WARN", "POOR"}:
            logger.warning(
                f"Poor timestamp synchronization detected:\n"
                f"  Mean delta: {stats['mean_delta_ms']:.1f}ms\n"
                f"  P95 delta:  {stats['p95_delta_ms']:.1f}ms\n"
                f"  Max delta:  {stats['max_delta_ms']:.1f}ms\n"
                f"  Dropped frames: {self._dropped_frames_sync} ({stats['drop_rate_pct']:.1f}%)\n"
                f"Recommendation: {stats['sync_recommendation']}"
            )
            self._last_sync_warning_time = current_time

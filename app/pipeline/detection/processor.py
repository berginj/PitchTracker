"""Detection processor for stereo matching, metrics computation, and observation tracking."""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Callable, Dict, List, Optional, Tuple

from configs.settings import AppConfig
from contracts import Detection, Frame, StereoObservation
from detect.lane import LaneGate
from metrics.simple_metrics import (
    PlateMetricsStub,
    compute_plate_from_observations,
    compute_plate_stub,
)
from metrics.strike_zone import StrikeResult, build_strike_zone, is_strike
from stereo import StereoLaneGate
from stereo.simple_stereo import SimpleStereoMatcher
from track.simple_tracker import SimpleTracker

from app.pipeline.utils import build_stereo_matches, gate_detections

logger = logging.getLogger(__name__)


class DetectionProcessor:
    """Processes detection results for stereo matching and metrics computation.

    Handles:
    - Stereo frame pairing and temporal matching
    - Detection gating (lane and plate ROIs)
    - Stereo triangulation
    - Observation tracking
    - Plate metrics computation
    - Strike zone calculation
    """

    def __init__(
        self,
        config: AppConfig,
        stereo_matcher: SimpleStereoMatcher,
        lane_gate: Optional[LaneGate],
        plate_gate: Optional[LaneGate],
        stereo_gate: Optional[StereoLaneGate],
        plate_stereo_gate: Optional[StereoLaneGate],
        get_ball_radius_fn: Callable[[], float],
    ):
        """Initialize detection processor.

        Args:
            config: Application configuration
            stereo_matcher: Stereo triangulation matcher
            lane_gate: Lane ROI gate for detection filtering
            plate_gate: Plate ROI gate for detection filtering
            stereo_gate: Stereo gate for match filtering
            plate_stereo_gate: Plate stereo gate for match filtering
            get_ball_radius_fn: Function to get current ball radius
        """
        self._config = config
        self._stereo = stereo_matcher
        self._lane_gate = lane_gate
        self._plate_gate = plate_gate
        self._stereo_gate = stereo_gate
        self._plate_stereo_gate = plate_stereo_gate
        self._get_ball_radius_fn = get_ball_radius_fn

        # Tracking
        self._tracker = SimpleTracker()
        self._plate_observations = deque(maxlen=12)

        # Stereo buffering
        self._left_buffer: deque[Tuple[Frame, list[Detection]]] = deque(maxlen=6)
        self._right_buffer: deque[Tuple[Frame, list[Detection]]] = deque(maxlen=6)

        # Timestamp synchronization monitoring
        self._frame_deltas_ns: deque[int] = deque(maxlen=100)  # Track last 100 frame pairs
        self._total_paired_frames = 0
        self._dropped_frames_sync = 0
        self._last_sync_warning_time = 0.0

        # State (thread-safe)
        self._detect_lock = threading.Lock()
        self._last_detections: Dict[str, list[Detection]] = {}
        self._last_gated: Dict[str, Dict[str, list[Detection]]] = {}
        self._last_plate_metrics = PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)
        self._strike_result = StrikeResult(is_strike=False, sample_count=0)

        # Callbacks
        self._on_stereo_pair: Optional[
            Callable[
                [
                    Frame,
                    Frame,
                    list[Detection],
                    list[Detection],
                    List[StereoObservation],
                    int,
                    int,
                ],
                None,
            ]
        ] = None

    def set_stereo_pair_callback(
        self,
        callback: Callable[
            [
                Frame,
                Frame,
                list[Detection],
                list[Detection],
                List[StereoObservation],
                int,
                int,
            ],
            None,
        ],
    ) -> None:
        """Set callback for stereo pair processing.

        Args:
            callback: Function called when stereo pair is processed,
                     receives (left_frame, right_frame, left_detections, right_detections,
                              observations, lane_count, plate_count)
        """
        self._on_stereo_pair = callback

    def process_detection_result(self, label: str, frame: Frame, detections: list[Detection]) -> None:
        """Process detection result.

        Updates latest detections and buffers frames for stereo matching.

        Args:
            label: Camera label ("left" or "right")
            frame: Detected frame
            detections: Detection results
        """
        # Update latest detections
        with self._detect_lock:
            self._last_detections[frame.camera_id] = detections

        # Buffer for stereo matching
        if label == "left":
            self._left_buffer.append((frame, detections))
        else:
            self._right_buffer.append((frame, detections))

        # Try to match stereo pairs
        self._match_stereo_buffers()

    def get_latest_detections(self) -> Dict[str, list[Detection]]:
        """Get latest detections for all cameras.

        Returns:
            Dictionary mapping camera ID to detection list
        """
        with self._detect_lock:
            return dict(self._last_detections)

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, list[Detection]]]:
        """Get latest gated detections.

        Returns:
            Dictionary mapping camera ID to dict of gate type to detection list
        """
        with self._detect_lock:
            return {key: dict(value) for key, value in self._last_gated.items()}

    def get_plate_metrics(self) -> PlateMetricsStub:
        """Get latest plate metrics.

        Returns:
            Latest plate metrics
        """
        with self._detect_lock:
            return self._last_plate_metrics

    def get_strike_result(self) -> StrikeResult:
        """Get latest strike result.

        Returns:
            Latest strike result
        """
        with self._detect_lock:
            return self._strike_result

    def update_config(self, config: AppConfig) -> None:
        """Update configuration.

        Args:
            config: New application configuration
        """
        self._config = config

    def _check_sync_quality(self) -> None:
        """Check timestamp synchronization quality and log warnings if poor.

        Analyzes recent frame deltas and warns if cameras are poorly synchronized.
        """
        import time
        import numpy as np

        if not self._frame_deltas_ns:
            return

        deltas_ms = np.array(self._frame_deltas_ns) / 1e6
        mean_delta = np.mean(deltas_ms)
        max_delta = np.max(deltas_ms)
        p95_delta = np.percentile(deltas_ms, 95)

        # Thresholds for warnings
        WARN_MEAN_MS = 10.0  # Mean delta > 10ms is concerning
        WARN_MAX_MS = 50.0   # Max delta > 50ms is very concerning
        WARN_P95_MS = 20.0   # 95th percentile > 20ms is concerning

        # Throttle warnings to once per minute
        current_time = time.monotonic()
        if current_time - self._last_sync_warning_time < 60.0:
            return

        # Check for poor synchronization
        if mean_delta > WARN_MEAN_MS or max_delta > WARN_MAX_MS or p95_delta > WARN_P95_MS:
            drop_rate = (self._dropped_frames_sync / max(self._total_paired_frames, 1)) * 100

            logger.warning(
                f"Poor timestamp synchronization detected:\n"
                f"  Mean delta: {mean_delta:.1f}ms (target: <{WARN_MEAN_MS}ms)\n"
                f"  P95 delta:  {p95_delta:.1f}ms (target: <{WARN_P95_MS}ms)\n"
                f"  Max delta:  {max_delta:.1f}ms (target: <{WARN_MAX_MS}ms)\n"
                f"  Dropped frames: {self._dropped_frames_sync} ({drop_rate:.1f}%)\n"
                f"Recommendation: Consider hardware trigger or frame-index pairing"
            )
            self._last_sync_warning_time = current_time

    def get_sync_stats(self) -> dict:
        """Get timestamp synchronization statistics.

        Returns:
            Dictionary with sync quality metrics:
            - mean_delta_ms: Average timestamp delta
            - p95_delta_ms: 95th percentile delta
            - max_delta_ms: Maximum delta
            - total_paired: Total frames successfully paired
            - dropped_sync: Frames dropped due to sync issues
            - drop_rate_pct: Percentage of frames dropped
        """
        import numpy as np

        if not self._frame_deltas_ns:
            return {
                "mean_delta_ms": 0.0,
                "p95_delta_ms": 0.0,
                "max_delta_ms": 0.0,
                "total_paired": self._total_paired_frames,
                "dropped_sync": self._dropped_frames_sync,
                "drop_rate_pct": 0.0,
            }

        deltas_ms = np.array(self._frame_deltas_ns) / 1e6
        total = self._total_paired_frames + self._dropped_frames_sync
        drop_rate = (self._dropped_frames_sync / max(total, 1)) * 100

        return {
            "mean_delta_ms": float(np.mean(deltas_ms)),
            "p95_delta_ms": float(np.percentile(deltas_ms, 95)),
            "max_delta_ms": float(np.max(deltas_ms)),
            "total_paired": self._total_paired_frames,
            "dropped_sync": self._dropped_frames_sync,
            "drop_rate_pct": float(drop_rate),
        }

    def _match_stereo_buffers(self) -> None:
        """Match stereo pairs from buffered frames.

        Pairs left/right frames based on temporal proximity and processes them.
        Also monitors timestamp synchronization quality.
        """
        while self._left_buffer and self._right_buffer:
            left_frame, left_dets = self._left_buffer[0]
            right_frame, right_dets = self._right_buffer[0]

            # Check temporal alignment
            delta = abs(left_frame.t_capture_monotonic_ns - right_frame.t_capture_monotonic_ns)
            tolerance = 0
            if self._config is not None:
                tolerance = int(self._config.stereo.pairing_tolerance_ms * 1e6)

            if tolerance and delta > tolerance:
                # Frames too far apart, drop the older one
                self._dropped_frames_sync += 1
                if left_frame.t_capture_monotonic_ns < right_frame.t_capture_monotonic_ns:
                    self._left_buffer.popleft()
                    logger.debug(
                        f"Dropped left frame (delta={delta/1e6:.1f}ms exceeds tolerance={tolerance/1e6:.1f}ms)"
                    )
                else:
                    self._right_buffer.popleft()
                    logger.debug(
                        f"Dropped right frame (delta={delta/1e6:.1f}ms exceeds tolerance={tolerance/1e6:.1f}ms)"
                    )
                continue

            # Frames are paired - track sync quality
            self._frame_deltas_ns.append(delta)
            self._total_paired_frames += 1

            # Periodic sync quality check
            if self._total_paired_frames % 100 == 0:
                self._check_sync_quality()

            # Process the pair
            self._left_buffer.popleft()
            self._right_buffer.popleft()
            self._process_stereo_pair(left_frame, right_frame, left_dets, right_dets)

    def _process_stereo_pair(
        self,
        left_frame: Frame,
        right_frame: Frame,
        left_detections: list[Detection],
        right_detections: list[Detection],
    ) -> None:
        """Process a stereo pair of frames.

        Performs detection gating, stereo triangulation, tracking, and metrics computation.

        Args:
            left_frame: Left camera frame
            right_frame: Right camera frame
            left_detections: Left camera detections
            right_detections: Right camera detections
        """
        # Get camera IDs
        left_id = left_frame.camera_id
        right_id = right_frame.camera_id

        # Update latest detections
        with self._detect_lock:
            self._last_detections = {
                left_id: left_detections,
                right_id: right_detections,
            }

        # Gate detections by lane
        detections = left_detections + right_detections
        gated = gate_detections(self._lane_gate, detections)
        left_gated = [d for d in gated if d.camera_id == left_id]
        right_gated = [d for d in gated if d.camera_id == right_id]

        # Gate by plate
        plate_left = []
        plate_right = []
        if self._plate_gate is not None:
            plate = gate_detections(self._plate_gate, gated)
            plate_left = [d for d in plate if d.camera_id == left_id]
            plate_right = [d for d in plate if d.camera_id == right_id]

        # Update gated detections
        with self._detect_lock:
            self._last_gated = {
                left_id: {
                    "lane": left_gated,
                    "plate": plate_left,
                },
                right_id: {
                    "lane": right_gated,
                    "plate": plate_right,
                },
            }

        # Check temporal alignment for metrics computation
        if self._config is not None:
            tolerance_ns = int(self._config.stereo.pairing_tolerance_ms * 1e6)
            delta_ns = abs(left_frame.t_capture_monotonic_ns - right_frame.t_capture_monotonic_ns)
            if delta_ns > tolerance_ns:
                with self._detect_lock:
                    self._last_plate_metrics = compute_plate_stub([])
                    self._strike_result = StrikeResult(is_strike=False, sample_count=0)
                # Still notify callback with zero observations
                if self._on_stereo_pair:
                    lane_count = len(left_gated) + len(right_gated)
                    plate_count = len(plate_left) + len(plate_right)
                    self._on_stereo_pair(
                        left_frame, right_frame, left_detections, right_detections, [], lane_count, plate_count
                    )
                return

        # Build stereo matches
        matches = build_stereo_matches(left_gated, right_gated)
        if self._stereo_gate is not None:
            matches = self._stereo_gate.filter_matches(matches)

        # Filter plate matches
        if self._plate_stereo_gate is not None:
            plate_matches = self._plate_stereo_gate.filter_matches(matches)
        else:
            plate_matches = []

        # Triangulate observations
        observations = []
        for match in plate_matches:
            observations.append(self._stereo.triangulate(match))

        # Track observations
        for obs in observations:
            state = self._tracker.update(obs)
            if state.samples:
                self._plate_observations.append(obs)

        # Compute plate metrics
        if self._plate_observations:
            metrics = compute_plate_from_observations(self._plate_observations)
        else:
            metrics = compute_plate_stub(plate_matches)

        # Compute strike zone
        if self._config is not None:
            zone = build_strike_zone(
                plate_z_ft=self._config.metrics.plate_plane_z_ft,
                plate_width_in=self._config.strike_zone.plate_width_in,
                plate_length_in=self._config.strike_zone.plate_length_in,
                batter_height_in=self._config.strike_zone.batter_height_in,
                top_ratio=self._config.strike_zone.top_ratio,
                bottom_ratio=self._config.strike_zone.bottom_ratio,
            )
            radius_in = self._get_ball_radius_fn()
            strike = is_strike(self._plate_observations, zone, radius_in)
        else:
            strike = StrikeResult(is_strike=False, sample_count=0)

        # Update state
        with self._detect_lock:
            self._last_plate_metrics = metrics
            self._strike_result = strike

        # Notify callback
        if self._on_stereo_pair:
            lane_count = len(left_gated) + len(right_gated)
            plate_count = len(plate_left) + len(plate_right)
            self._on_stereo_pair(
                left_frame, right_frame, left_detections, right_detections, observations, lane_count, plate_count
            )

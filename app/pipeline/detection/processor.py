"""Detection processor for stereo matching, metrics computation, and observation tracking."""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Callable, Dict, List, Optional, Tuple

from configs.settings import AppConfig
from contracts import Detection, Frame, RayObservation, StereoObservation
from detect.lane import LaneGate
from metrics.simple_metrics import (
    PlateMetricsStub,
    compute_plate_from_observations,
    compute_plate_stub,
)
from metrics.strike_zone import StrikeResult, build_strike_zone, is_strike
from stereo import StereoLaneGate, StereoMatcher
from track.trajectory_tracker import TimestampedTrajectoryTracker

from app.pipeline.utils import build_stereo_matches, gate_detections
from app.pipeline.sync_diagnostics import summarize_sync_quality

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
        stereo_matcher: StereoMatcher,
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
        self._tracker = TimestampedTrajectoryTracker()
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
        self._on_ray_observations: Optional[Callable[[str, Frame, List[RayObservation], int, int], None]] = None

        # Cached strike zone (rebuilt only when config changes)
        self._cached_strike_zone = None
        self._cached_strike_zone_config_hash = None

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

    def set_ray_observation_callback(
        self,
        callback: Callable[[str, Frame, List[RayObservation], int, int], None],
    ) -> None:
        """Set callback for lane-gated per-camera ray observations."""
        self._on_ray_observations = callback

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

        self._emit_ray_observations(label, frame, detections)

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
        # Invalidate cached strike zone when config changes
        self._cached_strike_zone = None
        self._cached_strike_zone_config_hash = None

    def update_gates(
        self,
        lane_gate: Optional[LaneGate],
        plate_gate: Optional[LaneGate],
        stereo_gate: Optional[StereoLaneGate],
        plate_stereo_gate: Optional[StereoLaneGate],
    ) -> None:
        """Hot-swap lane and plate gates used for future frames."""
        self._lane_gate = lane_gate
        self._plate_gate = plate_gate
        self._stereo_gate = stereo_gate
        self._plate_stereo_gate = plate_stereo_gate

    def _emit_ray_observations(self, label: str, frame: Frame, detections: list[Detection]) -> None:
        """Emit lane-gated per-camera ray observations before stereo pairing."""
        if self._on_ray_observations is None:
            return

        lane_gated = gate_detections(self._lane_gate, detections)
        plate_gated = gate_detections(self._plate_gate, lane_gated) if self._plate_gate is not None else []

        max_candidates = 2
        if self._config is not None and getattr(self._config, "trajectory", None) is not None:
            max_candidates = int(self._config.trajectory.ray.max_candidates_per_frame)

        lane_gated = sorted(lane_gated, key=lambda det: det.confidence, reverse=True)[:max_candidates]
        rays = [
            RayObservation(
                camera_id=label,
                frame_index=det.frame_index,
                t_ns=det.t_capture_monotonic_ns,
                u=float(det.u),
                v=float(det.v),
                radius_px=float(det.radius_px),
                confidence=float(det.confidence),
            )
            for det in lane_gated
        ]

        with self._detect_lock:
            current = dict(self._last_gated.get(frame.camera_id, {}))
            current["lane"] = lane_gated
            current["plate"] = plate_gated
            self._last_gated[frame.camera_id] = current

        self._on_ray_observations(label, frame, rays, len(lane_gated), len(plate_gated))

    def _get_or_build_strike_zone(self):
        """Get cached strike zone or build new one if config changed.

        Caches strike zone to avoid rebuilding on every frame (10-20% latency reduction).
        Strike zone only depends on config parameters, so it can be safely cached.

        Returns:
            Strike zone object
        """
        if self._config is None:
            return None

        # Compute config hash to detect changes
        config_tuple = (
            self._config.metrics.plate_plane_z_ft,
            self._config.strike_zone.plate_width_in,
            self._config.strike_zone.plate_length_in,
            self._config.strike_zone.batter_height_in,
            self._config.strike_zone.top_ratio,
            self._config.strike_zone.bottom_ratio,
        )

        # Return cached zone if config unchanged
        if self._cached_strike_zone_config_hash == config_tuple:
            return self._cached_strike_zone

        # Build and cache new strike zone
        self._cached_strike_zone = build_strike_zone(
            plate_z_ft=self._config.metrics.plate_plane_z_ft,
            plate_width_in=self._config.strike_zone.plate_width_in,
            plate_length_in=self._config.strike_zone.plate_length_in,
            batter_height_in=self._config.strike_zone.batter_height_in,
            top_ratio=self._config.strike_zone.top_ratio,
            bottom_ratio=self._config.strike_zone.bottom_ratio,
        )
        self._cached_strike_zone_config_hash = config_tuple

        return self._cached_strike_zone

    def _check_sync_quality(self) -> None:
        """Check timestamp synchronization quality and log warnings if poor.

        Analyzes recent frame deltas and warns if cameras are poorly synchronized.
        """
        import time

        if not self._frame_deltas_ns:
            return

        # Throttle warnings to once per minute
        current_time = time.monotonic()
        if current_time - self._last_sync_warning_time < 60.0:
            return

        stats = summarize_sync_quality(
            self._frame_deltas_ns,
            self._total_paired_frames,
            self._dropped_frames_sync,
        )

        # Check for poor synchronization
        if stats["sync_quality"] in {"WARN", "POOR"}:
            logger.warning(
                f"Poor timestamp synchronization detected:\n"
                f"  Mean delta: {stats['mean_delta_ms']:.1f}ms "
                f"({stats['mean_motion_in_at_max_speed']:.1f}in at 60mph)\n"
                f"  P95 delta:  {stats['p95_delta_ms']:.1f}ms "
                f"({stats['p95_motion_in_at_max_speed']:.1f}in at 60mph)\n"
                f"  Max delta:  {stats['max_delta_ms']:.1f}ms "
                f"({stats['max_motion_in_at_max_speed']:.1f}in at 60mph)\n"
                f"  Dropped frames: {self._dropped_frames_sync} ({stats['drop_rate_pct']:.1f}%)\n"
                f"Recommendation: {stats['sync_recommendation']}"
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
        return summarize_sync_quality(
            self._frame_deltas_ns,
            self._total_paired_frames,
            self._dropped_frames_sync,
        )

    def _match_stereo_buffers(self) -> None:
        """Match stereo pairs from buffered frames.

        Pairs left/right frames based on temporal proximity (or frame indices if enabled).
        Also monitors timestamp synchronization quality.
        """
        # Use frame-index pairing if enabled
        if self._config and self._config.stereo.use_frame_index_pairing:
            self._match_by_frame_index()
        else:
            self._match_by_timestamp()

    def _match_by_frame_index(self) -> None:
        """Match stereo pairs by frame index instead of timestamp.

        More reliable than timestamp matching if cameras maintain sync.
        Assumes both cameras capture at same rate.
        """
        while self._left_buffer and self._right_buffer:
            left_frame, left_dets = self._left_buffer[0]
            right_frame, right_dets = self._right_buffer[0]

            # Get frame indices
            left_idx = left_frame.frame_index
            right_idx = right_frame.frame_index

            # Get tolerance from config
            tolerance = 1
            if self._config is not None:
                tolerance = self._config.stereo.frame_index_tolerance

            # Check if indices match within tolerance
            index_diff = abs(left_idx - right_idx)

            if index_diff > tolerance:
                # Indices don't match, drop the one that's behind
                self._dropped_frames_sync += 1
                if left_idx < right_idx:
                    self._left_buffer.popleft()
                    logger.debug(f"Dropped left frame (index {left_idx} vs {right_idx}, diff={index_diff})")
                else:
                    self._right_buffer.popleft()
                    logger.debug(f"Dropped right frame (index {right_idx} vs {left_idx}, diff={index_diff})")
                continue

            # Frames matched by index - still track timestamp delta for monitoring
            delta = abs(left_frame.t_capture_monotonic_ns - right_frame.t_capture_monotonic_ns)
            self._frame_deltas_ns.append(delta)
            self._total_paired_frames += 1

            # Warn if timestamps are very different (indicates drift)
            if delta > 50_000_000:  # 50ms
                logger.warning(
                    f"Frame index match (left={left_idx}, right={right_idx}) "
                    f"but large timestamp delta: {delta/1e6:.1f}ms"
                )

            # Periodic sync quality check
            if self._total_paired_frames % 100 == 0:
                self._check_sync_quality()

            # Process the pair
            self._left_buffer.popleft()
            self._right_buffer.popleft()
            self._process_stereo_pair(left_frame, right_frame, left_dets, right_dets)

    def _match_by_timestamp(self) -> None:
        """Match stereo pairs by timestamp (traditional method).

        Pairs frames based on temporal proximity within tolerance.
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

        # Build stereo matches through the configured matcher so calibrated rigs use
        # their saved fundamental matrix instead of a rectified horizontal shortcut.
        epipolar_tolerance = 10.0
        if self._config is not None:
            epipolar_tolerance = float(self._config.stereo.epipolar_epsilon_px)
        matches = build_stereo_matches(
            left_gated,
            right_gated,
            epipolar_tolerance=epipolar_tolerance,
            matcher=self._stereo,
        )
        if self._stereo_gate is not None:
            matches = self._stereo_gate.filter_matches(matches)

        # Filter plate matches
        if self._plate_stereo_gate is not None:
            plate_matches = self._plate_stereo_gate.filter_matches(matches)
        else:
            plate_matches = []

        # Triangulate lane observations. Plate matches remain the input for plate
        # metrics, but the pitch tracker benefits from the longer in-flight path.
        observations = [self._stereo.triangulate(match) for match in matches]
        plate_observations = [self._stereo.triangulate(match) for match in plate_matches]

        # Track observations
        for obs in observations:
            state = self._tracker.update(obs)
        for obs in plate_observations:
            self._plate_observations.append(obs)

        # Compute plate metrics
        if self._plate_observations:
            metrics = compute_plate_from_observations(self._plate_observations)
        else:
            metrics = compute_plate_stub(plate_matches)

        # Compute strike zone (use cached zone for 10-20% latency reduction)
        zone = self._get_or_build_strike_zone()
        if zone is not None:
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

"""Detection processor for stereo matching, metrics computation, and observation tracking."""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Callable, Dict, List, Optional

from configs.settings import AppConfig
from contracts import Detection, Frame, RayObservation, StereoObservation
from contracts.evidence import PairingOutcomeEvidence
from detect.lane import LaneGate
from metrics.simple_metrics import (
    PlateMetricsStub,
    compute_plate_from_observations,
    compute_plate_stub,
)
from metrics.strike_zone import StrikeResult, StrikeZone, build_strike_zone, is_strike
from stereo import StereoLaneGate, StereoMatcher
from stereo.association import pair_timing
from track.trajectory_tracker import TimestampedTrajectoryTracker

from app.events.event_types import StereoAssociationOutcomeEvent
from app.pipeline.detection.association_graph import run_association
from app.pipeline.detection.decision_ids import stereo_pair_id
from app.pipeline.detection.evidence_assembly import (
    build_association_outcome_event,
    build_skew_rejection_event,
    emit_association_outcome,
    emit_pairing_outcomes,
)
from app.pipeline.detection.pair_buffer import PairBuffer
from app.pipeline.utils import gate_detections

logger = logging.getLogger(__name__)


class DetectionProcessor:
    """Processes detection results for stereo matching and metrics computation.

    Delegates pair buffering/timing to :class:`PairBuffer`, association
    decisions to :mod:`association_graph`, triangulation to
    :mod:`triangulation`, and event building to :mod:`evidence_assembly`.
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
        self._config = config
        self._stereo = stereo_matcher
        self._lane_gate = lane_gate
        self._plate_gate = plate_gate
        self._stereo_gate = stereo_gate
        self._plate_stereo_gate = plate_stereo_gate
        self._get_ball_radius_fn = get_ball_radius_fn

        # Tracking
        self._tracker = TimestampedTrajectoryTracker()
        self._plate_observations: deque[StereoObservation] = deque(maxlen=12)

        # Pair buffering (thread-safe internally)
        self._pair_buffer = PairBuffer(config)

        # State (thread-safe)
        self._detect_lock = threading.Lock()
        self._last_detections: Dict[str, list[Detection]] = {}
        self._last_gated: Dict[str, Dict[str, list[Detection]]] = {}
        self._last_plate_metrics = PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)
        self._strike_result = StrikeResult(is_strike=False, sample_count=0)

        # Callbacks
        self._on_stereo_pair: Optional[
            Callable[
                [Frame, Frame, list[Detection], list[Detection], List[StereoObservation], int, int],
                None,
            ]
        ] = None
        self._on_ray_observations: Optional[
            Callable[[str, Frame, List[RayObservation], int, int], None]
        ] = None
        self._on_pairing_outcome: Optional[Callable[[PairingOutcomeEvidence], None]] = None
        self._on_association_outcome: Optional[
            Callable[[StereoAssociationOutcomeEvent], None]
        ] = None

        # Cached strike zone
        self._cached_strike_zone: Optional[StrikeZone] = None
        self._cached_strike_zone_config_hash: Optional[tuple[float, float, float, float, float, float]] = None

    # ------------------------------------------------------------------
    # Callback registration (public API)
    # ------------------------------------------------------------------

    def set_stereo_pair_callback(
        self,
        callback: Callable[
            [Frame, Frame, list[Detection], list[Detection], List[StereoObservation], int, int],
            None,
        ],
    ) -> None:
        """Set callback for stereo pair processing."""
        self._on_stereo_pair = callback

    def set_ray_observation_callback(
        self,
        callback: Callable[[str, Frame, List[RayObservation], int, int], None],
    ) -> None:
        """Set callback for lane-gated per-camera ray observations."""
        self._on_ray_observations = callback

    def set_pairing_outcome_callback(
        self, callback: Callable[[PairingOutcomeEvidence], None]
    ) -> None:
        self._on_pairing_outcome = callback

    def set_association_outcome_callback(
        self, callback: Callable[[StereoAssociationOutcomeEvent], None]
    ) -> None:
        self._on_association_outcome = callback

    # ------------------------------------------------------------------
    # Public processing entry points
    # ------------------------------------------------------------------

    def process_detection_result(
        self, label: str, frame: Frame, detections: list[Detection]
    ) -> None:
        """Process detection result from a single camera thread."""
        with self._detect_lock:
            self._last_detections[frame.camera_id] = detections

        self._emit_ray_observations(label, frame, detections)

        matched_pairs, outcomes = self._pair_buffer.push(label, frame, detections)

        emit_pairing_outcomes(outcomes, self._on_pairing_outcome)
        for left_frame, right_frame, left_dets, right_dets in matched_pairs:
            self._process_stereo_pair(left_frame, right_frame, left_dets, right_dets)

    def flush_pairing_buffers(self, reason: str = "FLUSHED_ON_STOP") -> None:
        """Give every buffered frame an explicit terminal unmatched outcome."""
        outcomes = self._pair_buffer.flush(reason)
        emit_pairing_outcomes(outcomes, self._on_pairing_outcome)

    # ------------------------------------------------------------------
    # Public state accessors
    # ------------------------------------------------------------------

    def get_latest_detections(self) -> Dict[str, list[Detection]]:
        with self._detect_lock:
            return dict(self._last_detections)

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, list[Detection]]]:
        with self._detect_lock:
            return {key: dict(value) for key, value in self._last_gated.items()}

    def get_plate_metrics(self) -> PlateMetricsStub:
        with self._detect_lock:
            return self._last_plate_metrics

    def get_strike_result(self) -> StrikeResult:
        with self._detect_lock:
            return self._strike_result

    def get_sync_stats(self) -> dict:
        return dict(self._pair_buffer.get_sync_stats())

    def update_config(self, config: AppConfig) -> None:
        self._config = config
        self._pair_buffer.update_config(config)
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

    # ------------------------------------------------------------------
    # Internal: ray observations
    # ------------------------------------------------------------------

    def _emit_ray_observations(
        self, label: str, frame: Frame, detections: list[Detection]
    ) -> None:
        if self._on_ray_observations is None:
            return

        lane_gated = gate_detections(self._lane_gate, detections)
        plate_gated = (
            gate_detections(self._plate_gate, lane_gated)
            if self._plate_gate is not None
            else []
        )

        max_candidates = 2
        if self._config is not None and getattr(self._config, "trajectory", None) is not None:
            max_candidates = int(self._config.trajectory.ray.max_candidates_per_frame)

        lane_gated = sorted(lane_gated, key=lambda d: d.confidence, reverse=True)[
            :max_candidates
        ]
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

    # ------------------------------------------------------------------
    # Internal: stereo pair processing
    # ------------------------------------------------------------------

    def _process_stereo_pair(
        self,
        left_frame: Frame,
        right_frame: Frame,
        left_detections: list[Detection],
        right_detections: list[Detection],
    ) -> None:
        left_id = left_frame.camera_id
        right_id = right_frame.camera_id

        with self._detect_lock:
            self._last_detections = {left_id: left_detections, right_id: right_detections}

        # Gate detections
        all_dets = left_detections + right_detections
        gated = gate_detections(self._lane_gate, all_dets)
        left_gated = [d for d in gated if d.camera_id == left_id]
        right_gated = [d for d in gated if d.camera_id == right_id]

        plate_left: list[Detection] = []
        plate_right: list[Detection] = []
        if self._plate_gate is not None:
            plate = gate_detections(self._plate_gate, gated)
            plate_left = [d for d in plate if d.camera_id == left_id]
            plate_right = [d for d in plate if d.camera_id == right_id]

        with self._detect_lock:
            self._last_gated = {
                left_id: {"lane": left_gated, "plate": plate_left},
                right_id: {"lane": right_gated, "plate": plate_right},
            }

        # Check temporal alignment
        timing = self._pair_timing(left_frame, right_frame)
        if self._config is not None:
            tolerance_ns = int(self._config.stereo.pairing_tolerance_ms * 1e6)
            if timing.adjusted_skew_ns > tolerance_ns:
                self._handle_skew_rejection(
                    left_frame, right_frame, left_detections, right_detections,
                    left_gated, right_gated, plate_left, plate_right,
                )
                return

        # Association + triangulation
        result = run_association(
            left_frame, right_frame, left_gated, right_gated,
            self._config, self._stereo, self._stereo_gate,
        )
        observations = result.triangulation.observations

        # Plate triangulation
        plate_matches = (
            self._plate_stereo_gate.filter_matches(result.filtered_matches)
            if self._plate_stereo_gate is not None
            else []
        )
        plate_observations = [self._stereo.triangulate(m) for m in plate_matches]

        # Emit association outcome event
        event = build_association_outcome_event(result, timing)
        emit_association_outcome(event, self._on_association_outcome)

        # Track observations
        for obs in observations:
            self._tracker.update(obs)
        for obs in plate_observations:
            self._plate_observations.append(obs)

        # Compute metrics
        metrics = (
            compute_plate_from_observations(self._plate_observations)
            if self._plate_observations
            else compute_plate_stub(plate_matches)
        )
        strike = self._compute_strike()

        with self._detect_lock:
            self._last_plate_metrics = metrics
            self._strike_result = strike

        if self._on_stereo_pair:
            lane_count = len(left_gated) + len(right_gated)
            plate_count = len(plate_left) + len(plate_right)
            self._on_stereo_pair(
                left_frame, right_frame, left_detections, right_detections,
                observations, lane_count, plate_count,
            )

    def _handle_skew_rejection(
        self, left_frame, right_frame, left_detections, right_detections,
        left_gated, right_gated, plate_left, plate_right,
    ) -> None:
        with self._detect_lock:
            self._last_plate_metrics = compute_plate_stub([])
            self._strike_result = StrikeResult(is_strike=False, sample_count=0)
        if self._on_stereo_pair:
            lane_count = len(left_gated) + len(right_gated)
            plate_count = len(plate_left) + len(plate_right)
            self._on_stereo_pair(
                left_frame, right_frame, left_detections, right_detections,
                [], lane_count, plate_count,
            )
        timing = self._pair_timing(left_frame, right_frame)
        event = build_skew_rejection_event(
            stereo_pair_id(left_frame, right_frame), timing.timestamp_ns,
        )
        emit_association_outcome(event, self._on_association_outcome)

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    def _pair_timing(self, left_frame: Frame, right_frame: Frame):
        offset = 0
        if self._config is not None:
            offset = int(getattr(self._config.stereo, "time_sync_offset_ns", 0))
        return pair_timing(
            left_frame.t_capture_monotonic_ns,
            right_frame.t_capture_monotonic_ns,
            offset,
        )

    def _compute_strike(self) -> StrikeResult:
        zone = self._get_or_build_strike_zone()
        if zone is not None:
            radius_in = self._get_ball_radius_fn()
            return is_strike(self._plate_observations, zone, radius_in)
        return StrikeResult(is_strike=False, sample_count=0)

    def _get_or_build_strike_zone(self):
        if self._config is None:
            return None
        config_tuple = (
            self._config.metrics.plate_plane_z_ft,
            self._config.strike_zone.plate_width_in,
            self._config.strike_zone.plate_length_in,
            self._config.strike_zone.batter_height_in,
            self._config.strike_zone.top_ratio,
            self._config.strike_zone.bottom_ratio,
        )
        if self._cached_strike_zone_config_hash == config_tuple:
            return self._cached_strike_zone
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

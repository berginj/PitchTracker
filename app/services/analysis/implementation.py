"""AnalysisService implementation with EventBus integration.

Manages analysis pipeline:
- Pitch trajectory fitting
- Session summary generation
- Pattern detection
- Strike zone calculation
- Metrics computation
"""

from __future__ import annotations

import json
import threading
from collections import deque
from pathlib import Path
from typing import List, Optional

from app.contracts import PitchSummary, SessionSummary, measurement_is_usable, session_summary_from_dict
from app.events.event_bus import EventBus
from app.events.event_types import PitchAnalyzedEvent, PitchEndEvent
from app.pipeline.analysis.pitch_summary import PitchAnalyzer
from app.pipeline.pitch_tracking_v2 import PitchData
from app.services.analysis.interface import AnalysisService
from app.services.analysis.worker import BoundedAnalysisWorker
from calib.online_refinement import OnlineCalibrationRefiner
from configs.settings import AppConfig
from contracts import StereoObservation
from log_config.logger import get_logger
from metrics.simple_metrics import PlateMetricsStub
from metrics.strike_zone import StrikeResult, build_strike_zone, is_strike

logger = get_logger(__name__)


class AnalysisServiceImpl(AnalysisService):
    """Event-driven analysis service implementation.

    Features:
    - EventBus integration for event-driven analysis
    - Subscribes to PitchEndEvent for automatic analysis
    - Wraps PitchAnalyzer for trajectory fitting
    - Session summary aggregation
    - Pattern detection (future)
    - Strike zone calculation

    Architecture:
        - Subscribes to PitchEndEvent from EventBus
        - Analyzes pitch data and generates PitchSummary
        - Maintains session summary with all pitches
        - Provides strike zone calculations

    Thread Safety:
        - All public methods are thread-safe
        - Analysis runs on a bounded worker queue and drains on shutdown
        - Session summary updated atomically
    """

    def __init__(self, event_bus: EventBus, config: AppConfig):
        """Initialize analysis service.

        Args:
            event_bus: EventBus instance for subscribing to events
            config: Application configuration
        """
        self._event_bus = event_bus
        self._config = config
        self._lock = threading.Lock()

        # Pitch analyzer
        self._analyzer = PitchAnalyzer(
            config=config,
            get_ball_radius_fn=self._get_ball_radius,
            radar_speed_fn=lambda: self._manual_speed_mph,
            speed_source_fn=lambda: "manual_override",
        )

        # Session state
        self._session_summary: Optional[SessionSummary] = None
        self._pitch_summaries: List[PitchSummary] = []
        self._recent_pitch_paths: deque[List[StereoObservation]] = deque(maxlen=10)
        self._terminal_pitch_ids: set[str] = set()

        # Latest metrics
        self._plate_metrics = PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)

        # Strike zone configuration
        self._ball_type = config.ball.type
        self._batter_height_in = config.strike_zone.batter_height_in
        self._top_ratio = config.strike_zone.top_ratio
        self._bottom_ratio = config.strike_zone.bottom_ratio
        self._manual_speed_mph: Optional[float] = None

        # Online calibration refinement
        self._refiner: Optional[OnlineCalibrationRefiner] = None
        self._refinement_enabled = config.metrics.online_refinement_enabled
        if self._refinement_enabled:
            try:
                # Initialize refiner with config path
                config_path = Path("configs/default.yaml")
                self._refiner = OnlineCalibrationRefiner(config_path)
                logger.info("Online calibration refinement enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize calibration refiner: {e}")
                self._refinement_enabled = False

        # EventBus subscription
        self._analysis_active = False
        self._analysis_paused = False
        self._subscribed = False
        self._analysis_worker = BoundedAnalysisWorker(self._analyze_pitch_end_event, max_queue=64)

        logger.info("AnalysisService initialized")

    def start_analysis(self, session_id: str = "current") -> None:
        """Start analysis processing.

        Subscribes to EventBus for automatic pitch analysis.
        """
        with self._lock:
            if self._analysis_active:
                return

            if not self._analysis_worker.start():
                raise RuntimeError(
                    "Analysis worker from the previous session is still stopping; retry after it exits"
                )

            # Initialize session summary
            self._session_summary = SessionSummary(
                session_id=session_id,
                pitch_count=0,
                strikes=0,
                balls=0,
                heatmap=[[0] * 3 for _ in range(3)],  # 3x3 grid
                pitches=[],
            )
            self._pitch_summaries = []
            self._recent_pitch_paths.clear()
            self._terminal_pitch_ids.clear()

            # Subscribe to EventBus
            self._subscribe_to_events()
            self._analysis_active = True
            self._analysis_paused = False

            logger.info("Analysis started")

    def stop_analysis(self) -> None:
        """Stop analysis processing.

        Unsubscribes from EventBus.
        """
        with self._lock:
            if self._analysis_active:
                # Unsubscribe before draining so no new pitch work can arrive.
                self._unsubscribe_from_events()
                self._analysis_active = False
                self._analysis_paused = False

        # Always retry the worker stop. This makes a prior bounded timeout
        # recoverable without pretending shutdown completed.
        if not self._analysis_worker.stop(drain=True):
            logger.error("Analysis worker did not drain and stop within timeout")
            raise RuntimeError("Analysis worker is still stopping; retry session stop")
        logger.info("Analysis stopped")

    def pause_analysis(self) -> None:
        """Pause analysis without clearing accumulated session state."""
        with self._lock:
            if not self._analysis_active or self._analysis_paused:
                return

            self._unsubscribe_from_events()
            self._analysis_paused = True
            logger.info("Analysis paused")

    def resume_analysis(self) -> None:
        """Resume analysis for the current session."""
        with self._lock:
            if not self._analysis_active or not self._analysis_paused:
                return

            self._subscribe_to_events()
            self._analysis_paused = False
            logger.info("Analysis resumed")

    def analyze_pitch(self, pitch_data: PitchData, config: AppConfig) -> PitchSummary:
        """Analyze a completed pitch and generate summary.

        Performs:
        - Trajectory fitting
        - Speed/spin calculation
        - Strike zone determination
        - Metrics computation

        Args:
            pitch_data: Pitch data from state machine
            config: Application configuration with strike zone settings

        Returns:
            PitchSummary with all computed metrics

        Raises:
            ValueError: If pitch_data is insufficient for analysis

        Note: This is a CPU-intensive operation (50-200ms).
        """
        if not pitch_data.observations:
            raise ValueError("Pitch has no observations")

        # Use analyzer
        summary = self._analyzer.analyze_pitch(
            pitch_id=f"pitch_{pitch_data.pitch_index:05d}",
            start_ns=pitch_data.start_ns,
            end_ns=pitch_data.end_ns,
            observations=pitch_data.observations,
            ray_observations=pitch_data.ray_observations,
        )

        return summary

    def analyze_session(self, session_path: Path) -> SessionSummary:
        """Analyze a recorded session and generate summary.

        Loads session from disk, aggregates pitch summaries, builds heatmap.

        Args:
            session_path: Path to session directory

        Returns:
            SessionSummary with aggregated statistics

        Raises:
            FileNotFoundError: If session directory does not exist
            ValueError: If session data is corrupt

        Note: Can analyze sessions recorded in previous runs.
        """
        if not session_path.exists():
            raise FileNotFoundError(f"Session directory not found: {session_path}")

        summary_path = session_path / "session_summary.json"
        if not summary_path.exists():
            raise FileNotFoundError(f"Session summary not found: {summary_path}")

        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid session summary JSON: {exc}") from exc

        return session_summary_from_dict(payload)

    def detect_patterns(self, session_path: Path, pitcher_id: Optional[str] = None) -> dict:
        """Run pattern detection on a recorded session.

        Integrates with pattern_detection module to analyze:
        - Pitch type classification
        - Anomaly detection
        - Consistency metrics
        - Repertoire analysis

        Args:
            session_path: Path to session directory
            pitcher_id: Optional pitcher identifier for baseline comparison

        Returns:
            PatternAnalysisReport as dict

        Raises:
            FileNotFoundError: If session directory does not exist
            ValueError: If session has insufficient pitches (< 5)

        Note: Generates analysis_report.json and analysis_report.html.
        """
        if not session_path.exists():
            raise FileNotFoundError(f"Session directory not found: {session_path}")

        summary = self.analyze_session(session_path)
        if summary.pitch_count < 5:
            raise ValueError("Session has insufficient pitches (< 5)")

        from analysis.pattern_detection.detector import PatternDetector

        report = PatternDetector().analyze_session(
            session_path=session_path,
            pitcher_id=pitcher_id,
            output_json=True,
            output_html=True,
        )
        return report.to_dict()

    def calculate_strike_result(self, obs: StereoObservation, config: AppConfig) -> StrikeResult:
        """Calculate strike/ball result for an observation.

        Uses plate crossing estimation and strike zone boundaries.

        Args:
            obs: Stereo observation to evaluate
            config: Application configuration with strike zone settings

        Returns:
            StrikeResult with determination and zone location

        Note: This is fast (< 1ms) and can be called on every observation.
        """
        # Build strike zone
        zone = build_strike_zone(
            plate_z_ft=config.metrics.plate_plane_z_ft,
            plate_width_in=config.strike_zone.plate_width_in,
            plate_length_in=config.strike_zone.plate_length_in,
            batter_height_in=self._batter_height_in,
            top_ratio=self._top_ratio,
            bottom_ratio=self._bottom_ratio,
        )

        # Calculate strike
        radius_in = self._get_ball_radius()
        return is_strike([obs], zone, radius_in)

    def get_plate_metrics(self) -> PlateMetricsStub:
        """Get latest plate-gated metrics.

        Returns:
            PlateMetricsStub with plate crossing statistics

        Note: Returns stub if no plate gate configured.
        """
        with self._lock:
            return self._plate_metrics

    def get_session_summary(self) -> SessionSummary:
        """Get current session summary.

        Returns:
            SessionSummary with current session statistics

        Note: Updates in real-time during recording.
        """
        with self._lock:
            if self._session_summary is None:
                return SessionSummary(
                    session_id="none",
                    pitch_count=0,
                    strikes=0,
                    balls=0,
                    heatmap=[[0] * 3 for _ in range(3)],
                    pitches=[],
                )
            return self._session_summary

    def get_recent_pitch_paths(self, count: int = 10) -> List[List[StereoObservation]]:
        """Get observation paths for recent pitches.

        Useful for visualization and debugging.

        Args:
            count: Number of recent pitches to return

        Returns:
            List of pitch paths (each path is list of observations)

        Note: Returns empty list if no pitches recorded.
        """
        with self._lock:
            return list(self._recent_pitch_paths)

    def wait_for_idle(self, timeout: float = 5.0) -> bool:
        """Wait for queued analysis, primarily for shutdown and deterministic tests."""
        return self._analysis_worker.wait_idle(timeout)

    def get_worker_stats(self) -> dict:
        stats = self._analysis_worker.stats()
        attempted = stats.submitted + stats.dropped
        return {
            "submitted": stats.submitted,
            "completed": stats.completed,
            "dropped": stats.dropped,
            "failed": stats.failed,
            "queue_depth": stats.queue_depth,
            "drop_rate": stats.dropped / max(attempted, 1),
            "failure_rate": stats.failed / max(stats.submitted, 1),
        }

    def set_ball_type(self, ball_type: str) -> None:
        """Set ball type for strike detection.

        Args:
            ball_type: "baseball" or "softball"

        Note: Affects strike zone height calculation.
        """
        with self._lock:
            self._ball_type = ball_type
            logger.info(f"Ball type set to: {ball_type}")

    def set_batter_height_in(self, height_in: float) -> None:
        """Set batter height for strike zone calculation.

        Args:
            height_in: Batter height in inches

        Raises:
            ValueError: If height is outside valid range (36-84 inches)

        Note: Strike zone height is based on batter's knees and armpits.
        """
        if not 36 <= height_in <= 84:
            raise ValueError(f"Invalid batter height: {height_in} (must be 36-84 inches)")

        with self._lock:
            self._batter_height_in = height_in
            logger.info(f"Batter height set to: {height_in} inches")

    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        """Set strike zone top/bottom ratios.

        Args:
            top_ratio: Top of zone as fraction of batter height (e.g., 0.7)
            bottom_ratio: Bottom of zone as fraction of batter height (e.g., 0.3)

        Raises:
            ValueError: If ratios are invalid (not in 0-1 range or top < bottom)

        Note: Ratios define zone boundaries relative to batter height.
        """
        if not 0 <= top_ratio <= 1:
            raise ValueError(f"Invalid top_ratio: {top_ratio} (must be 0-1)")
        if not 0 <= bottom_ratio <= 1:
            raise ValueError(f"Invalid bottom_ratio: {bottom_ratio} (must be 0-1)")
        if top_ratio <= bottom_ratio:
            raise ValueError(f"top_ratio ({top_ratio}) must be > bottom_ratio ({bottom_ratio})")

        with self._lock:
            self._top_ratio = top_ratio
            self._bottom_ratio = bottom_ratio
            logger.info(f"Strike zone ratios set: top={top_ratio}, bottom={bottom_ratio}")

    def update_config(self, config: AppConfig) -> None:
        """Update analysis configuration.

        Args:
            config: New application configuration

        Note: Affects future analyses, not past results.
        """
        with self._lock:
            self._config = config
            self._analyzer.update_config(config)
            self._ball_type = config.ball.type
            logger.info("Analysis config updated")

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        """Override radar speed used for future pitch analyses."""
        with self._lock:
            self._manual_speed_mph = speed_mph
            logger.info("Manual speed override updated: %s", speed_mph)

    def get_refinement_summary(self) -> Optional[dict]:
        """Get online calibration refinement summary.

        Returns:
            Dictionary with refinement state and calibration health, or None if disabled

        Note: Includes refined parameters, accumulation progress, and health metrics.
        """
        if not self._refinement_enabled or not self._refiner:
            return None

        return self._refiner.get_refinement_summary()

    # Internal Event Handlers

    def _on_pitch_end_internal(self, event: PitchEndEvent) -> None:
        """Queue pitch analysis so the event publisher is never blocked by fitting."""
        if not self._analysis_worker.submit(event):
            logger.error("Analysis queue dropped pitch %s", event.pitch_id)
            self._publish_unavailable_result(event, "ANALYSIS_QUEUE_DROPPED")

    def _analyze_pitch_end_event(self, event: PitchEndEvent) -> None:
        """Handle PitchEndEvent from EventBus.

        Analyzes pitch and updates session summary.

        Args:
            event: PitchEndEvent with pitch_id, observations, timestamp_ns, duration_ns

        Note: Called from publisher's thread
        """
        if not event.observations:
            logger.warning("Pitch %s has no observations; publishing unavailable verdict", event.pitch_id)
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
                logger.exception("Failed to publish unavailable verdict for pitch %s", event.pitch_id)
            # Unexpected failures must reach BoundedAnalysisWorker so its
            # failure numerator remains honest.
            raise

        # Online refinement is advisory and must not create a second terminal
        # result if it fails after the durable pitch verdict was published.
        if self._refinement_enabled and self._refiner and summary.trajectory_confidence:
            try:
                self._accumulate_trajectory_for_refinement(summary, event)
            except Exception as ref_error:
                logger.warning(f"Error accumulating trajectory for refinement: {ref_error}")

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
            # Legacy scalar fields are structurally required. The UNAVAILABLE
            # status and suppression ledger above prohibit treating them as
            # measurements.
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
            measurement_status="UNAVAILABLE",
            speed_source=None,
            correction_records=[],
            quality_diagnostics=diagnostics,
        )
        return self._publish_terminal_summary(event, summary)

    def _publish_terminal_summary(self, event: PitchEndEvent, summary: PitchSummary) -> bool:
        """Atomically aggregate and publish exactly one terminal event per pitch."""

        with self._lock:
            if event.pitch_id in self._terminal_pitch_ids:
                logger.warning("Ignoring duplicate terminal analysis result for pitch %s", event.pitch_id)
                return False

            measurement_usable = measurement_is_usable(summary)
            current = self._session_summary or SessionSummary(
                session_id="current",
                pitch_count=0,
                strikes=0,
                balls=0,
                heatmap=[[0] * 3 for _ in range(3)],
                pitches=[],
            )
            new_heatmap = [row[:] for row in current.heatmap]
            if (
                measurement_usable
                and summary.zone_row is not None
                and summary.zone_col is not None
                and 0 <= summary.zone_row < len(new_heatmap)
                and 0 <= summary.zone_col < len(new_heatmap[summary.zone_row])
            ):
                new_heatmap[summary.zone_row][summary.zone_col] += 1

            self._pitch_summaries.append(summary)
            self._recent_pitch_paths.append(list(event.observations))
            self._session_summary = SessionSummary(
                session_id=current.session_id,
                pitch_count=current.pitch_count + 1,
                strikes=current.strikes + (1 if measurement_usable and summary.is_strike else 0),
                balls=current.balls + (1 if measurement_usable and not summary.is_strike else 0),
                heatmap=new_heatmap,
                pitches=[*current.pitches, summary],
            )
            self._terminal_pitch_ids.add(event.pitch_id)
            session_summary = self._session_summary

        self._event_bus.publish(
            PitchAnalyzedEvent(
                pitch_id=event.pitch_id,
                summary=summary,
                session_summary=session_summary,
            )
        )
        logger.info(
            "Pitch analysis terminal result: pitch=%s status=%s reasons=%s",
            event.pitch_id,
            summary.measurement_status,
            (summary.quality_diagnostics or {}).get("reason_codes", []),
        )
        return True

    def _accumulate_trajectory_for_refinement(self, summary: PitchSummary, event: PitchEndEvent) -> None:
        """Accumulate trajectory for online calibration refinement.

        Converts PitchSummary to refinement format and checks if refinement should occur.

        Args:
            summary: Pitch summary with trajectory data
            event: Original pitch end event with observations

        Note: time_sync_residual_ns is not currently extracted from trajectory fitting.
        This could be added in the future if systematic time sync bias is detected.
        """
        if not self._refiner:
            return

        # Convert PitchSummary to refinement format
        trajectory_data = {
            "timestamp_ns": summary.t_end_ns,
            "drag_k0_fit": summary.trajectory_drag_param or 0.1,
            "time_sync_residual_ns": 0,  # Not currently extracted from trajectory fitting
            "plate_crossing_z_ft": summary.trajectory_plate_z_ft or 0.0,
            "mean_epipolar_error_px": summary.trajectory_rmse_px or 1.0,
            "max_epipolar_error_px": (summary.trajectory_rmse_px * 1.5) if summary.trajectory_rmse_px else 1.5,
            "num_observations": summary.sample_count,
            "confidence_score": summary.trajectory_confidence or 0.0,
        }

        # Accumulate trajectory
        accepted = self._refiner.accumulate_trajectory(trajectory_data)

        if accepted:
            logger.debug(
                f"Trajectory {summary.pitch_id} accumulated for refinement "
                f"({self._refiner.state.num_trajectories_accumulated} total)"
            )

            # Check if we should refine parameters
            if self._refiner.should_refine():
                result = self._refiner.refine_parameters()

                if result.get("proposed"):
                    logger.warning(
                        "Calibration refinement proposal created in shadow mode; "
                        "configuration was not changed: %s",
                        "; ".join(result["changes"]),
                    )
                    logger.info("Refinement proposal confidence: %.2f", result["confidence"])
                else:
                    logger.info(f"Refinement check: {result['reason']}")

                # Check calibration health
                health = self._refiner.validate_calibration_health()
                if health["alert"]:
                    logger.warning(f"Calibration health alert: {health['reason']}")
                else:
                    logger.debug(f"Calibration health: {health['reason']}")

    # EventBus Subscription Management

    def _subscribe_to_events(self) -> None:
        """Subscribe to EventBus events.

        Called when analysis starts.
        """
        if self._subscribed:
            return

        self._event_bus.subscribe(PitchEndEvent, self._on_pitch_end_internal)

        self._subscribed = True
        logger.info("AnalysisService subscribed to EventBus")

    def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from EventBus events.

        Called when analysis stops.
        """
        if not self._subscribed:
            return

        self._event_bus.unsubscribe(PitchEndEvent, self._on_pitch_end_internal)

        self._subscribed = False
        logger.info("AnalysisService unsubscribed from EventBus")

    # Helper Methods

    def _get_ball_radius(self) -> float:
        """Get current ball radius in inches.

        Returns:
            Ball radius based on ball type
        """
        radii = self._config.ball.radius_in
        return float(radii.get(self._ball_type, radii.get("baseball", 1.45)))

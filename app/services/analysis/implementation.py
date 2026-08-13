"""AnalysisService implementation — thin facade over focused collaborators.

Collaborator modules:
- pitch_terminal: Pitch analysis handler and terminal event publishing
- session_aggregation: Running session summary, heatmap, and recent paths
- refinement: Online calibration refinement accumulation
- worker: Bounded background work queue
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import List, Optional

from app.contracts import PitchSummary, SessionSummary, session_summary_from_dict
from app.events.event_bus import EventBus
from app.events.event_types import PitchEndEvent
from app.pipeline.analysis.pitch_summary import PitchAnalyzer
from app.pipeline.pitch_tracking_v2 import PitchData
from app.services.analysis.interface import AnalysisService
from app.services.analysis.pitch_terminal import PitchTerminalHandler
from app.services.analysis.refinement import RefinementAccumulator
from app.services.analysis.session_aggregation import SessionAggregator
from app.services.analysis.worker import BoundedAnalysisWorker
from configs.settings import AppConfig
from contracts import StereoObservation
from log_config.logger import get_logger
from metrics.simple_metrics import PlateMetricsStub
from metrics.strike_zone import StrikeResult, build_strike_zone, is_strike

logger = get_logger(__name__)


class AnalysisServiceImpl(AnalysisService):
    """Event-driven analysis service facade.

    Thread Safety:
        - All public methods are thread-safe
        - Analysis runs on a bounded worker queue and drains on shutdown
        - Session summary updated atomically via SessionAggregator
    """

    def __init__(self, event_bus: EventBus, config: AppConfig):
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

        # Collaborators
        self._aggregator = SessionAggregator(max_recent=10)
        self._refiner = RefinementAccumulator(config)
        self._terminal_handler = PitchTerminalHandler(
            event_bus=event_bus,
            analyzer=self._analyzer,
            aggregator=self._aggregator,
            refiner=self._refiner,
            lock=self._lock,
        )

        # Latest metrics
        self._plate_metrics = PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)

        # Strike zone configuration
        self._ball_type = config.ball.type
        self._batter_height_in = config.strike_zone.batter_height_in
        self._top_ratio = config.strike_zone.top_ratio
        self._bottom_ratio = config.strike_zone.bottom_ratio
        self._manual_speed_mph: Optional[float] = None

        # EventBus subscription
        self._analysis_active = False
        self._analysis_paused = False
        self._subscribed = False
        self._analysis_worker = BoundedAnalysisWorker(
            self._terminal_handler.handle_pitch_end, max_queue=64
        )

        logger.info("AnalysisService initialized")

    def start_analysis(self, session_id: str = "current") -> None:
        """Start analysis processing."""
        with self._lock:
            if self._analysis_active:
                return

            if not self._analysis_worker.start():
                raise RuntimeError(
                    "Analysis worker from the previous session is still stopping; retry after it exits"
                )

            self._aggregator.reset(session_id)
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
        """Get current session summary."""
        with self._lock:
            return self._aggregator.session_summary

    def get_recent_pitch_paths(self, count: int = 10) -> List[List[StereoObservation]]:
        """Get observation paths for recent pitches."""
        with self._lock:
            return self._aggregator.recent_pitch_paths

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
        """Get online calibration refinement summary."""
        return self._refiner.get_summary()

    # Internal Event Handlers

    def _on_pitch_end_internal(self, event: PitchEndEvent) -> None:
        """Queue pitch analysis so the event publisher is never blocked by fitting."""
        if not self._analysis_worker.submit(event):
            logger.error("Analysis queue dropped pitch %s", event.pitch_id)
            self._terminal_handler._publish_unavailable_result(event, "ANALYSIS_QUEUE_DROPPED")

    # EventBus Subscription Management

    def _subscribe_to_events(self) -> None:
        """Subscribe to EventBus events."""
        if self._subscribed:
            return
        self._event_bus.subscribe(PitchEndEvent, self._on_pitch_end_internal)
        self._subscribed = True
        logger.info("AnalysisService subscribed to EventBus")

    def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from EventBus events."""
        if not self._subscribed:
            return
        self._event_bus.unsubscribe(PitchEndEvent, self._on_pitch_end_internal)
        self._subscribed = False
        logger.info("AnalysisService unsubscribed from EventBus")

    # Helper Methods

    def _get_ball_radius(self) -> float:
        """Get current ball radius in inches."""
        radii = self._config.ball.radius_in
        return float(radii.get(self._ball_type, radii.get("baseball", 1.45)))

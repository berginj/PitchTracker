"""AnalysisService implementation with EventBus integration.

Manages analysis pipeline:
- Pitch trajectory fitting
- Session summary generation
- Pattern detection
- Strike zone calculation
- Metrics computation
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from pathlib import Path
from typing import List, Optional

from app.events.event_bus import EventBus
from app.events.event_types import PitchEndEvent
from app.pipeline.analysis.pitch_summary import PitchAnalyzer
from app.pipeline.pitch_tracking_v2 import PitchData
from app.pipeline_service import PitchSummary, SessionSummary
from app.services.analysis.interface import AnalysisService
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
        - Analysis runs synchronously on PitchEndEvent thread
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
            radar_speed_fn=lambda: None  # No radar speed by default
        )

        # Session state
        self._session_summary: Optional[SessionSummary] = None
        self._pitch_summaries: List[PitchSummary] = []
        self._recent_pitch_paths: deque[List[StereoObservation]] = deque(maxlen=10)

        # Latest metrics
        self._plate_metrics = PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)

        # Strike zone configuration
        self._ball_type = "baseball"
        self._batter_height_in = config.strike_zone.batter_height_in
        self._top_ratio = config.strike_zone.top_ratio
        self._bottom_ratio = config.strike_zone.bottom_ratio

        # EventBus subscription
        self._subscribed = False

        logger.info("AnalysisService initialized")

    def start_analysis(self) -> None:
        """Start analysis processing.

        Subscribes to EventBus for automatic pitch analysis.
        """
        with self._lock:
            if self._subscribed:
                return

            # Initialize session summary
            self._session_summary = SessionSummary(
                session_id="current",
                pitch_count=0,
                strikes=0,
                balls=0,
                heatmap=[[0] * 3 for _ in range(3)],  # 3x3 grid
                pitches=[]
            )
            self._pitch_summaries = []
            self._recent_pitch_paths.clear()

            # Subscribe to EventBus
            self._subscribe_to_events()

            logger.info("Analysis started")

    def stop_analysis(self) -> None:
        """Stop analysis processing.

        Unsubscribes from EventBus.
        """
        with self._lock:
            if not self._subscribed:
                return

            # Unsubscribe from EventBus
            self._unsubscribe_from_events()

            logger.info("Analysis stopped")

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
            observations=pitch_data.observations
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

        # TODO: Load session summary from disk
        # For now, return empty summary
        return SessionSummary(
            session_id=session_path.name,
            pitch_count=0,
            strikes=0,
            balls=0,
            heatmap=[[0] * 3 for _ in range(3)],
            pitches=[]
        )

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

        # TODO: Integrate pattern detection module
        # For now, return empty report
        return {
            "session_id": session_path.name,
            "pitcher_id": pitcher_id,
            "pitch_count": 0,
            "patterns": []
        }

    def calculate_strike_result(
        self,
        obs: StereoObservation,
        config: AppConfig
    ) -> StrikeResult:
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
                    pitches=[]
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
            logger.info("Analysis config updated")

    # Internal Event Handlers

    def _on_pitch_end_internal(self, event: PitchEndEvent) -> None:
        """Handle PitchEndEvent from EventBus.

        Analyzes pitch and updates session summary.

        Args:
            event: PitchEndEvent with pitch_id, observations, timestamp_ns, duration_ns

        Note: Called from publisher's thread
        """
        try:
            # Validate observations
            if not event.observations:
                logger.warning(f"Pitch {event.pitch_id} has no observations, skipping analysis")
                return

            # Analyze pitch directly
            summary = self._analyzer.analyze_pitch(
                pitch_id=event.pitch_id,
                start_ns=event.timestamp_ns - event.duration_ns,
                end_ns=event.timestamp_ns,
                observations=event.observations
            )

            # Update session summary
            with self._lock:
                self._pitch_summaries.append(summary)
                self._recent_pitch_paths.append(event.observations)

                # Update session stats (SessionSummary is frozen, so we need to recreate)
                if self._session_summary is not None:
                    # Update heatmap
                    new_heatmap = [row[:] for row in self._session_summary.heatmap]  # Deep copy
                    if summary.zone_row is not None and summary.zone_col is not None:
                        new_heatmap[summary.zone_row][summary.zone_col] += 1

                    # Update pitches list
                    new_pitches = list(self._session_summary.pitches)
                    new_pitches.append(summary)

                    # Create updated session summary
                    self._session_summary = SessionSummary(
                        session_id=self._session_summary.session_id,
                        pitch_count=self._session_summary.pitch_count + 1,
                        strikes=self._session_summary.strikes + (1 if summary.is_strike else 0),
                        balls=self._session_summary.balls + (0 if summary.is_strike else 1),
                        heatmap=new_heatmap,
                        pitches=new_pitches
                    )

            logger.info(f"Pitch analyzed: {event.pitch_id}, strike={summary.is_strike}")

        except Exception as e:
            logger.error(f"Error analyzing pitch: {e}", exc_info=True)

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
        # Default ball radii
        radii = {
            "baseball": 1.45,  # inches
            "softball": 1.875,  # inches
        }
        return radii.get(self._ball_type, 1.45)

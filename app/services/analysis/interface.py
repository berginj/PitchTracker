"""AnalysisService interface for post-processing and pattern detection.

Responsibility: Analyze pitches, sessions, detect patterns, calculate metrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from app.pipeline_service import PitchSummary, SessionSummary
from app.pipeline.pitch_tracking_v2 import PitchData
from configs.settings import AppConfig
from contracts import StereoObservation
from metrics.simple_metrics import PlateMetricsStub
from metrics.strike_zone import StrikeResult


class AnalysisService(ABC):
    """Abstract interface for analysis service.

    Manages analysis pipeline:
    - Pitch trajectory fitting
    - Session summary generation
    - Pattern detection
    - Strike zone calculation
    - Metrics computation

    Thread-Safety:
        - All methods are thread-safe
        - Can analyze while recording is active
        - Can batch analyze recorded sessions
    """

    @abstractmethod
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

    @abstractmethod
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

    @abstractmethod
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
            PatternAnalysisReport as dict (see analysis.pattern_detection.schemas)

        Raises:
            FileNotFoundError: If session directory does not exist
            ValueError: If session has insufficient pitches (< 5)

        Note: Generates analysis_report.json and analysis_report.html.
        """

    @abstractmethod
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

    @abstractmethod
    def get_plate_metrics(self) -> PlateMetricsStub:
        """Get latest plate-gated metrics.

        Returns:
            PlateMetricsStub with plate crossing statistics

        Note: Returns stub if no plate gate configured.
        """

    @abstractmethod
    def get_session_summary(self) -> SessionSummary:
        """Get current session summary.

        Returns:
            SessionSummary with current session statistics

        Note: Updates in real-time during recording.
        """

    @abstractmethod
    def get_recent_pitch_paths(self, count: int = 10) -> List[List[StereoObservation]]:
        """Get observation paths for recent pitches.

        Useful for visualization and debugging.

        Args:
            count: Number of recent pitches to return

        Returns:
            List of pitch paths (each path is list of observations)

        Note: Returns empty list if no pitches recorded.
        """

    @abstractmethod
    def set_ball_type(self, ball_type: str) -> None:
        """Set ball type for strike detection.

        Args:
            ball_type: "baseball" or "softball"

        Note: Affects strike zone height calculation.
        """

    @abstractmethod
    def set_batter_height_in(self, height_in: float) -> None:
        """Set batter height for strike zone calculation.

        Args:
            height_in: Batter height in inches

        Raises:
            ValueError: If height is outside valid range (36-84 inches)

        Note: Strike zone height is based on batter's knees and armpits.
        """

    @abstractmethod
    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        """Set strike zone top/bottom ratios.

        Args:
            top_ratio: Top of zone as fraction of batter height (e.g., 0.7)
            bottom_ratio: Bottom of zone as fraction of batter height (e.g., 0.3)

        Raises:
            ValueError: If ratios are invalid (not in 0-1 range or top < bottom)

        Note: Ratios define zone boundaries relative to batter height.
        """

    @abstractmethod
    def update_config(self, config: AppConfig) -> None:
        """Update analysis configuration.

        Args:
            config: New application configuration

        Note: Affects future analyses, not past results.
        """

"""Multi-session trend analysis for pitcher performance tracking.

Provides:
- Cross-session performance trend analysis
- Baseline comparison with deviation alerts
- Progress tracking over time
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np

from analysis.pattern_detection.utils import (
    compute_coefficient_of_variation,
    compute_statistics,
    linear_regression,
)

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


@dataclass
class SessionSummary:
    """Summary statistics for a single session."""

    session_id: str
    session_date: str  # ISO format
    pitcher_id: Optional[str]
    total_pitches: int

    # Velocity metrics
    avg_velocity_mph: float
    max_velocity_mph: float
    min_velocity_mph: float
    velocity_std: float

    # Movement metrics
    avg_horizontal_in: float
    avg_vertical_in: float

    # Accuracy metrics
    strike_percentage: float
    consistency_score: float  # 0-1

    # Pitch type breakdown (if classified)
    pitch_type_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "session_date": self.session_date,
            "pitcher_id": self.pitcher_id,
            "total_pitches": self.total_pitches,
            "avg_velocity_mph": self.avg_velocity_mph,
            "max_velocity_mph": self.max_velocity_mph,
            "min_velocity_mph": self.min_velocity_mph,
            "velocity_std": self.velocity_std,
            "avg_horizontal_in": self.avg_horizontal_in,
            "avg_vertical_in": self.avg_vertical_in,
            "strike_percentage": self.strike_percentage,
            "consistency_score": self.consistency_score,
            "pitch_type_counts": self.pitch_type_counts,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SessionSummary":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class TrendReport:
    """Report on trends across multiple sessions."""

    pitcher_id: str
    sessions_analyzed: int
    date_range_start: str
    date_range_end: str

    # Velocity trends
    velocity_trend_mph_per_session: float  # Slope of velocity over time
    velocity_trend_direction: str  # "improving", "declining", "stable"
    velocity_current_vs_peak: float  # Current avg vs best session avg

    # Consistency trends
    consistency_trend: float  # Slope of consistency score
    consistency_direction: str

    # Strike percentage trends
    strike_pct_trend: float
    strike_pct_direction: str

    # Session-by-session data for charting
    session_velocities: List[Tuple[str, float]]  # [(date, avg_velocity), ...]
    session_strike_pcts: List[Tuple[str, float]]
    session_consistency: List[Tuple[str, float]]

    # Alerts
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "pitcher_id": self.pitcher_id,
            "sessions_analyzed": self.sessions_analyzed,
            "date_range_start": self.date_range_start,
            "date_range_end": self.date_range_end,
            "velocity_trend_mph_per_session": self.velocity_trend_mph_per_session,
            "velocity_trend_direction": self.velocity_trend_direction,
            "velocity_current_vs_peak": self.velocity_current_vs_peak,
            "consistency_trend": self.consistency_trend,
            "consistency_direction": self.consistency_direction,
            "strike_pct_trend": self.strike_pct_trend,
            "strike_pct_direction": self.strike_pct_direction,
            "session_velocities": self.session_velocities,
            "session_strike_pcts": self.session_strike_pcts,
            "session_consistency": self.session_consistency,
            "alerts": self.alerts,
        }


@dataclass
class BaselineComparison:
    """Comparison of current session to pitcher baseline."""

    session_id: str
    pitcher_id: str

    # Velocity comparison
    velocity_vs_baseline_pct: float  # +5% means 5% above baseline
    velocity_vs_baseline_status: str  # "above", "normal", "below"

    # Movement comparison
    horizontal_vs_baseline_in: float
    vertical_vs_baseline_in: float
    movement_status: str

    # Accuracy comparison
    strike_pct_vs_baseline: float
    accuracy_status: str

    # Overall assessment
    overall_status: str  # "strong", "normal", "concerning"
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "pitcher_id": self.pitcher_id,
            "velocity_vs_baseline_pct": self.velocity_vs_baseline_pct,
            "velocity_vs_baseline_status": self.velocity_vs_baseline_status,
            "horizontal_vs_baseline_in": self.horizontal_vs_baseline_in,
            "vertical_vs_baseline_in": self.vertical_vs_baseline_in,
            "movement_status": self.movement_status,
            "strike_pct_vs_baseline": self.strike_pct_vs_baseline,
            "accuracy_status": self.accuracy_status,
            "overall_status": self.overall_status,
            "recommendations": self.recommendations,
        }


class TrendAnalyzer:
    """Analyzes performance trends across multiple sessions.

    Tracks:
    - Velocity progression over time
    - Consistency improvements
    - Strike percentage trends
    - Baseline deviations
    """

    # Thresholds for trend classification
    TREND_STABLE_THRESHOLD = 0.5  # mph/session for velocity
    TREND_IMPROVING_THRESHOLD = 0.5
    CONSISTENCY_STABLE_THRESHOLD = 0.02

    # Thresholds for baseline comparison
    BASELINE_NORMAL_THRESHOLD = 0.03  # 3% deviation is normal
    BASELINE_CONCERNING_THRESHOLD = 0.08  # 8% deviation is concerning

    def __init__(self, summaries_dir: Optional[Path] = None):
        """Initialize trend analyzer.

        Args:
            summaries_dir: Directory for session summary storage
        """
        if summaries_dir is None:
            summaries_dir = Path("recordings/summaries")

        self.summaries_dir = Path(summaries_dir)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

    def summarize_session(
        self,
        session_id: str,
        pitches: List["PitchSummary"],
        pitcher_id: Optional[str] = None,
        session_date: Optional[str] = None,
    ) -> SessionSummary:
        """Create summary statistics for a session.

        Args:
            session_id: Session identifier
            pitches: List of pitch summaries from the session
            pitcher_id: Optional pitcher identifier
            session_date: Optional session date (ISO format)

        Returns:
            SessionSummary with computed statistics
        """
        if session_date is None:
            session_date = datetime.now().isoformat()

        # Extract velocity data
        velocities = [p.speed_mph for p in pitches if p.speed_mph is not None]
        velocity_stats = compute_statistics(velocities)

        # Extract movement data
        h_movements = [p.run_in for p in pitches if p.run_in is not None]
        v_movements = [p.rise_in for p in pitches if p.rise_in is not None]

        avg_h = float(np.mean(h_movements)) if h_movements else 0.0
        avg_v = float(np.mean(v_movements)) if v_movements else 0.0

        # Compute strike percentage
        strikes = sum(1 for p in pitches if p.is_strike)
        strike_pct = strikes / len(pitches) if pitches else 0.0

        # Compute consistency score (inverse of coefficient of variation)
        velocity_cv = compute_coefficient_of_variation(velocities)
        consistency_score = max(0.0, min(1.0, 1.0 - velocity_cv))

        # Count pitch types (if classified)
        pitch_type_counts: Dict[str, int] = {}
        for p in pitches:
            if hasattr(p, "pitch_type") and p.pitch_type:
                pitch_type = p.pitch_type
                pitch_type_counts[pitch_type] = pitch_type_counts.get(pitch_type, 0) + 1

        summary = SessionSummary(
            session_id=session_id,
            session_date=session_date,
            pitcher_id=pitcher_id,
            total_pitches=len(pitches),
            avg_velocity_mph=velocity_stats["mean"],
            max_velocity_mph=velocity_stats["max"],
            min_velocity_mph=velocity_stats["min"],
            velocity_std=velocity_stats["std"],
            avg_horizontal_in=avg_h,
            avg_vertical_in=avg_v,
            strike_percentage=strike_pct,
            consistency_score=consistency_score,
            pitch_type_counts=pitch_type_counts,
        )

        # Save summary to disk
        self._save_summary(summary)

        return summary

    def analyze_trends(
        self,
        pitcher_id: str,
        days: int = 30,
        min_sessions: int = 3,
    ) -> Optional[TrendReport]:
        """Analyze trends across multiple sessions for a pitcher.

        Args:
            pitcher_id: Pitcher identifier
            days: Number of days to analyze (default: 30)
            min_sessions: Minimum sessions required for analysis (default: 3)

        Returns:
            TrendReport if enough data, None otherwise
        """
        # Load session summaries for this pitcher
        summaries = self._load_summaries_for_pitcher(pitcher_id, days)

        if len(summaries) < min_sessions:
            return None

        # Sort by date
        summaries.sort(key=lambda s: s.session_date)

        # Extract data series
        dates = [s.session_date for s in summaries]
        velocities = [s.avg_velocity_mph for s in summaries]
        strike_pcts = [s.strike_percentage for s in summaries]
        consistencies = [s.consistency_score for s in summaries]

        # Compute trends using linear regression
        x_indices = list(range(len(summaries)))

        velocity_slope, _ = linear_regression(x_indices, velocities)
        strike_slope, _ = linear_regression(x_indices, strike_pcts)
        consistency_slope, _ = linear_regression(x_indices, consistencies)

        # Classify trends
        velocity_direction = self._classify_trend(
            velocity_slope,
            self.TREND_STABLE_THRESHOLD,
            higher_is_better=True,
        )
        strike_direction = self._classify_trend(
            strike_slope,
            self.CONSISTENCY_STABLE_THRESHOLD,
            higher_is_better=True,
        )
        consistency_direction = self._classify_trend(
            consistency_slope,
            self.CONSISTENCY_STABLE_THRESHOLD,
            higher_is_better=True,
        )

        # Calculate current vs peak velocity
        peak_velocity = max(velocities)
        current_velocity = velocities[-1]
        velocity_vs_peak = (
            (current_velocity - peak_velocity) / peak_velocity * 100
            if peak_velocity > 0
            else 0.0
        )

        # Generate alerts
        alerts = self._generate_trend_alerts(
            velocity_slope,
            velocity_direction,
            strike_slope,
            strike_direction,
            velocity_vs_peak,
        )

        return TrendReport(
            pitcher_id=pitcher_id,
            sessions_analyzed=len(summaries),
            date_range_start=dates[0],
            date_range_end=dates[-1],
            velocity_trend_mph_per_session=velocity_slope,
            velocity_trend_direction=velocity_direction,
            velocity_current_vs_peak=velocity_vs_peak,
            consistency_trend=consistency_slope,
            consistency_direction=consistency_direction,
            strike_pct_trend=strike_slope,
            strike_pct_direction=strike_direction,
            session_velocities=list(zip(dates, velocities)),
            session_strike_pcts=list(zip(dates, strike_pcts)),
            session_consistency=list(zip(dates, consistencies)),
            alerts=alerts,
        )

    def compare_to_baseline(
        self,
        session_summary: SessionSummary,
        baseline_sessions: int = 5,
    ) -> Optional[BaselineComparison]:
        """Compare session to pitcher's baseline performance.

        Args:
            session_summary: Current session summary
            baseline_sessions: Number of recent sessions for baseline (default: 5)

        Returns:
            BaselineComparison if baseline data available, None otherwise
        """
        if not session_summary.pitcher_id:
            return None

        # Load recent sessions for baseline
        recent = self._load_summaries_for_pitcher(
            session_summary.pitcher_id,
            days=90,  # Look back further for baseline
        )

        # Exclude current session and take most recent for baseline
        baseline = [
            s for s in recent
            if s.session_id != session_summary.session_id
        ]

        if len(baseline) < 2:
            return None

        # Use most recent sessions for baseline
        baseline = sorted(baseline, key=lambda s: s.session_date, reverse=True)
        baseline = baseline[:baseline_sessions]

        # Compute baseline averages
        baseline_velocity = float(np.mean([s.avg_velocity_mph for s in baseline]))
        baseline_h_movement = float(np.mean([s.avg_horizontal_in for s in baseline]))
        baseline_v_movement = float(np.mean([s.avg_vertical_in for s in baseline]))
        baseline_strike_pct = float(np.mean([s.strike_percentage for s in baseline]))

        # Compute deviations
        velocity_pct = (
            (session_summary.avg_velocity_mph - baseline_velocity) / baseline_velocity * 100
            if baseline_velocity > 0
            else 0.0
        )
        h_deviation = session_summary.avg_horizontal_in - baseline_h_movement
        v_deviation = session_summary.avg_vertical_in - baseline_v_movement
        strike_deviation = session_summary.strike_percentage - baseline_strike_pct

        # Classify deviations
        velocity_status = self._classify_deviation(
            abs(velocity_pct) / 100,
            "velocity",
            positive=(velocity_pct > 0),
        )
        movement_status = self._classify_movement_deviation(h_deviation, v_deviation)
        accuracy_status = self._classify_deviation(
            abs(strike_deviation),
            "accuracy",
            positive=(strike_deviation > 0),
        )

        # Overall assessment
        overall_status = self._compute_overall_status(
            velocity_status,
            movement_status,
            accuracy_status,
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            velocity_pct,
            h_deviation,
            v_deviation,
            strike_deviation,
        )

        return BaselineComparison(
            session_id=session_summary.session_id,
            pitcher_id=session_summary.pitcher_id,
            velocity_vs_baseline_pct=velocity_pct,
            velocity_vs_baseline_status=velocity_status,
            horizontal_vs_baseline_in=h_deviation,
            vertical_vs_baseline_in=v_deviation,
            movement_status=movement_status,
            strike_pct_vs_baseline=strike_deviation,
            accuracy_status=accuracy_status,
            overall_status=overall_status,
            recommendations=recommendations,
        )

    def _save_summary(self, summary: SessionSummary) -> None:
        """Save session summary to disk.

        Args:
            summary: Summary to save
        """
        # Create pitcher subdirectory if needed
        if summary.pitcher_id:
            pitcher_dir = self.summaries_dir / summary.pitcher_id
        else:
            pitcher_dir = self.summaries_dir / "unknown"

        pitcher_dir.mkdir(parents=True, exist_ok=True)

        # Save with session ID as filename
        summary_path = pitcher_dir / f"{summary.session_id}.json"

        try:
            with open(summary_path, "w") as f:
                json.dump(summary.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving session summary: {e}")

    def _load_summaries_for_pitcher(
        self,
        pitcher_id: str,
        days: int,
    ) -> List[SessionSummary]:
        """Load session summaries for a pitcher.

        Args:
            pitcher_id: Pitcher identifier
            days: Number of days to look back

        Returns:
            List of session summaries
        """
        pitcher_dir = self.summaries_dir / pitcher_id

        if not pitcher_dir.exists():
            return []

        summaries = []
        cutoff_date = datetime.now().isoformat()[:10]  # YYYY-MM-DD

        for summary_file in pitcher_dir.glob("*.json"):
            try:
                with open(summary_file, "r") as f:
                    data = json.load(f)

                summary = SessionSummary.from_dict(data)

                # Check if within date range
                session_date = summary.session_date[:10]  # YYYY-MM-DD
                # Simple date comparison (works for ISO format)
                summaries.append(summary)

            except Exception as e:
                print(f"Error loading summary {summary_file}: {e}")

        return summaries

    def _classify_trend(
        self,
        slope: float,
        threshold: float,
        higher_is_better: bool = True,
    ) -> str:
        """Classify a trend as improving, declining, or stable.

        Args:
            slope: Regression slope
            threshold: Threshold for stable classification
            higher_is_better: Whether higher values are better

        Returns:
            Trend direction string
        """
        if abs(slope) < threshold:
            return "stable"

        if higher_is_better:
            return "improving" if slope > 0 else "declining"
        else:
            return "declining" if slope > 0 else "improving"

    def _classify_deviation(
        self,
        deviation: float,
        metric: str,
        positive: bool,
    ) -> str:
        """Classify deviation from baseline.

        Args:
            deviation: Absolute deviation value
            metric: Metric name for context
            positive: Whether deviation is positive

        Returns:
            Status string
        """
        if deviation < self.BASELINE_NORMAL_THRESHOLD:
            return "normal"
        elif deviation < self.BASELINE_CONCERNING_THRESHOLD:
            return "above" if positive else "below"
        else:
            return "significantly_above" if positive else "significantly_below"

    def _classify_movement_deviation(
        self,
        h_deviation: float,
        v_deviation: float,
    ) -> str:
        """Classify movement deviation.

        Args:
            h_deviation: Horizontal movement deviation (inches)
            v_deviation: Vertical movement deviation (inches)

        Returns:
            Movement status string
        """
        total_deviation = np.sqrt(h_deviation**2 + v_deviation**2)

        if total_deviation < 0.5:
            return "normal"
        elif total_deviation < 1.5:
            return "minor_shift"
        else:
            return "significant_shift"

    def _compute_overall_status(
        self,
        velocity_status: str,
        movement_status: str,
        accuracy_status: str,
    ) -> str:
        """Compute overall session status.

        Args:
            velocity_status: Velocity comparison status
            movement_status: Movement comparison status
            accuracy_status: Accuracy comparison status

        Returns:
            Overall status string
        """
        concerning_statuses = ["significantly_below", "significant_shift"]
        positive_statuses = ["above", "significantly_above"]

        # Count concerning indicators
        concerns = sum(
            1 for s in [velocity_status, movement_status, accuracy_status]
            if s in concerning_statuses
        )

        positives = sum(
            1 for s in [velocity_status, accuracy_status]
            if s in positive_statuses
        )

        if concerns >= 2:
            return "concerning"
        elif positives >= 2 and concerns == 0:
            return "strong"
        else:
            return "normal"

    def _generate_trend_alerts(
        self,
        velocity_slope: float,
        velocity_direction: str,
        strike_slope: float,
        strike_direction: str,
        velocity_vs_peak: float,
    ) -> List[str]:
        """Generate alerts based on trend analysis.

        Args:
            velocity_slope: Velocity trend slope
            velocity_direction: Velocity trend direction
            strike_slope: Strike percentage trend slope
            strike_direction: Strike percentage trend direction
            velocity_vs_peak: Current velocity vs peak (percentage)

        Returns:
            List of alert messages
        """
        alerts = []

        # Velocity alerts
        if velocity_direction == "declining" and velocity_slope < -1.0:
            alerts.append(
                f"Velocity declining at {abs(velocity_slope):.1f} mph per session"
            )

        if velocity_vs_peak < -10:
            alerts.append(
                f"Current velocity {abs(velocity_vs_peak):.1f}% below peak performance"
            )

        # Strike percentage alerts
        if strike_direction == "declining" and strike_slope < -0.05:
            alerts.append("Strike percentage trending downward")

        # Positive alerts
        if velocity_direction == "improving" and velocity_slope > 1.0:
            alerts.append(
                f"Velocity improving at {velocity_slope:.1f} mph per session"
            )

        if strike_direction == "improving" and strike_slope > 0.03:
            alerts.append("Strike percentage trending upward")

        return alerts

    def _generate_recommendations(
        self,
        velocity_pct: float,
        h_deviation: float,
        v_deviation: float,
        strike_deviation: float,
    ) -> List[str]:
        """Generate recommendations based on baseline comparison.

        Args:
            velocity_pct: Velocity vs baseline percentage
            h_deviation: Horizontal movement deviation
            v_deviation: Vertical movement deviation
            strike_deviation: Strike percentage deviation

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Velocity recommendations
        if velocity_pct < -5:
            recommendations.append(
                "Velocity below baseline - check for fatigue or mechanical issues"
            )
        elif velocity_pct > 8:
            recommendations.append(
                "Velocity above baseline - maintain current approach"
            )

        # Movement recommendations
        total_movement = np.sqrt(h_deviation**2 + v_deviation**2)
        if total_movement > 1.5:
            recommendations.append(
                "Significant movement variation - review release point consistency"
            )

        # Strike percentage recommendations
        if strike_deviation < -0.10:
            recommendations.append(
                "Strike percentage below baseline - focus on command"
            )
        elif strike_deviation > 0.10:
            recommendations.append(
                "Strong strike percentage - consider expanding zone usage"
            )

        return recommendations


__all__ = [
    "SessionSummary",
    "TrendReport",
    "BaselineComparison",
    "TrendAnalyzer",
]

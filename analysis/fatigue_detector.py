"""Real-time fatigue detection for pitchers during sessions.

Analyzes recent pitch data to detect signs of fatigue including:
- Velocity decline from session start
- Release point drift
- Movement consistency variance
- Composite fatigue scoring with recommendations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple


from analysis.pattern_detection.utils import (
    compute_coefficient_of_variation,
    compute_statistics,
    linear_regression,
)

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary
    from analysis.pattern_detection.pitcher_profile import ProfileMetrics


@dataclass(frozen=True)
class FatigueMetrics:
    """Fatigue indicators computed from recent pitch data.

    Attributes:
        velocity_drop_pct: Percentage drop from session start velocity
        velocity_trend_mph_per_pitch: Rate of velocity change (negative = declining)
        movement_variance_pct: Increase in movement inconsistency vs session start
        trajectory_quality_drop: Decline in trajectory confidence
        fatigue_score: Composite score 0-100 (higher = more fatigued)
        recommendation: Action recommendation ("Continue" / "Monitor" / "Rest")
        contributing_factors: List of factors contributing to fatigue score
    """

    velocity_drop_pct: float
    velocity_trend_mph_per_pitch: float
    movement_variance_pct: float
    trajectory_quality_drop: float
    fatigue_score: float
    recommendation: str
    contributing_factors: List[str] = field(default_factory=list)
    available: bool = True


class FatigueDetector:
    """Detects pitcher fatigue in real-time during sessions.

    Uses a rolling window of recent pitches to compare against:
    - Session start baseline (first N pitches)
    - Optional pitcher profile baseline for context

    Typical usage:
        detector = FatigueDetector()
        metrics = detector.analyze(session_pitches[-10:], session_pitches)
    """

    # Configuration
    BASELINE_WINDOW = 5  # First N pitches establish session baseline
    ROLLING_WINDOW = 10  # Recent pitches for current analysis

    # Fatigue thresholds
    VELOCITY_DROP_YELLOW = 3.0  # % drop triggers monitoring
    VELOCITY_DROP_RED = 6.0  # % drop triggers rest recommendation
    MOVEMENT_VAR_YELLOW = 50.0  # % increase in variance triggers monitoring
    MOVEMENT_VAR_RED = 100.0  # % increase triggers rest
    TRAJECTORY_DROP_YELLOW = 0.10  # Confidence drop triggers monitoring
    TRAJECTORY_DROP_RED = 0.20  # Confidence drop triggers rest

    # Score weights
    WEIGHT_VELOCITY = 0.55
    WEIGHT_MOVEMENT = 0.30
    WEIGHT_TRAJECTORY = 0.0
    WEIGHT_TREND = 0.15

    def __init__(
        self,
        baseline_window: int = BASELINE_WINDOW,
        rolling_window: int = ROLLING_WINDOW,
    ):
        """Initialize fatigue detector.

        Args:
            baseline_window: Number of initial pitches for baseline
            rolling_window: Number of recent pitches to analyze
        """
        self.baseline_window = baseline_window
        self.rolling_window = rolling_window

    def analyze(
        self,
        recent_pitches: List["PitchSummary"],
        all_session_pitches: Optional[List["PitchSummary"]] = None,
        profile_baseline: Optional["ProfileMetrics"] = None,
    ) -> FatigueMetrics:
        """Analyze recent pitches for fatigue indicators.

        Args:
            recent_pitches: Last N pitches (rolling window)
            all_session_pitches: All pitches in session (for baseline comparison)
            profile_baseline: Optional pitcher profile for context

        Returns:
            FatigueMetrics with fatigue indicators and recommendation
        """
        if not recent_pitches:
            return self._empty_metrics()

        # Fatigue is an athlete claim. Only compare usable measurements with
        # one explicit, consistent speed provenance across the session window.
        session_pitches = [
            pitch
            for pitch in (all_session_pitches or recent_pitches)
            if getattr(pitch, "measurement_status", "ESTIMATED") not in {"REJECTED", "UNAVAILABLE"}
            and pitch.speed_mph is not None
        ]
        sources = {getattr(pitch, "speed_source", None) for pitch in session_pitches}
        if not session_pitches or None in sources or len(sources) != 1:
            return self._empty_metrics("Comparable speed provenance is unavailable")
        recent_pitches = [
            pitch
            for pitch in recent_pitches
            if getattr(pitch, "measurement_status", "ESTIMATED") not in {"REJECTED", "UNAVAILABLE"}
            and pitch.speed_mph is not None
            and getattr(pitch, "speed_source", None) in sources
        ]

        # Establish baseline from first N pitches
        baseline_pitches = session_pitches[: self.baseline_window]
        if len(baseline_pitches) < 3:
            # Not enough data for meaningful baseline
            return self._empty_metrics()

        # Compute baseline statistics
        baseline_stats = self._compute_window_stats(baseline_pitches)
        recent_stats = self._compute_window_stats(recent_pitches)

        # Calculate individual fatigue metrics
        velocity_drop = self._compute_velocity_drop(baseline_stats, recent_stats)
        velocity_trend = self._compute_velocity_trend(session_pitches)
        movement_variance = self._compute_movement_variance_change(baseline_stats, recent_stats)
        # Trajectory confidence is measurement-system health, not evidence of
        # athlete fatigue. Keep the compatibility field at zero and surface
        # confidence decay through runtime quality diagnostics instead.
        trajectory_drop = 0.0

        # Calculate composite score and recommendation
        score, factors = self._compute_fatigue_score(velocity_drop, velocity_trend, movement_variance, trajectory_drop)
        recommendation = self._get_recommendation(score)

        return FatigueMetrics(
            velocity_drop_pct=velocity_drop,
            velocity_trend_mph_per_pitch=velocity_trend,
            movement_variance_pct=movement_variance,
            trajectory_quality_drop=trajectory_drop,
            fatigue_score=score,
            recommendation=recommendation,
            contributing_factors=factors,
        )

    def _compute_window_stats(self, pitches: List["PitchSummary"]) -> Dict[str, Any]:
        """Compute statistics for a window of pitches.

        Args:
            pitches: List of pitch summaries

        Returns:
            Dictionary with velocity, movement, and trajectory stats
        """
        # Extract data
        velocities = [p.speed_mph for p in pitches if p.speed_mph is not None]
        # Legacy run/rise fields are raw endpoint displacement unless a
        # validated movement algorithm explicitly marks them usable. Raw camera
        # displacement must not be converted into an athlete-fatigue claim.
        validated_movement = [
            p
            for p in pitches
            if bool((getattr(p, "quality_diagnostics", None) or {}).get("movement_validated", False))
        ]
        h_movements = [p.run_in for p in validated_movement]
        v_movements = [p.rise_in for p in validated_movement]
        trajectory_confs = [p.trajectory_confidence for p in pitches if p.trajectory_confidence is not None]

        return {
            "velocity": compute_statistics(velocities),
            "h_movement": compute_statistics(h_movements),
            "v_movement": compute_statistics(v_movements),
            "trajectory_conf": compute_statistics(trajectory_confs),
            "velocity_cv": compute_coefficient_of_variation(velocities),
            "h_movement_cv": compute_coefficient_of_variation(h_movements),
            "v_movement_cv": compute_coefficient_of_variation(v_movements),
        }

    def _compute_velocity_drop(
        self,
        baseline_stats: Dict[str, Any],
        recent_stats: Dict[str, Any],
    ) -> float:
        """Compute percentage velocity drop from baseline.

        Args:
            baseline_stats: Baseline window statistics
            recent_stats: Recent window statistics

        Returns:
            Percentage drop (positive = slower)
        """
        baseline_mean = baseline_stats["velocity"]["mean"]
        recent_mean = recent_stats["velocity"]["mean"]

        if baseline_mean <= 0:
            return 0.0

        drop_pct = ((baseline_mean - recent_mean) / baseline_mean) * 100
        return float(max(0.0, drop_pct))  # Only positive drops indicate fatigue

    def _compute_velocity_trend(self, pitches: List["PitchSummary"]) -> float:
        """Compute velocity trend over session (mph per pitch).

        Args:
            pitches: All session pitches

        Returns:
            Slope of velocity trend (negative = declining)
        """
        velocities = [p.speed_mph for p in pitches if p.speed_mph is not None]
        if len(velocities) < 5:
            return 0.0

        pitch_numbers = [float(index) for index in range(len(velocities))]
        slope, _ = linear_regression(pitch_numbers, velocities)
        return slope

    def _compute_movement_variance_change(
        self,
        baseline_stats: Dict[str, Any],
        recent_stats: Dict[str, Any],
    ) -> float:
        """Compute percentage increase in movement variance.

        Higher variance suggests less consistent mechanics (fatigue indicator).

        Args:
            baseline_stats: Baseline window statistics
            recent_stats: Recent window statistics

        Returns:
            Percentage increase in combined movement CV
        """
        # Combine horizontal and vertical CVs
        baseline_cv = (baseline_stats.get("h_movement_cv", 0) + baseline_stats.get("v_movement_cv", 0)) / 2

        recent_cv = (recent_stats.get("h_movement_cv", 0) + recent_stats.get("v_movement_cv", 0)) / 2

        if baseline_cv <= 0:
            return 0.0

        variance_increase = ((recent_cv - baseline_cv) / baseline_cv) * 100
        return float(max(0.0, variance_increase))  # Only increases indicate fatigue

    def _compute_trajectory_quality_drop(
        self,
        baseline_stats: Dict[str, Any],
        recent_stats: Dict[str, Any],
    ) -> float:
        """Compute drop in trajectory confidence.

        Lower trajectory quality suggests less clean ball flight.

        Args:
            baseline_stats: Baseline window statistics
            recent_stats: Recent window statistics

        Returns:
            Absolute drop in confidence (0.0-1.0 scale)
        """
        baseline_conf = baseline_stats["trajectory_conf"]["mean"]
        recent_conf = recent_stats["trajectory_conf"]["mean"]

        drop = baseline_conf - recent_conf
        return float(max(0.0, drop))  # Only drops indicate concern

    def _compute_fatigue_score(
        self,
        velocity_drop: float,
        velocity_trend: float,
        movement_variance: float,
        trajectory_drop: float,
    ) -> Tuple[float, List[str]]:
        """Compute composite fatigue score (0-100).

        Args:
            velocity_drop: Percentage velocity drop
            velocity_trend: Velocity trend per pitch
            movement_variance: Percentage variance increase
            trajectory_drop: Trajectory confidence drop

        Returns:
            Tuple of (fatigue_score, contributing_factors)
        """
        factors = []

        # Normalize each component to 0-100 scale
        velocity_score = min(100, (velocity_drop / self.VELOCITY_DROP_RED) * 100)
        if velocity_drop >= self.VELOCITY_DROP_YELLOW:
            factors.append(f"Velocity down {velocity_drop:.1f}%")

        # Negative trend contributes to fatigue
        trend_contribution = max(0, -velocity_trend * 10)  # -0.1 mph/pitch = 10 score
        trend_score = min(100, trend_contribution)
        if velocity_trend < -0.05:
            factors.append(f"Declining velocity trend ({velocity_trend:.2f} mph/pitch)")

        movement_score = min(100, (movement_variance / self.MOVEMENT_VAR_RED) * 100)
        if movement_variance >= self.MOVEMENT_VAR_YELLOW:
            factors.append(f"Movement variance up {movement_variance:.0f}%")

        # Weighted composite score
        composite = (
            velocity_score * self.WEIGHT_VELOCITY
            + trend_score * self.WEIGHT_TREND
            + movement_score * self.WEIGHT_MOVEMENT
        )

        return min(100, composite), factors

    def _get_recommendation(self, fatigue_score: float) -> str:
        """Get action recommendation based on fatigue score.

        Args:
            fatigue_score: Composite fatigue score (0-100)

        Returns:
            Recommendation string
        """
        if fatigue_score < 30:
            return "Continue"
        elif fatigue_score < 60:
            return "Monitor"
        else:
            return "Rest"

    def _empty_metrics(self, reason: str = "Insufficient data for analysis") -> FatigueMetrics:
        """Return metrics indicating insufficient data."""
        return FatigueMetrics(
            velocity_drop_pct=0.0,
            velocity_trend_mph_per_pitch=0.0,
            movement_variance_pct=0.0,
            trajectory_quality_drop=0.0,
            fatigue_score=0.0,
            recommendation="Unavailable",
            contributing_factors=[reason],
            available=False,
        )


def analyze_session_fatigue(
    pitches: List["PitchSummary"],
    window_size: int = 10,
) -> List[FatigueMetrics]:
    """Analyze fatigue progression throughout a session.

    Useful for post-session analysis to identify when fatigue set in.

    Args:
        pitches: All session pitches
        window_size: Rolling window size

    Returns:
        List of FatigueMetrics, one per pitch starting at window_size
    """
    if len(pitches) < window_size:
        return []

    detector = FatigueDetector(rolling_window=window_size)
    results = []

    for i in range(window_size, len(pitches) + 1):
        recent = pitches[i - window_size : i]
        metrics = detector.analyze(recent, pitches[:i])
        results.append(metrics)

    return results


__all__ = [
    "FatigueMetrics",
    "FatigueDetector",
    "analyze_session_fatigue",
]

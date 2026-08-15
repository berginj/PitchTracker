"""Multi-session trend analysis for pitcher performance tracking."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from analysis.trend_classification import (
    classify_deviation,
    classify_movement_deviation,
    classify_trend,
    compute_overall_status,
    generate_recommendations,
    generate_trend_alerts,
)
from analysis.trend_models import BaselineComparison, SessionSummary, TrendReport
from analysis.trend_reports import build_baseline_comparison, build_trend_report
from analysis.trend_statistics import aggregate_session

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


class TrendAnalyzer:
    """Analyze performance trends across multiple sessions."""

    TREND_STABLE_THRESHOLD = 0.5
    TREND_IMPROVING_THRESHOLD = 0.5
    CONSISTENCY_STABLE_THRESHOLD = 0.02
    BASELINE_NORMAL_THRESHOLD = 0.03
    BASELINE_CONCERNING_THRESHOLD = 0.08

    def __init__(self, summaries_dir: Optional[Path] = None):
        """Initialize trend analyzer and its summary storage."""
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
        """Create, persist, and return statistics for a session."""
        metrics = aggregate_session(pitches)
        if session_date is None:
            session_date = datetime.now().isoformat()
        summary = SessionSummary(
            session_id=session_id,
            session_date=session_date,
            pitcher_id=pitcher_id,
            total_pitches=len(pitches),
            avg_velocity_mph=metrics.avg_velocity_mph,
            max_velocity_mph=metrics.max_velocity_mph,
            min_velocity_mph=metrics.min_velocity_mph,
            velocity_std=metrics.velocity_std,
            avg_horizontal_in=metrics.avg_horizontal_in,
            avg_vertical_in=metrics.avg_vertical_in,
            strike_percentage=metrics.strike_percentage,
            consistency_score=metrics.consistency_score,
            pitch_type_counts=metrics.pitch_type_counts,
        )
        self._save_summary(summary)
        return summary

    def analyze_trends(
        self,
        pitcher_id: str,
        days: int = 30,
        min_sessions: int = 3,
    ) -> Optional[TrendReport]:
        """Analyze date-ordered performance trends for a pitcher."""
        summaries = self._load_summaries_for_pitcher(pitcher_id, days)
        if len(summaries) < min_sessions:
            return None
        summaries.sort(key=lambda summary: summary.session_date)
        return build_trend_report(
            pitcher_id,
            summaries,
            self.TREND_STABLE_THRESHOLD,
            self.CONSISTENCY_STABLE_THRESHOLD,
        )

    def compare_to_baseline(
        self,
        session_summary: SessionSummary,
        baseline_sessions: int = 5,
    ) -> Optional[BaselineComparison]:
        """Compare a session to the pitcher's most recent baseline."""
        if not session_summary.pitcher_id:
            return None
        recent = self._load_summaries_for_pitcher(session_summary.pitcher_id, days=90)
        baseline = [summary for summary in recent if summary.session_id != session_summary.session_id]
        if len(baseline) < 2:
            return None
        baseline.sort(key=lambda summary: summary.session_date, reverse=True)
        return build_baseline_comparison(
            session_summary,
            baseline[:baseline_sessions],
            self.BASELINE_NORMAL_THRESHOLD,
            self.BASELINE_CONCERNING_THRESHOLD,
        )

    def _save_summary(self, summary: SessionSummary) -> None:
        """Save a session summary to its pitcher directory."""
        pitcher_dir = self.summaries_dir / (summary.pitcher_id or "unknown")
        pitcher_dir.mkdir(parents=True, exist_ok=True)
        summary_path = pitcher_dir / f"{summary.session_id}.json"
        try:
            with summary_path.open("w") as handle:
                json.dump(summary.to_dict(), handle, indent=2)
        except (OSError, TypeError, ValueError) as exc:
            print(f"Error saving session summary: {exc}")

    def _load_summaries_for_pitcher(
        self,
        pitcher_id: str,
        days: int,
    ) -> List[SessionSummary]:
        """Load valid stored summaries for a pitcher."""
        pitcher_dir = self.summaries_dir / pitcher_id
        if not pitcher_dir.exists():
            return []
        summaries: List[SessionSummary] = []
        for summary_file in pitcher_dir.glob("*.json"):
            try:
                with summary_file.open("r") as handle:
                    summaries.append(SessionSummary.from_dict(json.load(handle)))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                print(f"Error loading summary {summary_file}: {exc}")
        return summaries

    def _classify_trend(
        self,
        slope: float,
        threshold: float,
        higher_is_better: bool = True,
    ) -> str:
        """Classify a regression slope."""
        return classify_trend(slope, threshold, higher_is_better)

    def _classify_deviation(
        self,
        deviation: float,
        metric: str,
        positive: bool,
    ) -> str:
        """Classify an absolute baseline deviation."""
        return classify_deviation(
            deviation,
            positive,
            self.BASELINE_NORMAL_THRESHOLD,
            self.BASELINE_CONCERNING_THRESHOLD,
        )

    def _classify_movement_deviation(
        self,
        h_deviation: float,
        v_deviation: float,
    ) -> str:
        """Classify a movement deviation in inches."""
        return classify_movement_deviation(h_deviation, v_deviation)

    def _compute_overall_status(
        self,
        velocity_status: str,
        movement_status: str,
        accuracy_status: str,
    ) -> str:
        """Combine metric classifications into an overall status."""
        return compute_overall_status(velocity_status, movement_status, accuracy_status)

    def _generate_trend_alerts(
        self,
        velocity_slope: float,
        velocity_direction: str,
        strike_slope: float,
        strike_direction: str,
        velocity_vs_peak: float,
    ) -> List[str]:
        """Generate trend alerts."""
        return generate_trend_alerts(
            velocity_slope,
            velocity_direction,
            strike_slope,
            strike_direction,
            velocity_vs_peak,
        )

    def _generate_recommendations(
        self,
        velocity_pct: float,
        h_deviation: float,
        v_deviation: float,
        strike_deviation: float,
    ) -> List[str]:
        """Generate baseline recommendations."""
        return generate_recommendations(
            velocity_pct,
            h_deviation,
            v_deviation,
            strike_deviation,
        )


__all__ = [
    "SessionSummary",
    "TrendReport",
    "BaselineComparison",
    "TrendAnalyzer",
]

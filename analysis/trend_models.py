"""Serializable data models for multi-session trend analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SessionSummary:
    """Summary statistics for a single session."""

    session_id: str
    session_date: str
    pitcher_id: Optional[str]
    total_pitches: int
    avg_velocity_mph: float
    max_velocity_mph: float
    min_velocity_mph: float
    velocity_std: float
    avg_horizontal_in: float
    avg_vertical_in: float
    strike_percentage: float
    consistency_score: float
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
    velocity_trend_mph_per_session: float
    velocity_trend_direction: str
    velocity_current_vs_peak: float
    consistency_trend: float
    consistency_direction: str
    strike_pct_trend: float
    strike_pct_direction: str
    session_velocities: List[Tuple[str, float]]
    session_strike_pcts: List[Tuple[str, float]]
    session_consistency: List[Tuple[str, float]]
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
    velocity_vs_baseline_pct: float
    velocity_vs_baseline_status: str
    horizontal_vs_baseline_in: float
    vertical_vs_baseline_in: float
    movement_status: str
    strike_pct_vs_baseline: float
    accuracy_status: str
    overall_status: str
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


__all__ = ["SessionSummary", "TrendReport", "BaselineComparison"]

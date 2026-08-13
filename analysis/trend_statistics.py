"""Aggregation and statistical calculations for trend analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np

from analysis.pattern_detection.utils import (
    compute_coefficient_of_variation,
    compute_statistics,
    linear_regression,
)
from analysis.trend_models import SessionSummary


@dataclass(frozen=True)
class SessionMetrics:
    """Computed metrics used to construct a session summary."""

    avg_velocity_mph: float
    max_velocity_mph: float
    min_velocity_mph: float
    velocity_std: float
    avg_horizontal_in: float
    avg_vertical_in: float
    strike_percentage: float
    consistency_score: float
    pitch_type_counts: dict[str, int]


@dataclass(frozen=True)
class TrendSeries:
    """Ordered session series and their regression slopes."""

    dates: List[str]
    velocities: List[float]
    strike_pcts: List[float]
    consistencies: List[float]
    velocity_slope: float
    strike_slope: float
    consistency_slope: float
    velocity_vs_peak: float


@dataclass(frozen=True)
class BaselineMetrics:
    """Baseline means and current-session deviations."""

    velocity_pct: float
    horizontal_deviation: float
    vertical_deviation: float
    strike_deviation: float


def aggregate_session(pitches: Sequence[object]) -> SessionMetrics:
    """Aggregate available pitch measurements without imputing missing data."""
    velocities = [p.speed_mph for p in pitches if p.speed_mph is not None]
    velocity_stats = compute_statistics(velocities)
    h_movements = [p.run_in for p in pitches if p.run_in is not None]
    v_movements = [p.rise_in for p in pitches if p.rise_in is not None]
    strike_pct = sum(1 for p in pitches if p.is_strike) / len(pitches) if pitches else 0.0
    velocity_cv = compute_coefficient_of_variation(velocities)

    return SessionMetrics(
        avg_velocity_mph=velocity_stats["mean"],
        max_velocity_mph=velocity_stats["max"],
        min_velocity_mph=velocity_stats["min"],
        velocity_std=velocity_stats["std"],
        avg_horizontal_in=_mean_or_zero(h_movements),
        avg_vertical_in=_mean_or_zero(v_movements),
        strike_percentage=strike_pct,
        consistency_score=max(0.0, min(1.0, 1.0 - velocity_cv)),
        pitch_type_counts=_count_pitch_types(pitches),
    )


def compute_trend_series(summaries: Sequence[SessionSummary]) -> TrendSeries:
    """Compute ordered chart series and per-session linear trends."""
    dates = [summary.session_date for summary in summaries]
    velocities = [summary.avg_velocity_mph for summary in summaries]
    strike_pcts = [summary.strike_percentage for summary in summaries]
    consistencies = [summary.consistency_score for summary in summaries]
    indices = list(range(len(summaries)))
    velocity_slope, _ = linear_regression(indices, velocities)
    strike_slope, _ = linear_regression(indices, strike_pcts)
    consistency_slope, _ = linear_regression(indices, consistencies)
    peak_velocity = max(velocities)
    velocity_vs_peak = (velocities[-1] - peak_velocity) / peak_velocity * 100 if peak_velocity > 0 else 0.0

    return TrendSeries(
        dates=dates,
        velocities=velocities,
        strike_pcts=strike_pcts,
        consistencies=consistencies,
        velocity_slope=velocity_slope,
        strike_slope=strike_slope,
        consistency_slope=consistency_slope,
        velocity_vs_peak=velocity_vs_peak,
    )


def compute_baseline_metrics(
    session_summary: SessionSummary,
    baseline: Sequence[SessionSummary],
) -> BaselineMetrics:
    """Compute deviations from the supplied recent-session baseline."""
    baseline_velocity = float(np.mean([s.avg_velocity_mph for s in baseline]))
    baseline_h_movement = float(np.mean([s.avg_horizontal_in for s in baseline]))
    baseline_v_movement = float(np.mean([s.avg_vertical_in for s in baseline]))
    baseline_strike_pct = float(np.mean([s.strike_percentage for s in baseline]))
    velocity_pct = (
        (session_summary.avg_velocity_mph - baseline_velocity) / baseline_velocity * 100
        if baseline_velocity > 0
        else 0.0
    )
    return BaselineMetrics(
        velocity_pct=velocity_pct,
        horizontal_deviation=session_summary.avg_horizontal_in - baseline_h_movement,
        vertical_deviation=session_summary.avg_vertical_in - baseline_v_movement,
        strike_deviation=session_summary.strike_percentage - baseline_strike_pct,
    )


def chart_points(dates: List[str], values: List[float]) -> List[Tuple[str, float]]:
    """Pair dates and values while retaining the historical list shape."""
    return list(zip(dates, values))


def _mean_or_zero(values: Sequence[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _count_pitch_types(pitches: Sequence[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pitch in pitches:
        pitch_type = getattr(pitch, "pitch_type", None)
        if pitch_type:
            counts[pitch_type] = counts.get(pitch_type, 0) + 1
    return counts

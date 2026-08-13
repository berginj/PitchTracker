"""Construction of trend reports and baseline comparisons."""

from __future__ import annotations

from typing import Sequence

from analysis.trend_classification import (
    classify_deviation,
    classify_movement_deviation,
    classify_trend,
    compute_overall_status,
    generate_recommendations,
    generate_trend_alerts,
)
from analysis.trend_models import BaselineComparison, SessionSummary, TrendReport
from analysis.trend_statistics import (
    chart_points,
    compute_baseline_metrics,
    compute_trend_series,
)


def build_trend_report(
    pitcher_id: str,
    summaries: Sequence[SessionSummary],
    velocity_stable_threshold: float,
    consistency_stable_threshold: float,
) -> TrendReport:
    """Construct a trend report from date-ordered session summaries."""
    series = compute_trend_series(summaries)
    velocity_direction = classify_trend(series.velocity_slope, velocity_stable_threshold)
    strike_direction = classify_trend(series.strike_slope, consistency_stable_threshold)
    consistency_direction = classify_trend(series.consistency_slope, consistency_stable_threshold)
    alerts = generate_trend_alerts(
        series.velocity_slope,
        velocity_direction,
        series.strike_slope,
        strike_direction,
        series.velocity_vs_peak,
    )
    return TrendReport(
        pitcher_id=pitcher_id,
        sessions_analyzed=len(summaries),
        date_range_start=series.dates[0],
        date_range_end=series.dates[-1],
        velocity_trend_mph_per_session=series.velocity_slope,
        velocity_trend_direction=velocity_direction,
        velocity_current_vs_peak=series.velocity_vs_peak,
        consistency_trend=series.consistency_slope,
        consistency_direction=consistency_direction,
        strike_pct_trend=series.strike_slope,
        strike_pct_direction=strike_direction,
        session_velocities=chart_points(series.dates, series.velocities),
        session_strike_pcts=chart_points(series.dates, series.strike_pcts),
        session_consistency=chart_points(series.dates, series.consistencies),
        alerts=alerts,
    )


def build_baseline_comparison(
    session_summary: SessionSummary,
    baseline: Sequence[SessionSummary],
    normal_threshold: float,
    concerning_threshold: float,
) -> BaselineComparison:
    """Construct a comparison from a current session and baseline sessions."""
    metrics = compute_baseline_metrics(session_summary, baseline)
    velocity_status = classify_deviation(
        abs(metrics.velocity_pct) / 100,
        metrics.velocity_pct > 0,
        normal_threshold,
        concerning_threshold,
    )
    movement_status = classify_movement_deviation(
        metrics.horizontal_deviation,
        metrics.vertical_deviation,
    )
    accuracy_status = classify_deviation(
        abs(metrics.strike_deviation),
        metrics.strike_deviation > 0,
        normal_threshold,
        concerning_threshold,
    )
    return BaselineComparison(
        session_id=session_summary.session_id,
        pitcher_id=session_summary.pitcher_id or "",
        velocity_vs_baseline_pct=metrics.velocity_pct,
        velocity_vs_baseline_status=velocity_status,
        horizontal_vs_baseline_in=metrics.horizontal_deviation,
        vertical_vs_baseline_in=metrics.vertical_deviation,
        movement_status=movement_status,
        strike_pct_vs_baseline=metrics.strike_deviation,
        accuracy_status=accuracy_status,
        overall_status=compute_overall_status(
            velocity_status,
            movement_status,
            accuracy_status,
        ),
        recommendations=generate_recommendations(
            metrics.velocity_pct,
            metrics.horizontal_deviation,
            metrics.vertical_deviation,
            metrics.strike_deviation,
        ),
    )

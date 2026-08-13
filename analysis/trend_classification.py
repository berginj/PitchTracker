"""Trend, deviation, alert, and recommendation classification rules."""

from __future__ import annotations

from typing import List

import numpy as np


def classify_trend(slope: float, threshold: float, higher_is_better: bool = True) -> str:
    """Classify a regression slope as improving, declining, or stable."""
    if abs(slope) < threshold:
        return "stable"
    if higher_is_better:
        return "improving" if slope > 0 else "declining"
    return "declining" if slope > 0 else "improving"


def classify_deviation(
    deviation: float,
    positive: bool,
    normal_threshold: float,
    concerning_threshold: float,
) -> str:
    """Classify an absolute baseline deviation."""
    if deviation < normal_threshold:
        return "normal"
    if deviation < concerning_threshold:
        return "above" if positive else "below"
    return "significantly_above" if positive else "significantly_below"


def classify_movement_deviation(h_deviation: float, v_deviation: float) -> str:
    """Classify the magnitude of a two-dimensional movement shift."""
    total_deviation = np.sqrt(h_deviation**2 + v_deviation**2)
    if total_deviation < 0.5:
        return "normal"
    if total_deviation < 1.5:
        return "minor_shift"
    return "significant_shift"


def compute_overall_status(
    velocity_status: str,
    movement_status: str,
    accuracy_status: str,
) -> str:
    """Combine baseline indicators into the historical overall status."""
    statuses = [velocity_status, movement_status, accuracy_status]
    concerns = sum(s in {"significantly_below", "significant_shift"} for s in statuses)
    positives = sum(s in {"above", "significantly_above"} for s in [velocity_status, accuracy_status])
    if concerns >= 2:
        return "concerning"
    if positives >= 2 and concerns == 0:
        return "strong"
    return "normal"


def generate_trend_alerts(
    velocity_slope: float,
    velocity_direction: str,
    strike_slope: float,
    strike_direction: str,
    velocity_vs_peak: float,
) -> List[str]:
    """Generate deterministic alerts in their historical ordering."""
    alerts: List[str] = []
    if velocity_direction == "declining" and velocity_slope < -1.0:
        alerts.append(f"Velocity declining at {abs(velocity_slope):.1f} mph per session")
    if velocity_vs_peak < -10:
        alerts.append(f"Current velocity {abs(velocity_vs_peak):.1f}% below peak performance")
    if strike_direction == "declining" and strike_slope < -0.05:
        alerts.append("Strike percentage trending downward")
    if velocity_direction == "improving" and velocity_slope > 1.0:
        alerts.append(f"Velocity improving at {velocity_slope:.1f} mph per session")
    if strike_direction == "improving" and strike_slope > 0.03:
        alerts.append("Strike percentage trending upward")
    return alerts


def generate_recommendations(
    velocity_pct: float,
    h_deviation: float,
    v_deviation: float,
    strike_deviation: float,
) -> List[str]:
    """Generate deterministic baseline recommendations."""
    recommendations: List[str] = []
    if velocity_pct < -5:
        recommendations.append("Velocity below baseline - check for fatigue or mechanical issues")
    elif velocity_pct > 8:
        recommendations.append("Velocity above baseline - maintain current approach")
    if np.sqrt(h_deviation**2 + v_deviation**2) > 1.5:
        recommendations.append("Significant movement variation - review release point consistency")
    if strike_deviation < -0.10:
        recommendations.append("Strike percentage below baseline - focus on command")
    elif strike_deviation > 0.10:
        recommendations.append("Strong strike percentage - consider expanding zone usage")
    return recommendations

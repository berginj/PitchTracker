"""Data aggregation and CSV serialization for pitcher comparisons."""

from __future__ import annotations

import csv
from math import isfinite
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Protocol

import numpy as np


@dataclass
class PitcherStats:
    """Aggregated stats for a pitcher."""

    pitcher_id: str
    display_name: str
    sessions_count: int
    total_pitches: int
    avg_velocity: float | None
    max_velocity: float | None
    velocity_std: float | None
    avg_strike_pct: float | None
    avg_consistency: float | None
    velocity_by_type: Dict[str, float]


class SummarySource(Protocol):
    def _load_summaries_for_pitcher(self, pitcher_id: str, days: int): ...


def load_pitcher_stats(source: SummarySource, pitcher_id: str, display_name: str) -> PitcherStats:
    """Aggregate a pitcher's recent session summaries."""
    summaries = source._load_summaries_for_pitcher(pitcher_id, days=365)
    if not summaries:
        return PitcherStats(
            pitcher_id=pitcher_id,
            display_name=display_name,
            sessions_count=0,
            total_pitches=0,
            avg_velocity=None,
            max_velocity=None,
            velocity_std=None,
            avg_strike_pct=None,
            avg_consistency=None,
            velocity_by_type={},
        )

    velocities = [summary.avg_velocity_mph for summary in summaries
                  if summary.avg_velocity_mph is not None and isfinite(summary.avg_velocity_mph) and summary.avg_velocity_mph > 0]
    max_velocities = [summary.max_velocity_mph for summary in summaries
                      if summary.max_velocity_mph is not None and isfinite(summary.max_velocity_mph) and summary.max_velocity_mph > 0]
    strike_pcts = [summary.strike_percentage for summary in summaries]
    consistencies = [summary.consistency_score for summary in summaries]
    return PitcherStats(
        pitcher_id=pitcher_id,
        display_name=display_name,
        sessions_count=len(summaries),
        total_pitches=sum(summary.total_pitches for summary in summaries),
        avg_velocity=float(np.mean(velocities)) if velocities else None,
        max_velocity=max(max_velocities) if max_velocities else None,
        velocity_std=float(np.std(velocities)) if len(velocities) > 1 else None,
        avg_strike_pct=float(np.mean(strike_pcts)) if strike_pcts else 0.0,
        avg_consistency=float(np.mean(consistencies)) if consistencies else 0.0,
        velocity_by_type={},
    )


def export_comparison_csv(path: Path, stats_collection: Iterable[PitcherStats]) -> None:
    """Keep the original eight columns and append explicit legacy evidence limits."""
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "Pitcher",
                "Sessions",
                "Total Pitches",
                "Avg Velocity (mph)",
                "Max Velocity (mph)",
                "Velocity Std",
                "Strike %",
                "Consistency %",
                "Aggregation Basis",
                "Speed Source / Reference",
                "Eligible Call Denominator",
            ]
        )
        for stats in stats_collection:
            writer.writerow(
                [
                    stats.display_name,
                    stats.sessions_count,
                    stats.total_pitches,
                    format_metric(stats.avg_velocity),
                    format_metric(stats.max_velocity),
                    format_metric(stats.velocity_std, decimals=2),
                    format_metric(stats.avg_strike_pct, scale=100),
                    format_metric(stats.avg_consistency, scale=100),
                    "Legacy session aggregates; session means have equal weight",
                    "Unavailable",
                    "Unavailable",
                ]
            )


def format_metric(value: float | None, *, scale: float = 1, decimals: int = 1) -> str:
    """Preserve missing/nonfinite measurements in cards, charts and CSV."""
    return f"{value * scale:.{decimals}f}" if value is not None and isfinite(value) else "Unavailable"

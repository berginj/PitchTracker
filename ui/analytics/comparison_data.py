"""Data aggregation and CSV serialization for pitcher comparisons."""

from __future__ import annotations

import csv
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
    avg_velocity: float
    max_velocity: float
    velocity_std: float
    avg_strike_pct: float
    avg_consistency: float
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
            avg_velocity=0.0,
            max_velocity=0.0,
            velocity_std=0.0,
            avg_strike_pct=0.0,
            avg_consistency=0.0,
            velocity_by_type={},
        )

    velocities = [summary.avg_velocity_mph for summary in summaries]
    max_velocities = [summary.max_velocity_mph for summary in summaries]
    strike_pcts = [summary.strike_percentage for summary in summaries]
    consistencies = [summary.consistency_score for summary in summaries]
    return PitcherStats(
        pitcher_id=pitcher_id,
        display_name=display_name,
        sessions_count=len(summaries),
        total_pitches=sum(summary.total_pitches for summary in summaries),
        avg_velocity=float(np.mean(velocities)) if velocities else 0.0,
        max_velocity=max(max_velocities) if max_velocities else 0.0,
        velocity_std=float(np.std(velocities)) if len(velocities) > 1 else 0.0,
        avg_strike_pct=float(np.mean(strike_pcts)) if strike_pcts else 0.0,
        avg_consistency=float(np.mean(consistencies)) if consistencies else 0.0,
        velocity_by_type={},
    )


def export_comparison_csv(path: Path, stats_collection: Iterable[PitcherStats]) -> None:
    """Write comparison rows in the dashboard's stable CSV format."""
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
            ]
        )
        for stats in stats_collection:
            writer.writerow(
                [
                    stats.display_name,
                    stats.sessions_count,
                    stats.total_pitches,
                    f"{stats.avg_velocity:.1f}",
                    f"{stats.max_velocity:.1f}",
                    f"{stats.velocity_std:.2f}",
                    f"{stats.avg_strike_pct * 100:.1f}",
                    f"{stats.avg_consistency * 100:.1f}",
                ]
            )

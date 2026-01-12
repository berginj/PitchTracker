"""Stub metrics for plate-gated observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from contracts import StereoObservation
from stereo.association import StereoMatch


@dataclass(frozen=True)
class PlateMetricsStub:
    run_in: float
    rise_in: float
    sample_count: int


def compute_plate_stub(matches: Iterable[StereoMatch]) -> PlateMetricsStub:
    match_list: List[StereoMatch] = list(matches)
    return PlateMetricsStub(
        run_in=0.0,
        rise_in=0.0,
        sample_count=len(match_list),
    )


def compute_plate_from_observations(
    observations: Iterable[StereoObservation],
) -> PlateMetricsStub:
    obs_list = list(observations)
    if len(obs_list) < 2:
        return PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=len(obs_list))
    first = obs_list[0]
    last = obs_list[-1]
    run_in = (last.X - first.X) * 12.0
    rise_in = (last.Y - first.Y) * 12.0
    return PlateMetricsStub(
        run_in=run_in,
        rise_in=rise_in,
        sample_count=len(obs_list),
    )

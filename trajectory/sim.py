"""Synthetic trajectory simulator for tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from contracts import StereoObservation


@dataclass(frozen=True)
class SimConfig:
    dt_s: float = 0.01
    total_time_s: float = 0.6
    noise_ft: float = 0.02
    outlier_prob: float = 0.05
    time_offset_s: float = 0.0
    seed: int = 7


def simulate_ballistic(config: SimConfig) -> List[StereoObservation]:
    rng = np.random.default_rng(config.seed)
    t = np.arange(0.0, config.total_time_s, config.dt_s)
    x0, y0, z0 = 0.0, 6.0, 60.0
    vx, vy, vz = 1.0, 0.0, -120.0
    g = -32.174
    observations: List[StereoObservation] = []
    for i, t_s in enumerate(t):
        x = x0 + vx * t_s
        y = y0 + vy * t_s + 0.5 * g * t_s * t_s
        z = z0 + vz * t_s
        if rng.random() < config.outlier_prob:
            x += rng.normal(0.0, 1.0)
            y += rng.normal(0.0, 1.0)
            z += rng.normal(0.0, 1.0)
        else:
            x += rng.normal(0.0, config.noise_ft)
            y += rng.normal(0.0, config.noise_ft)
            z += rng.normal(0.0, config.noise_ft)
        t_ns = int((t_s + config.time_offset_s) * 1e9)
        observations.append(
            StereoObservation(
                t_ns=t_ns,
                left=(0.0, 0.0),
                right=(0.0, 0.0),
                X=float(x),
                Y=float(y),
                Z=float(z),
                quality=1.0,
                confidence=1.0,
            )
        )
    return observations

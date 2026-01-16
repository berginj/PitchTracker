"""Physics fitter with radar constraints and bias estimation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from trajectory.contracts import FailureCode, TrajectoryFitRequest, TrajectoryFitResult
from trajectory.physics import PhysicsDragFitter, _find_plate_crossing


@dataclass
class RadarBiasEstimator:
    bias_mph: float = 0.0

    def update(self, residual_mph: float, learning_rate: float = 0.1) -> None:
        self.bias_mph = (1.0 - learning_rate) * self.bias_mph + learning_rate * residual_mph

    def get_corrected_speed(self, raw_speed_mph: float) -> float:
        return raw_speed_mph - self.bias_mph


class PhysicsDragRadarFitter(PhysicsDragFitter):
    def __init__(self, bias_estimator: Optional[RadarBiasEstimator] = None) -> None:
        super().__init__()
        self._bias = bias_estimator or RadarBiasEstimator()

    def fit_trajectory(self, request: TrajectoryFitRequest) -> TrajectoryFitResult:
        base_result = super().fit_trajectory(request)
        radar_speed = request.radar_speed_mph
        if radar_speed is None or not base_result.samples:
            return base_result

        corrected = self._bias.get_corrected_speed(radar_speed)
        predicted = _speed_reference(base_result, request)
        if predicted is None:
            base_result.diagnostics.failure_codes.append(FailureCode.RADAR_OUTLIER)
            return base_result
        residual = corrected - predicted
        inlier_prob = _radar_inlier_probability(residual)
        base_result.diagnostics.radar_residual_mph = residual
        base_result.diagnostics.radar_inlier_probability = inlier_prob
        if inlier_prob < 0.2:
            base_result.diagnostics.failure_codes.append(FailureCode.RADAR_OUTLIER)
            return base_result
        self._bias.update(residual)
        return base_result


def _speed_reference(result: TrajectoryFitResult, request: TrajectoryFitRequest) -> Optional[float]:
    samples = result.samples
    if not samples:
        return None
    ref = request.radar_speed_ref or "plate"
    if ref == "release":
        return _speed_mph(samples[0])
    if ref == "plate":
        crossing = _find_plate_crossing(samples, request.plate_plane_z_ft)
        if crossing is None:
            return None
        crossing_t = crossing[1]
        closest = min(samples, key=lambda s: abs(s.t_ns - crossing_t))
        return _speed_mph(closest)
    if ref == "unknown":
        speeds = np.array([_speed_mph(sample) for sample in samples])
        return float(np.min(speeds))
    return None


def _speed_mph(sample) -> float:
    speed_ft_s = (sample.Vx ** 2 + sample.Vy ** 2 + sample.Vz ** 2) ** 0.5
    return float(speed_ft_s * 0.681818)


def _radar_inlier_probability(residual_mph: float) -> float:
    sigma = 2.0
    prob = float(np.exp(-(residual_mph ** 2) / (2 * sigma * sigma)))
    return prob


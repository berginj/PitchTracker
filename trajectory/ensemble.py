"""Trajectory ensemble selection."""

from __future__ import annotations

from typing import Dict, List, Optional

from trajectory.contracts import FailureCode, TrajectoryFitResult


class GatingModel:
    def predict_expected_error(self, diagnostics: Dict[str, float]) -> float:
        raise NotImplementedError


class RuleBasedGatingModel(GatingModel):
    def predict_expected_error(self, diagnostics: Dict[str, float]) -> float:
        base = diagnostics.get("rmse_3d_ft") or 1.0
        penalty = 0.0
        if diagnostics.get("inlier_ratio") is not None and diagnostics["inlier_ratio"] < 0.5:
            penalty += 0.5
        return base + penalty


class TrajectoryEnsembler:
    def __init__(self, gating_model: Optional[GatingModel] = None) -> None:
        self._gating_model = gating_model or RuleBasedGatingModel()

    def select(self, candidates: List[TrajectoryFitResult]) -> Optional[TrajectoryFitResult]:
        guarded = [cand for cand in candidates if self._guard(cand)]
        if not guarded:
            return None
        scored = sorted(guarded, key=self._score)
        return scored[0]

    def _score(self, result: TrajectoryFitResult) -> float:
        if result.expected_plate_error_ft is not None:
            return result.expected_plate_error_ft
        return self._gating_model.predict_expected_error(result.diagnostics.to_dict())

    @staticmethod
    def _guard(result: TrajectoryFitResult) -> bool:
        if result.plate_crossing_xyz_ft is None:
            return False
        if FailureCode.NON_MONOTONIC_Z in result.diagnostics.failure_codes:
            return False
        return True

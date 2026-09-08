"""Confidence scoring utilities."""

from __future__ import annotations

from typing import Optional, Tuple
import math


class ConfidenceScorer:
    def expected_plate_error_ft(
        self,
        residual_scale: Optional[float],
        plate_crossing: Optional[Tuple[Tuple[float, float, float], int]],
    ) -> Optional[float]:
        # Training residual alone does not estimate plate prediction error.
        return None

    def fit_quality(self, normalized_residual: Optional[float], failure_codes=()) -> float:
        """Heuristic goodness of fit, not calibrated physical confidence."""
        if failure_codes or normalized_residual is None or not math.isfinite(normalized_residual):
            return 0.0
        return math.exp(-max(normalized_residual, 0.0))

    def confidence_from_error(self, expected_error_ft: Optional[float]) -> float:
        if expected_error_ft is None:
            return 0.0
        tau = 1.0
        return float(pow(2.718281828, -expected_error_ft / tau))

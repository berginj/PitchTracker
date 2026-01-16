"""Confidence scoring utilities."""

from __future__ import annotations

from typing import Optional, Tuple


class ConfidenceScorer:
    def expected_plate_error_ft(
        self,
        residual_scale: Optional[float],
        plate_crossing: Optional[Tuple[Tuple[float, float, float], int]],
    ) -> Optional[float]:
        if residual_scale is None:
            return None
        if plate_crossing is None:
            return max(residual_scale, 1.0)
        return max(residual_scale, 0.25)

    def confidence_from_error(self, expected_error_ft: Optional[float]) -> float:
        if expected_error_ft is None:
            return 0.0
        tau = 1.0
        return float(pow(2.718281828, -expected_error_ft / tau))


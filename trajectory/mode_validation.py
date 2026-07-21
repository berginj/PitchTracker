"""Evidence-based comparison of trajectory modes without auto-promotion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class ModeResult:
    mode: str
    converged: bool
    plate_xyz_ft: Optional[tuple[float, float, float]]
    speed_mph: Optional[float]
    residual: Optional[float]
    uncertainty_ft: Optional[float]
    failure_codes: tuple[str, ...] = ()


def compare_modes(results: Mapping[str, ModeResult], *, primary_mode: str) -> dict[str, object]:
    primary = results.get(primary_mode)
    comparisons: dict[str, object] = {}
    for mode, result in results.items():
        if mode == primary_mode:
            continue
        plate_delta = None
        speed_delta = None
        comparable = bool(primary and primary.converged and result.converged)
        if comparable and primary and primary.plate_xyz_ft and result.plate_xyz_ft:
            plate_delta = sum((primary.plate_xyz_ft[i] - result.plate_xyz_ft[i]) ** 2 for i in range(3)) ** 0.5
        if comparable and primary and primary.speed_mph is not None and result.speed_mph is not None:
            speed_delta = result.speed_mph - primary.speed_mph
        comparisons[mode] = {
            "converged": result.converged,
            "plate_delta_ft": plate_delta,
            "speed_delta_mph": speed_delta,
            "residual": result.residual,
            "uncertainty_ft": result.uncertainty_ft,
            "failure_codes": list(result.failure_codes),
        }
    return {
        "primary_mode": primary_mode,
        "primary_converged": bool(primary and primary.converged),
        "comparisons": comparisons,
        "promotion_decision": "REQUIRES_GROUND_TRUTH",
    }


__all__ = ["ModeResult", "compare_modes"]

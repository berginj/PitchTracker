from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    MODE_A = "MODE_A"
    MODE_B = "MODE_B"


@dataclass(frozen=True)
class FilterConfig:
    min_area: int = 12
    max_area: int | None = None
    min_circularity: float = 0.1
    max_circularity: float | None = None
    min_velocity: float = 0.0
    max_velocity: float | None = None


@dataclass(frozen=True)
class DetectorConfig:
    frame_diff_threshold: float = 18.0
    bg_diff_threshold: float = 12.0
    bg_alpha: float = 0.08
    edge_threshold: float = 32.0
    blob_threshold: float = 22.0
    runtime_budget_ms: float = 4.0
    crop_padding_px: int = 20
    filters: FilterConfig = FilterConfig()

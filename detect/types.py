from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class Detection:
    centroid: tuple[float, float]
    area: int
    perimeter: int
    bbox: tuple[int, int, int, int]
    circularity: float
    velocity: float | None = None


Lane = Sequence[tuple[float, float]]
Lanes = Iterable[Lane]

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class BlobDetection:
    centroid: tuple[float, float]
    area: int
    perimeter: int
    bbox: tuple[int, int, int, int]
    circularity: float
    velocity: float | None = None


def to_contract_detection(
    blob: BlobDetection,
    camera_id: str,
    frame_index: int,
    t_capture_monotonic_ns: int,
    confidence: float,
) -> "contracts.Detection":
    from contracts import Detection

    radius_px = (blob.area / 3.141592653589793) ** 0.5 if blob.area > 0 else 0.0
    return Detection(
        camera_id=camera_id,
        frame_index=frame_index,
        t_capture_monotonic_ns=t_capture_monotonic_ns,
        u=float(blob.centroid[0]),
        v=float(blob.centroid[1]),
        radius_px=float(radius_px),
        confidence=float(confidence),
    )


Lane = Sequence[tuple[float, float]]
Lanes = Iterable[Lane]

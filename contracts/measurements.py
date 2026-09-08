"""Explicit speed provenance shared by analysis, review, and validation."""

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class SpeedMeasurement:
    speed_mph: float
    source: str
    reference: str
    reference_z_ft: float | None = None
    timestamp_ns: int | None = None
    estimator: str = "unknown"
    schema_version: str = "speed_measurement.v1"

    def __post_init__(self) -> None:
        if self.schema_version != "speed_measurement.v1":
            raise ValueError("unsupported speed measurement schema")
        if not isfinite(self.speed_mph) or self.speed_mph <= 0:
            raise ValueError("speed must be finite and positive")
        if self.reference_z_ft is not None and not isfinite(self.reference_z_ft):
            raise ValueError("speed reference location must be finite")

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def independent_vision_speed(measurement: SpeedMeasurement | None, reference_z_ft: float) -> float:
    """Reject external/assisted results and incomparable measurement planes."""
    if measurement is None or measurement.source != "vision_fit" or measurement.estimator != "vision_only":
        raise ValueError("vision-only validation requires an independent vision measurement")
    if (
        measurement.reference_z_ft is None
        or not isfinite(reference_z_ft)
        or abs(measurement.reference_z_ft - reference_z_ft) > 1e-6
    ):
        raise ValueError("speed reference locations do not match")
    return measurement.speed_mph

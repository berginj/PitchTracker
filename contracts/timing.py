"""Timestamp provenance; receipt timing never proves exposure synchronization."""

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class TimestampEvidence:
    source: str = "unknown"
    clock_domain: str = "unknown"
    semantics: str = "unknown"
    acquisition_uncertainty_ns: Optional[int] = None
    verification_id: Optional[str] = None
    schema_version: str = "timestamp_evidence.v1"

    def __post_init__(self) -> None:
        if self.schema_version != "timestamp_evidence.v1":
            raise ValueError("unsupported timestamp evidence schema")
        value = self.acquisition_uncertainty_ns
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("acquisition uncertainty must be a nonnegative integer in nanoseconds")

    @property
    def acquisition_verified(self) -> bool:
        return (
            self.source in {"device_exposure", "verified_timing_model"}
            and self.clock_domain not in {"", "unknown"}
            and self.semantics in {"exposure_start", "exposure_midpoint"}
            and self.acquisition_uncertainty_ns is not None
            and bool(self.verification_id)
        )

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Optional[Mapping[str, Any]]) -> "TimestampEvidence":
        return cls(**dict(payload or {}))


HOST_RECEIPT_TIMING = TimestampEvidence(source="host_receive", clock_domain="host_monotonic", semantics="receipt")

"""Typed control-query observations for camera capability discovery.

Each control query returns a ``ControlQueryResult`` recording the observed
value, the query status, and provenance (backend and timestamp). Setup
snapshots persist these observations so camera recommendations and validation
decisions remain auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Mapping, Tuple


class ControlQueryStatus(str, Enum):
    """Outcome of a single camera control query.

    Status semantics:
      SUPPORTED — control exists and readback was verified.
      UNSUPPORTED — the backend verified the control is absent on this device.
      PERMISSION_DENIED — the OS or driver refused access.
      QUERY_FAILED — a query or write was attempted but the readback did not
          confirm the expected state (e.g. write succeeded, readback mismatch).
      UNAVAILABLE — the query was never attempted or not applicable.
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    PERMISSION_DENIED = "permission_denied"
    QUERY_FAILED = "query_failed"
    UNAVAILABLE = "unavailable"

    def is_observed(self) -> bool:
        return self == ControlQueryStatus.SUPPORTED


@dataclass(frozen=True)
class ControlQueryResult:
    """Outcome and observed value for one camera control query.

    Attributes:
        control: Control name (exposure, gain, focus, white_balance, fps,
            resolution, pixel_format).
        status: Query outcome.
        observed_value: The raw value read from the device, if any.
        requested_value: The value the caller asked for, if applicable.
        backend: Backend that performed the query (uvc, opencv, simulated).
        reason: Human-readable explanation for non-supported statuses.
        timestamp_utc: ISO-8601 UTC time the query was executed.
    """

    control: str
    status: ControlQueryStatus
    observed_value: Any = None
    requested_value: Any = None
    backend: str = ""
    reason: str = ""
    timestamp_utc: str = ""
    query_method: str = ""
    error_code: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "control": self.control,
            "status": self.status.value,
            "observed_value": self.observed_value,
            "requested_value": self.requested_value,
            "backend": self.backend,
            "reason": self.reason,
            "timestamp_utc": self.timestamp_utc,
            "query_method": self.query_method,
            "error_code": self.error_code,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ControlQueryResult":
        return cls(
            control=str(payload.get("control", "")),
            status=ControlQueryStatus(payload.get("status", "unavailable")),
            observed_value=payload.get("observed_value"),
            requested_value=payload.get("requested_value"),
            backend=str(payload.get("backend", "")),
            reason=str(payload.get("reason", "")),
            timestamp_utc=str(payload.get("timestamp_utc", "")),
            query_method=str(payload.get("query_method", "")),
            error_code=str(payload.get("error_code", "")),
        )


@dataclass(frozen=True)
class CapabilityObservation:
    """Full set of control query results for one camera.

    All mapping fields are normalised to ``MappingProxyType`` on construction
    so the observation is deeply immutable after creation. Callers may pass
    plain dicts; ``__post_init__`` freezes them.

    Attributes:
        camera_id: Hardware identifier or serial.
        backend: Backend used for all queries.
        results: Per-control query results keyed by control name.
        requested_mode: Mode the caller asked for (resolution/fps/pixfmt).
        negotiated_mode: Mode the backend actually configured.
        provenance_note: Free-form note about observation conditions.
    """

    camera_id: str = ""
    backend: str = ""
    results: Mapping[str, ControlQueryResult] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    requested_mode: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    negotiated_mode: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    provenance_note: str = ""
    supported_modes: Tuple[Mapping[str, Any], ...] = ()
    probe_version: str = ""
    device_metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )

    def __post_init__(self) -> None:
        # Freeze mutable dicts passed by callers.
        object.__setattr__(
            self, "results", MappingProxyType(dict(self.results)),
        )
        object.__setattr__(
            self, "requested_mode", MappingProxyType(dict(self.requested_mode)),
        )
        object.__setattr__(
            self, "negotiated_mode", MappingProxyType(dict(self.negotiated_mode)),
        )
        object.__setattr__(
            self,
            "supported_modes",
            tuple(MappingProxyType(dict(mode)) for mode in self.supported_modes),
        )
        object.__setattr__(
            self, "device_metadata", MappingProxyType(dict(self.device_metadata)),
        )

    def status_for(self, control: str) -> ControlQueryStatus:
        result = self.results.get(control)
        if result is None:
            return ControlQueryStatus.UNAVAILABLE
        return result.status

    def observed_value(self, control: str) -> Any:
        result = self.results.get(control)
        if result is None:
            return None
        return result.observed_value

    def to_payload(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "backend": self.backend,
            "results": {k: v.to_payload() for k, v in self.results.items()},
            "requested_mode": dict(self.requested_mode),
            "negotiated_mode": dict(self.negotiated_mode),
            "provenance_note": self.provenance_note,
            "supported_modes": [dict(mode) for mode in self.supported_modes],
            "probe_version": self.probe_version,
            "device_metadata": dict(self.device_metadata),
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "CapabilityObservation":
        raw_results = payload.get("results") or {}
        return cls(
            camera_id=str(payload.get("camera_id", "")),
            backend=str(payload.get("backend", "")),
            results={
                k: ControlQueryResult.from_payload(v)
                for k, v in raw_results.items()
            },
            requested_mode=dict(payload.get("requested_mode") or {}),
            negotiated_mode=dict(payload.get("negotiated_mode") or {}),
            provenance_note=str(payload.get("provenance_note", "")),
            supported_modes=tuple(
                dict(mode) for mode in (payload.get("supported_modes") or ())
            ),
            probe_version=str(payload.get("probe_version", "")),
            device_metadata=dict(payload.get("device_metadata") or {}),
        )


# Standard control names used throughout the system.
CONTROL_EXPOSURE = "exposure"
CONTROL_GAIN = "gain"
CONTROL_FOCUS = "focus"
CONTROL_WHITE_BALANCE = "white_balance"
CONTROL_FPS = "fps"
CONTROL_RESOLUTION = "resolution"
CONTROL_PIXEL_FORMAT = "pixel_format"

ALL_CONTROLS: Tuple[str, ...] = (
    CONTROL_EXPOSURE,
    CONTROL_GAIN,
    CONTROL_FOCUS,
    CONTROL_WHITE_BALANCE,
    CONTROL_FPS,
    CONTROL_RESOLUTION,
    CONTROL_PIXEL_FORMAT,
)


def build_simulated_observation(
    camera_id: str,
    requested_mode: Dict[str, Any],
    controls: Dict[str, Any],
) -> CapabilityObservation:
    """Build a capability observation for a simulated camera.

    All controls report SUPPORTED with synthetic values and a provenance note
    that explicitly states no physical validation was performed.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    results: Dict[str, ControlQueryResult] = {}
    for control in ALL_CONTROLS:
        value = controls.get(control) or requested_mode.get(control)
        results[control] = ControlQueryResult(
            control=control,
            status=ControlQueryStatus.SUPPORTED,
            observed_value=value,
            requested_value=value,
            backend="simulated",
            reason="Simulated backend; does not represent physical device behavior.",
            timestamp_utc=now,
            query_method="simulated",
        )
    return CapabilityObservation(
        camera_id=camera_id,
        backend="simulated",
        results=results,
        requested_mode=dict(requested_mode),
        negotiated_mode=dict(requested_mode),
        provenance_note=(
            "Simulated camera observation. All controls are synthetic. "
            "This does not constitute physical validation."
        ),
        supported_modes=(dict(requested_mode),),
        probe_version="simulated-v1",
        device_metadata={"evidence_kind": "synthetic"},
    )


def build_unavailable_observation(
    camera_id: str,
    backend: str,
    reason: str,
    *,
    requested_mode: Mapping[str, Any] | None = None,
    negotiated_mode: Mapping[str, Any] | None = None,
) -> CapabilityObservation:
    """Build a complete observation when a backend supplies no probe evidence."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return CapabilityObservation(
        camera_id=camera_id,
        backend=backend,
        results={
            control: ControlQueryResult(
                control=control,
                status=ControlQueryStatus.UNAVAILABLE,
                backend=backend,
                reason=reason,
                timestamp_utc=now,
                query_method="backend_unavailable",
            )
            for control in ALL_CONTROLS
        },
        requested_mode=dict(requested_mode or {}),
        negotiated_mode=dict(negotiated_mode or {}),
        provenance_note=reason,
        probe_version="unavailable-v1",
        device_metadata={"evidence_kind": "unavailable"},
    )


__all__ = [
    "ALL_CONTROLS",
    "CONTROL_EXPOSURE",
    "CONTROL_FPS",
    "CONTROL_FOCUS",
    "CONTROL_GAIN",
    "CONTROL_PIXEL_FORMAT",
    "CONTROL_RESOLUTION",
    "CONTROL_WHITE_BALANCE",
    "CapabilityObservation",
    "ControlQueryResult",
    "ControlQueryStatus",
    "build_simulated_observation",
    "build_unavailable_observation",
]

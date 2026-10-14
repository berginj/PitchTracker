"""Read-only display values from historical pitch manifests; never refit data."""

from dataclasses import dataclass
from math import isclose, isfinite
from typing import TypeGuard


def finite_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _block(value) -> dict:
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class RecordedMetrics:
    speed: str
    provenance: str
    result: str
    status: str
    location: str
    reason: str


def recorded_metrics(manifest: dict) -> RecordedMetrics:
    status = str(manifest.get("measurement_status") or "UNKNOWN").upper()
    usable = status in {"VALIDATED", "ESTIMATED", "DEGRADED"}
    value = manifest.get("measured_speed_mph")
    speed = f"{value:.1f} mph" if usable and finite_number(value) and value > 0 else "unavailable"
    source = manifest.get("speed_source")
    matches = [m for m in (manifest.get("vision_speed"), manifest.get("external_speed"))
               if isinstance(m, dict) and finite_number(m.get("speed_mph")) and finite_number(value)
               and isclose(m["speed_mph"], value, abs_tol=1e-6) and (not source or m.get("source") == source)]
    provenance = f"{source or 'Source not recorded'} · reference unavailable"
    if len(matches) == 1:
        m = matches[0]
        provenance = f"{m.get('source') or 'Source not recorded'} · {m.get('reference') or 'reference unavailable'}"
        if finite_number(m.get("reference_z_ft")):
            provenance += f" · z {m['reference_z_ft']:g} ft"
    call = manifest.get("is_strike")
    result = ("STRIKE" if call else "BALL") if usable and type(call) is bool and manifest.get("strike_call_available", True) else "UNAVAILABLE"
    xyz = _block(manifest.get("trajectory")).get("plate_crossing_xyz_ft")
    location = "unavailable"
    if usable and isinstance(xyz, (tuple, list)) and len(xyz) >= 2 and all(finite_number(v) for v in xyz[:2]):
        location = f"x {xyz[0]:+.2f} ft · height {xyz[1]:.2f} ft"
    quality = _block(manifest.get("observation_quality"))
    reasons = quality.get("rejection_reasons") or quality.get("warning_reasons") or []
    reason = manifest.get("strike_call_reason") or "; ".join(str(r) for r in reasons)
    if status == "UNKNOWN":
        reason = "Legacy measurement validity and provenance are unknown."
    return RecordedMetrics(speed, provenance.replace("_", " "), result, status, location, reason)

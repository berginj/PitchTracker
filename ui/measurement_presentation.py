"""Shared presentation of recorded speed and call eligibility; no new estimates."""

from math import isclose, isfinite

from app.contracts import PitchSummary, measurement_is_usable


def recorded_status(pitch: PitchSummary) -> str:
    value = pitch.measurement_status
    return str(getattr(value, "value", value)).upper()


def displayed_speed(pitch: PitchSummary) -> float | None:
    value = pitch.speed_mph
    return value if measurement_is_usable(pitch) and value is not None and isfinite(value) and value > 0 else None


def speed_provenance(pitch: PitchSummary) -> str:
    source = pitch.speed_source
    measurements = [value for value in (pitch.external_speed, pitch.vision_speed)
                    if value and pitch.speed_mph is not None and isclose(value.speed_mph, pitch.speed_mph, abs_tol=1e-6)
                    and (not source or value.source == source)]
    if len(measurements) == 1:
        measurement = measurements[0]
        reference = measurement.reference.replace("_", " ")
        if measurement.reference_z_ft is not None:
            reference += f" · z {measurement.reference_z_ft:g} ft"
        return f"{measurement.source.replace('_', ' ')} · {reference}"
    return f"{source.replace('_', ' ') if source else 'Source not recorded'} · reference unavailable"


def recorded_outcome(pitch: PitchSummary) -> str:
    if not measurement_is_usable(pitch):
        return recorded_status(pitch)
    if not pitch.strike_call_available:
        return "Unavailable"
    return "Strike" if pitch.is_strike else "Ball"

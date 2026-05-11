"""Shared runtime DTOs for pipeline services and durable app artifacts."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Optional


@dataclass(frozen=True)
class CalibrationProfile:
    profile_id: str
    created_utc: str
    schema_version: str


@dataclass(frozen=True)
class PitchSummary:
    pitch_id: str
    t_start_ns: int
    t_end_ns: int
    is_strike: bool
    zone_row: Optional[int]
    zone_col: Optional[int]
    run_in: float
    rise_in: float
    speed_mph: Optional[float]
    rotation_rpm: Optional[float]
    sample_count: int
    trajectory_plate_x_ft: Optional[float] = None
    trajectory_plate_y_ft: Optional[float] = None
    trajectory_plate_z_ft: Optional[float] = None
    trajectory_plate_t_ns: Optional[int] = None
    trajectory_model: Optional[str] = None
    trajectory_expected_error_ft: Optional[float] = None
    trajectory_confidence: Optional[float] = None
    trajectory_drag_param: Optional[float] = None
    trajectory_rmse_px: Optional[float] = None
    trajectory_rmse_3d_ft: Optional[float] = None
    observation_duration_ms: Optional[float] = None
    observation_rate_hz: Optional[float] = None
    observation_max_gap_ms: Optional[float] = None
    observation_z_span_ft: Optional[float] = None
    observation_mean_confidence: Optional[float] = None


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    pitch_count: int
    strikes: int
    balls: int
    heatmap: list[list[int]]
    pitches: list[PitchSummary]


def _filter_dataclass_fields(cls: type, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {field.name for field in fields(cls)}
    return {key: value for key, value in payload.items() if key in allowed}


def pitch_summary_from_dict(payload: dict[str, Any]) -> PitchSummary:
    """Parse a pitch summary payload while ignoring envelope metadata."""
    return PitchSummary(**_filter_dataclass_fields(PitchSummary, payload))


def session_summary_from_dict(payload: dict[str, Any]) -> SessionSummary:
    """Parse a session summary payload while ignoring envelope metadata."""
    session_payload = _filter_dataclass_fields(SessionSummary, payload)
    pitch_payloads = payload.get("pitches", [])
    session_payload["pitches"] = [pitch_summary_from_dict(item) for item in pitch_payloads]
    return SessionSummary(**session_payload)

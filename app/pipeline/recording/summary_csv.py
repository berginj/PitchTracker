"""Qt-free CSV persistence with explicit measurement semantics and legacy columns."""

import csv
import json
from pathlib import Path
from typing import Any, Sequence

from contracts.measurements import SpeedMeasurement
from contracts.versioning import APP_VERSION


LEGACY_COLUMNS = (
    "pitch_id", "t_start_ns", "t_end_ns", "is_strike", "zone_row", "zone_col", "run_in", "rise_in",
    "speed_mph", "rotation_rpm", "sample_count", "trajectory_plate_x_ft", "trajectory_plate_y_ft",
    "trajectory_plate_z_ft", "trajectory_plate_t_ns", "trajectory_model", "trajectory_expected_error_ft",
    "trajectory_confidence", "measurement_status", "speed_source", "movement_basis", "movement_validated",
)
RECORDING_COLUMNS = (
    *LEGACY_COLUMNS[:16], "trajectory_mode", *LEGACY_COLUMNS[16:18], "ray_rmse_px",
    "estimated_camera_time_offset_ms", *LEGACY_COLUMNS[18:], "vision_speed", "external_speed",
)
_SPEED_FIELDS = ("speed_mph", "source", "reference", "reference_z_ft", "timestamp_ns", "estimator")
SEMANTIC_COLUMNS = (
    *(f"{prefix}_{field}" for prefix in ("vision_speed", "external_speed") for field in _SPEED_FIELDS),
    "fit_quality_score", "fit_quality_basis", "physical_prediction_uncertainty",
    "strike_call_available", "strike_call_reason", "strike_call_basis", "strike_uncertainty_policy",
    "csv_schema_version", "app_version",
)
_DECIMALS = {
    "run_in": ".3f", "rise_in": ".3f", "speed_mph": ".3f", "rotation_rpm": ".3f",
    "trajectory_plate_x_ft": ".4f", "trajectory_plate_y_ft": ".4f", "trajectory_plate_z_ft": ".4f",
    "trajectory_expected_error_ft": ".4f", "trajectory_confidence": ".3f",
    "ray_rmse_px": ".3f", "estimated_camera_time_offset_ms": ".3f", "fit_quality_score": ".3f",
}


def write_summary_csv(path: Path, summary: Any, legacy_columns: Sequence[str] = LEGACY_COLUMNS) -> None:
    """Append semantics without moving or removing a caller's legacy columns."""
    columns = (*legacy_columns, *(column for column in SEMANTIC_COLUMNS if column not in legacy_columns))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for pitch in summary.pitches:
            writer.writerow(_pitch_row(pitch))


def _pitch_row(pitch: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        name: value if isinstance(value := getattr(pitch, name, None), (str, int, float)) else ""
        for name in RECORDING_COLUMNS
    }
    quality = getattr(pitch, "quality_diagnostics", None)
    quality = quality if isinstance(quality, dict) else {}
    row.update(
        is_strike=int(bool(pitch.is_strike)), movement_basis=quality.get("movement_basis", ""),
        movement_validated=int(bool(quality.get("movement_validated", False))),
        fit_quality_basis=quality.get("fit_quality_basis", "unknown"),
        physical_prediction_uncertainty=quality.get("physical_prediction_uncertainty", "unavailable"),
        strike_call_reason=getattr(pitch, "strike_call_reason", None) or "",
        strike_call_basis=quality.get("strike_call_basis", "legacy_recorded_geometry"),
        strike_uncertainty_policy=quality.get("strike_uncertainty_policy", "unknown"),
        csv_schema_version="session_summary.csv.v2", app_version=APP_VERSION,
    )
    available = getattr(pitch, "strike_call_available", True)
    row["strike_call_available"] = int(available) if isinstance(available, bool) else ""
    comparison = getattr(pitch, "trajectory_comparison", None)
    mode = getattr(pitch, "trajectory_mode", None)
    diagnostic = comparison.get(mode, {}).get("diagnostics", {}) if isinstance(comparison, dict) else {}
    row["fit_quality_score"] = diagnostic.get("fit_quality_score")
    if row["fit_quality_score"] is None and row["fit_quality_basis"] == "heuristic_not_probability":
        row["fit_quality_score"] = row["trajectory_confidence"]
    for prefix in ("vision_speed", "external_speed"):
        measurement = getattr(pitch, prefix, None)
        for field in _SPEED_FIELDS:
            row[f"{prefix}_{field}"] = getattr(measurement, field) if isinstance(measurement, SpeedMeasurement) else ""
        row[prefix] = json.dumps(measurement.to_payload()) if isinstance(measurement, SpeedMeasurement) else ""
    for name, spec in _DECIMALS.items():
        value = row.get(name)
        row[name] = format(value, spec) if isinstance(value, (int, float)) else ""
    return row

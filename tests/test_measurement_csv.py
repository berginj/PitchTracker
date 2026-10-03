"""Independent speed and conditional quality semantics survive both CSV paths."""

import csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.contracts import PitchSummary
from app.pipeline.recording.session_recording_io import write_session_summary_csv as record_csv
from contracts.measurements import SpeedMeasurement
from ui.export import export_session_summary_csv, write_session_summary_csv as export_csv


def summary():
    pitch = PitchSummary(
        "pitch", 0, 120_000_000, False, None, None, 0.0, 0.0, 75.0, None, 7,
        trajectory_confidence=0.8, trajectory_mode="stereo_3d", speed_source="manual_override",
        vision_speed=SpeedMeasurement(60.0, "vision_fit", "first_observed_point", 8.0, 0, "vision_only"),
        external_speed=SpeedMeasurement(75.0, "manual_override", "unspecified", estimator="external"),
        strike_call_available=False, strike_call_reason="STRIKE_BOUNDARY_UNCERTAIN",
        quality_diagnostics={
            "fit_quality_basis": "heuristic_not_probability", "physical_prediction_uncertainty": "unavailable",
            "strike_call_basis": "conditional_covariance_sensitivity",
            "strike_uncertainty_policy": "conditional_sensitivity_not_physical_confidence",
        },
    )
    return SimpleNamespace(pitches=[pitch])


@pytest.mark.parametrize("writer", [record_csv, export_csv])
def test_manual_override_keeps_independent_speed_and_unavailable_call(writer, tmp_path):
    path = tmp_path / "summary.csv"
    writer(path, summary())
    with path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["speed_mph"] == "75.000"
    assert row["speed_source"] == "manual_override"
    assert row["vision_speed_speed_mph"] == "60.0"
    assert row["vision_speed_source"] == "vision_fit"
    assert row["vision_speed_reference"] == "first_observed_point"
    assert row["vision_speed_reference_z_ft"] == "8.0"
    assert row["vision_speed_timestamp_ns"] == "0"
    assert row["external_speed_speed_mph"] == "75.0"
    assert row["external_speed_reference"] == "unspecified"
    assert row["external_speed_reference_z_ft"] == row["external_speed_timestamp_ns"] == ""
    assert row["fit_quality_score"] == "0.800"
    assert row["fit_quality_basis"] == "heuristic_not_probability"
    assert row["physical_prediction_uncertainty"] == "unavailable"
    assert row["strike_call_available"] == "0"
    assert row["strike_call_reason"] == "STRIKE_BOUNDARY_UNCERTAIN"
    assert "conditional" in row["strike_call_basis"]
    assert row["csv_schema_version"] == "session_summary.csv.v2"


def test_legacy_summary_does_not_invent_speed_records_or_confidence_meaning(tmp_path):
    legacy = PitchSummary("legacy", 0, 1, True, 1, 1, 0.0, 0.0, 70.0, None, 6, trajectory_confidence=0.9)
    path = tmp_path / "legacy.csv"
    export_csv(path, SimpleNamespace(pitches=[legacy]))
    with path.open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["trajectory_confidence"] == "0.900"
    assert row["fit_quality_score"] == ""
    assert row["fit_quality_basis"] == "unknown"
    assert row["physical_prediction_uncertainty"] == "unavailable"
    assert row["vision_speed_speed_mph"] == row["external_speed_speed_mph"] == ""


def test_export_upgrades_columns_without_overwriting_old_recording(tmp_path):
    stored = tmp_path / "session_summary.csv"
    stored.write_text("legacy stored artifact", encoding="utf-8")
    output = tmp_path / "export.csv"
    with patch("ui.export.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(output), "")):
        export_session_summary_csv(None, summary(), Path(tmp_path))
    assert "vision_speed_reference" in output.read_text(encoding="utf-8")
    assert stored.read_text(encoding="utf-8") == "legacy stored artifact"

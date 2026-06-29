"""Tests for recording manifest metadata."""

from __future__ import annotations

from app.contracts import PitchSummary
from app.events.event_bus import EventBus
from app.pipeline.recording.manifest import create_pitch_manifest, create_session_manifest
from app.services.recording import RecordingServiceImpl


def test_session_manifest_includes_calibration_context() -> None:
    report = {
        "schema_version": "calibration_report.v1",
        "status": "PASS",
        "production_ready": True,
        "checks": {"required_matrix_keys_present": True},
        "metrics": {"rms_error_px": 0.4},
        "warnings": [],
        "errors": [],
    }

    manifest = create_session_manifest(
        pitch_id="pitch_00001",
        session_name="bullpen",
        mode="practice",
        measured_speed_mph=82.0,
        config_path="configs/default.yaml",
        calibration_profile_id="rig_active",
        calibration_report=report,
    )

    assert manifest["calibration_profile_id"] == "rig_active"
    assert manifest["calibration_report"] == report


def test_recording_service_stores_calibration_context_for_future_manifest() -> None:
    service = RecordingServiceImpl(EventBus())
    report = {"schema_version": "calibration_report.v1", "status": "WARN"}

    service.set_calibration_context("legacy", report)

    assert service._calibration_profile_id == "legacy"
    assert service._calibration_report == report
    assert service._calibration_report is not report


def test_pitch_manifest_includes_observation_quality_verdict() -> None:
    summary = PitchSummary(
        pitch_id="pitch_00001",
        t_start_ns=1000,
        t_end_ns=2000,
        is_strike=False,
        zone_row=None,
        zone_col=None,
        run_in=0.0,
        rise_in=0.0,
        speed_mph=None,
        rotation_rpm=None,
        sample_count=4,
        observation_quality_status="REJECT",
        observation_rejection_reasons=["HIGH_DEPTH_UNCERTAINTY"],
        observation_warning_reasons=["LARGE_OBSERVATION_GAP"],
        observation_mean_confidence=0.42,
        observation_mean_depth_sigma_ft=4.0,
        observation_max_depth_sigma_ft=9.0,
        observation_max_gap_ms=70.0,
        observation_z_span_ft=25.0,
    )

    manifest = create_pitch_manifest(summary, config_path="configs/default.yaml")

    assert manifest["observation_quality"] == {
        "status": "REJECT",
        "rejection_reasons": ["HIGH_DEPTH_UNCERTAINTY"],
        "warning_reasons": ["LARGE_OBSERVATION_GAP"],
        "mean_confidence": 0.42,
        "mean_depth_sigma_ft": 4.0,
        "max_depth_sigma_ft": 9.0,
        "max_gap_ms": 70.0,
        "z_span_ft": 25.0,
    }

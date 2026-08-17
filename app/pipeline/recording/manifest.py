"""Manifest creation helpers for session and pitch recordings."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, cast

from contracts.versioning import APP_VERSION, SCHEMA_VERSION


def create_base_manifest() -> Dict[str, Any]:
    """Create base manifest with common fields.

    Returns:
        Dictionary with schema_version, app_version, rig_id, created_utc
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "rig_id": None,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def create_session_manifest(
    pitch_id: str,
    session_name: Optional[str],
    mode: Optional[str],
    measured_speed_mph: Optional[float],
    config_path: Optional[str],
    started_utc: Optional[str] = None,
    ended_utc: Optional[str] = None,
    calibration_profile_id: Optional[str] = None,
    calibration_report: Optional[Dict[str, Any]] = None,
    decision_evidence_manifest: Optional[str] = None,
    decision_evidence_complete: Optional[bool] = None,
    event_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create session manifest.

    Args:
        pitch_id: Last pitch ID in session
        session_name: Session name
        mode: Recording mode
        measured_speed_mph: Manual speed measurement
        config_path: Path to config file

    Returns:
        Complete session manifest dictionary
    """
    manifest = create_base_manifest()
    manifest.update(
        {
            "pitch_id": pitch_id,
            "session_id": session_name,
            "session_name": session_name,
            "session": session_name,
            "mode": mode,
            "measured_speed_mph": measured_speed_mph,
            "t_start_utc": started_utc,
            "t_end_utc": ended_utc,
            "config_path": config_path or "configs/default.yaml",
            "calibration_profile_id": calibration_profile_id,
            "calibration_report": calibration_report,
            "decision_evidence_manifest": decision_evidence_manifest,
            "decision_evidence_complete": decision_evidence_complete,
            "session_summary": "session_summary.json",
            "session_summary_csv": "session_summary.csv",
            "session_left_video": "session_left.avi",
            "session_right_video": "session_right.avi",
            "session_left_timestamps": "session_left_timestamps.csv",
            "session_right_timestamps": "session_right_timestamps.csv",
        }
    )
    if event_metadata:
        manifest["event_metadata"] = event_metadata
    return cast(Dict[str, Any], _json_safe(manifest))


def create_pitch_manifest(
    summary,
    config_path: Optional[str],
    performance_metrics: Optional[Dict] = None,
    left_video: str = "left.avi",
    right_video: str = "right.avi",
    event_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create pitch manifest.

    Args:
        summary: PitchSummary object
        config_path: Path to config file
        performance_metrics: Optional dict with detection/tracking metrics

    Returns:
        Complete pitch manifest dictionary
    """
    manifest = create_base_manifest()
    manifest.update(
        {
            "pitch_id": summary.pitch_id,
            "t_start_ns": summary.t_start_ns,
            "t_end_ns": summary.t_end_ns,
            "is_strike": summary.is_strike,
            "zone_row": summary.zone_row,
            "zone_col": summary.zone_col,
            "run_in": summary.run_in,
            "rise_in": summary.rise_in,
            "measured_speed_mph": summary.speed_mph,
            "rotation_rpm": summary.rotation_rpm,
            "measurement_status": summary.measurement_status,
            "speed_source": summary.speed_source,
            "corrections": summary.correction_records or [],
            "quality_diagnostics": summary.quality_diagnostics or {},
            "evidence_manifest": "evidence/manifest.json",
            "trajectory": {
                "plate_crossing_xyz_ft": [
                    summary.trajectory_plate_x_ft,
                    summary.trajectory_plate_y_ft,
                    summary.trajectory_plate_z_ft,
                ],
                "plate_crossing_t_ns": summary.trajectory_plate_t_ns,
                "model": summary.trajectory_model,
                "mode": summary.trajectory_mode,
                "expected_error_ft": summary.trajectory_expected_error_ft,
                "confidence": summary.trajectory_confidence,
                "comparison": summary.trajectory_comparison,
                "ray_rmse_px": summary.ray_rmse_px,
                "estimated_camera_time_offset_ms": summary.estimated_camera_time_offset_ms,
                "ray_failure_codes": summary.ray_failure_codes,
            },
            "observation_quality": {
                "status": summary.observation_quality_status,
                "rejection_reasons": summary.observation_rejection_reasons,
                "warning_reasons": summary.observation_warning_reasons,
                "mean_confidence": summary.observation_mean_confidence,
                "mean_depth_sigma_ft": summary.observation_mean_depth_sigma_ft,
                "max_depth_sigma_ft": summary.observation_max_depth_sigma_ft,
                "max_gap_ms": summary.observation_max_gap_ms,
                "z_span_ft": summary.observation_z_span_ft,
            },
            "left_video": left_video,
            "right_video": right_video,
            "left_timestamps": "left_timestamps.csv",
            "right_timestamps": "right_timestamps.csv",
            "config_path": config_path or "configs/default.yaml",
        }
    )

    # Add performance metrics if provided
    if performance_metrics:
        manifest["performance_metrics"] = performance_metrics

    if event_metadata:
        manifest["event_metadata"] = event_metadata

    return cast(Dict[str, Any], _json_safe(manifest))


def _json_safe(value: Any) -> Any:
    """Normalize numpy-like scalar outputs before durable JSON encoding."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value

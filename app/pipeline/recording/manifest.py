"""Manifest creation helpers for session and pitch recordings."""

from __future__ import annotations

import time
from typing import Dict, Any

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
    session_name: str,
    mode: str,
    measured_speed_mph: float,
    config_path: str,
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
    manifest.update({
        "pitch_id": pitch_id,
        "session": session_name,
        "mode": mode,
        "measured_speed_mph": measured_speed_mph,
        "config_path": config_path or "configs/default.yaml",
        "calibration_profile_id": None,
        "session_summary": "session_summary.json",
        "session_summary_csv": "session_summary.csv",
        "session_left_video": "session_left.avi",
        "session_right_video": "session_right.avi",
        "session_left_timestamps": "session_left_timestamps.csv",
        "session_right_timestamps": "session_right_timestamps.csv",
    })
    return manifest


def create_pitch_manifest(summary, config_path: str) -> Dict[str, Any]:
    """Create pitch manifest.

    Args:
        summary: PitchSummary object
        config_path: Path to config file

    Returns:
        Complete pitch manifest dictionary
    """
    manifest = create_base_manifest()
    manifest.update({
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
        "trajectory": {
            "plate_crossing_xyz_ft": [
                summary.trajectory_plate_x_ft,
                summary.trajectory_plate_y_ft,
                summary.trajectory_plate_z_ft,
            ],
            "plate_crossing_t_ns": summary.trajectory_plate_t_ns,
            "model": summary.trajectory_model,
            "expected_error_ft": summary.trajectory_expected_error_ft,
            "confidence": summary.trajectory_confidence,
        },
        "left_video": "left.avi",
        "right_video": "right.avi",
        "left_timestamps": "left_timestamps.csv",
        "right_timestamps": "right_timestamps.csv",
        "config_path": config_path or "configs/default.yaml",
    })
    return manifest

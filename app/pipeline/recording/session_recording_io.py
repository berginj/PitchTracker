"""Codec and summary persistence helpers for session recording."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import cv2

from app.events import ErrorCategory, ErrorSeverity, publish_error

logger = logging.getLogger(__name__)

CODEC_PREFERENCE = ["H264", "avc1", "XVID", "MP4V", "MJPG"]


def open_video_writer(
    path: Path, width: int, height: int, fps: int
) -> cv2.VideoWriter:
    """Open a video writer using the configured codec fallback order."""
    for codec_name in CODEC_PREFERENCE:
        fourcc = cv2.VideoWriter_fourcc(*codec_name)
        writer = cv2.VideoWriter(
            str(path), fourcc, float(fps), (width, height), True
        )
        if writer.isOpened():
            logger.info(
                "Video writer opened successfully: %s with %s codec",
                path.name,
                codec_name,
            )
            return writer
        writer.release()
        logger.debug("Codec %s failed for %s, trying next...", codec_name, path.name)

    publish_error(
        category=ErrorCategory.RECORDING,
        severity=ErrorSeverity.CRITICAL,
        message=f"All video codecs failed for {path.name}",
        source="SessionRecorder._open_video_writer",
        video_path=str(path),
        tried_codecs=CODEC_PREFERENCE,
    )
    raise RuntimeError(
        f"Failed to open video writer for {path.name}. "
        f"Tried codecs: {CODEC_PREFERENCE}. "
        "Check that ffmpeg or system codecs are installed."
    )


def write_session_summary_csv(path: Path, summary) -> None:
    """Persist the pitch rows from a session summary."""
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "pitch_id",
                "t_start_ns",
                "t_end_ns",
                "is_strike",
                "zone_row",
                "zone_col",
                "run_in",
                "rise_in",
                "speed_mph",
                "rotation_rpm",
                "sample_count",
                "trajectory_plate_x_ft",
                "trajectory_plate_y_ft",
                "trajectory_plate_z_ft",
                "trajectory_plate_t_ns",
                "trajectory_model",
                "trajectory_mode",
                "trajectory_expected_error_ft",
                "trajectory_confidence",
                "ray_rmse_px",
                "estimated_camera_time_offset_ms",
                "measurement_status",
                "speed_source",
                "movement_basis",
                "movement_validated",
            ]
        )
        for pitch in summary.pitches:
            quality = pitch.quality_diagnostics or {}
            writer.writerow(
                [
                    pitch.pitch_id,
                    pitch.t_start_ns,
                    pitch.t_end_ns,
                    int(pitch.is_strike),
                    pitch.zone_row if pitch.zone_row is not None else "",
                    pitch.zone_col if pitch.zone_col is not None else "",
                    f"{pitch.run_in:.3f}",
                    f"{pitch.rise_in:.3f}",
                    f"{pitch.speed_mph:.3f}" if pitch.speed_mph is not None else "",
                    f"{pitch.rotation_rpm:.3f}"
                    if pitch.rotation_rpm is not None
                    else "",
                    pitch.sample_count,
                    _format_optional(pitch.trajectory_plate_x_ft, ".4f"),
                    _format_optional(pitch.trajectory_plate_y_ft, ".4f"),
                    _format_optional(pitch.trajectory_plate_z_ft, ".4f"),
                    pitch.trajectory_plate_t_ns
                    if pitch.trajectory_plate_t_ns is not None
                    else "",
                    pitch.trajectory_model or "",
                    pitch.trajectory_mode or "",
                    _format_optional(pitch.trajectory_expected_error_ft, ".4f"),
                    _format_optional(pitch.trajectory_confidence, ".3f"),
                    _format_optional(pitch.ray_rmse_px, ".3f"),
                    _format_optional(pitch.estimated_camera_time_offset_ms, ".3f"),
                    pitch.measurement_status,
                    pitch.speed_source or "",
                    quality.get("movement_basis", ""),
                    int(bool(quality.get("movement_validated"))),
                ]
            )


def _format_optional(value, format_spec: str) -> str:
    return format(value, format_spec) if value is not None else ""

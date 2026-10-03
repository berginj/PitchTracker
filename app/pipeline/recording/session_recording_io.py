"""Codec and summary persistence helpers for session recording."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2

from app.events import ErrorCategory, ErrorSeverity, publish_error
from app.pipeline.recording.summary_csv import RECORDING_COLUMNS, write_summary_csv

logger = logging.getLogger(__name__)

CODEC_PREFERENCE = ["H264", "avc1", "XVID", "MP4V", "MJPG"]


def open_video_writer(path: Path, width: int, height: int, fps: int) -> cv2.VideoWriter:
    """Open a video writer using the configured codec fallback order."""
    for codec_name in CODEC_PREFERENCE:
        fourcc = getattr(cv2, "VideoWriter_fourcc")(*codec_name)
        writer = cv2.VideoWriter(str(path), fourcc, float(fps), (width, height), True)
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
    """Persist compatible recording columns through the canonical CSV writer."""
    write_summary_csv(path, summary, RECORDING_COLUMNS)

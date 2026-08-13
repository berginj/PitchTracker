"""JSON artifact export helpers for pitch recordings."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping, Sequence

logger = logging.getLogger(__name__)


def export_detections(
    pitch_dir: Path,
    pitch_id: str,
    detections: Mapping[str, Sequence[dict]],
    detection_counts: Mapping[str, int],
) -> None:
    """Write per-camera detection artifacts."""
    detections_dir = pitch_dir / "detections"
    detections_dir.mkdir(exist_ok=True)
    for camera in ("left", "right"):
        camera_detections = detections[camera]
        if not camera_detections:
            continue
        detection_file = detections_dir / f"{camera}_detections.json"
        data = {
            "pitch_id": pitch_id,
            "camera": camera,
            "detection_count": detection_counts[camera],
            "detections": camera_detections,
        }
        detection_file.write_text(json.dumps(data, indent=2))
        logger.info(
            "Exported %s detections to %s",
            detection_counts[camera],
            detection_file,
        )


def export_observations(
    pitch_dir: Path, pitch_id: str, observations: Sequence[dict]
) -> None:
    """Write the stereo observation artifact."""
    obs_dir = pitch_dir / "observations"
    obs_dir.mkdir(exist_ok=True)
    obs_file = obs_dir / "stereo_observations.json"
    data = {
        "pitch_id": pitch_id,
        "observation_count": len(observations),
        "observations": observations,
    }
    obs_file.write_text(json.dumps(data, indent=2))
    logger.info("Exported %s observations to %s", len(observations), obs_file)

"""Durable artifact helpers for review session loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from configs.settings import AppConfig
from exceptions import PitchTrackerError
from log_config.logger import get_logger

logger = get_logger(__name__)

SESSION_MANIFEST_CANDIDATES = ("manifest.json", "session_manifest.json")
PITCH_MANIFEST_CANDIDATES = ("manifest.json", "pitch_manifest.json")
DETECTIONS_LEFT_CANDIDATES = ("detections_left.json", "detections/left_detections.json")
DETECTIONS_RIGHT_CANDIDATES = ("detections_right.json", "detections/right_detections.json")
OBSERVATIONS_CANDIDATES = ("observations.json", "observations/stereo_observations.json")


@dataclass
class LoadedPitch:
    """A pitch and its durable review artifacts."""

    pitch_id: str
    pitch_dir: Path
    manifest: dict
    left_video_path: Path
    right_video_path: Path
    left_timestamps_path: Path
    right_timestamps_path: Path
    original_detections_left: Optional[dict] = None
    original_detections_right: Optional[dict] = None
    original_observations: Optional[list] = None
    frame_files: Optional[list[Path]] = None
    event_metadata: Optional[dict] = None


@dataclass
class LoadedSession:
    """A session and its durable review artifacts."""

    session_id: str
    session_dir: Path
    manifest: dict
    pitches: list[LoadedPitch]
    left_video_path: Path
    right_video_path: Path
    left_timestamps_path: Path
    right_timestamps_path: Path
    session_summary: Optional[dict] = None
    calibration: Optional[dict] = None
    original_config: Optional[AppConfig] = None


def safe_path(base_dir: Path, untrusted: object, default: str) -> Path:
    """Resolve a manifest path within its artifact directory."""
    if not isinstance(untrusted, str) or not untrusted:
        return base_dir / default
    candidate = Path(untrusted)
    if candidate.is_absolute() or ".." in candidate.parts:
        logger.warning(f"Rejected unsafe manifest path: {untrusted!r}")
        return base_dir / default
    resolved = (base_dir / candidate).resolve()
    try:
        resolved.relative_to(base_dir.resolve())
    except ValueError:
        logger.warning(f"Path escapes session directory: {untrusted!r}")
        return base_dir / default
    return base_dir / candidate


def validate_manifest(manifest: object, *, pitch: bool = False) -> None:
    """Validate the stable path-bearing portion of a manifest."""
    kind = "Pitch" if pitch else "Session"
    if not isinstance(manifest, dict):
        raise PitchTrackerError(f"{kind} manifest is not a JSON object")
    fields = (
        ("left_video", "right_video", "left_timestamps", "right_timestamps")
        if pitch
        else (
            "session_left_video",
            "session_right_video",
            "session_left_timestamps",
            "session_right_timestamps",
            "session_summary",
            "config_path",
        )
    )
    for field in fields:
        value = manifest.get(field)
        if value is not None and not isinstance(value, str):
            raise PitchTrackerError(f"{kind} manifest field '{field}' must be a string, " f"got {type(value).__name__}")


def find_existing_path(base_dir: Path, candidates: tuple[str, ...]) -> Optional[Path]:
    """Return the first existing compatibility candidate."""
    return next(
        (base_dir / candidate for candidate in candidates if (base_dir / candidate).exists()),
        None,
    )


def load_json(path: Path, description: str) -> object:
    """Load JSON while retaining a clear artifact-specific parse error."""
    try:
        with path.open("r") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse {description}: {exc}") from exc


def load_optional_json(path: Optional[Path], description: str) -> object:
    """Load optional JSON, degrading safely when an ancillary artifact is corrupt."""
    if path is None or not path.exists():
        return None
    try:
        with path.open("r") as handle:
            return json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        logger.debug(f"Failed to load {description}: {exc}")
        return None


def load_pitch(pitch_dir: Path) -> LoadedPitch:
    """Load one pitch while preserving legacy artifact names."""
    manifest_path = find_existing_path(pitch_dir, PITCH_MANIFEST_CANDIDATES)
    if manifest_path is None:
        raise FileNotFoundError(f"Pitch manifest not found in {pitch_dir}")
    manifest = load_json(manifest_path, "pitch manifest")
    validate_manifest(manifest, pitch=True)
    assert isinstance(manifest, dict)
    pitch_id = manifest.get("pitch_id") or pitch_dir.name
    left_detections = load_optional_json(
        find_existing_path(pitch_dir, DETECTIONS_LEFT_CANDIDATES),
        f"left detections for {pitch_id}",
    )
    right_detections = load_optional_json(
        find_existing_path(pitch_dir, DETECTIONS_RIGHT_CANDIDATES),
        f"right detections for {pitch_id}",
    )
    observations = load_optional_json(
        find_existing_path(pitch_dir, OBSERVATIONS_CANDIDATES),
        f"observations for {pitch_id}",
    )
    frames_dir = pitch_dir / "frames"
    frame_files = sorted(frames_dir.glob("*.png")) if frames_dir.is_dir() else None
    logger.debug(f"Loaded pitch {pitch_id}")
    return LoadedPitch(
        pitch_id=pitch_id,
        pitch_dir=pitch_dir,
        manifest=manifest,
        left_video_path=safe_path(pitch_dir, manifest.get("left_video", "left.avi"), "left.avi"),
        right_video_path=safe_path(pitch_dir, manifest.get("right_video", "right.avi"), "right.avi"),
        left_timestamps_path=safe_path(
            pitch_dir, manifest.get("left_timestamps", "left_timestamps.csv"), "left_timestamps.csv"
        ),
        right_timestamps_path=safe_path(
            pitch_dir,
            manifest.get("right_timestamps", "right_timestamps.csv"),
            "right_timestamps.csv",
        ),
        original_detections_left=left_detections,
        original_detections_right=right_detections,
        original_observations=observations,
        frame_files=frame_files,
        event_metadata=manifest.get("event_metadata"),
    )

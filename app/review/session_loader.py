"""Session loader facade for review and training mode."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from configs.settings import load_config
from exceptions import PitchTrackerError
from log_config.logger import get_logger

from .session_artifacts import (
    DETECTIONS_LEFT_CANDIDATES,
    DETECTIONS_RIGHT_CANDIDATES,
    OBSERVATIONS_CANDIDATES,
    PITCH_MANIFEST_CANDIDATES,
    SESSION_MANIFEST_CANDIDATES,
    LoadedPitch,
    LoadedSession,
    find_existing_path,
    load_json,
    load_pitch,
    safe_path,
    validate_manifest,
)

logger = get_logger(__name__)
_SAFE_CONFIG_DIRS = (Path("configs"),)

# Retain private module aliases used by older integrations.
_safe_path = safe_path
_validate_session_manifest = validate_manifest


def _validate_pitch_manifest(manifest: dict) -> None:
    validate_manifest(manifest, pitch=True)


class SessionLoader:
    """Load recorded sessions while preserving durable artifact compatibility."""

    _SESSION_MANIFEST_CANDIDATES = SESSION_MANIFEST_CANDIDATES
    _PITCH_MANIFEST_CANDIDATES = PITCH_MANIFEST_CANDIDATES
    _DETECTIONS_LEFT_CANDIDATES = DETECTIONS_LEFT_CANDIDATES
    _DETECTIONS_RIGHT_CANDIDATES = DETECTIONS_RIGHT_CANDIDATES
    _OBSERVATIONS_CANDIDATES = OBSERVATIONS_CANDIDATES

    @staticmethod
    def get_available_sessions(recordings_dir: Path) -> list[Path]:
        """Return compatible session directories, newest name first."""
        if not recordings_dir.exists():
            logger.warning(f"Recordings directory does not exist: {recordings_dir}")
            return []
        sessions = [
            item
            for item in recordings_dir.iterdir()
            if item.is_dir()
            and SessionLoader._find_existing_path(item, SessionLoader._SESSION_MANIFEST_CANDIDATES) is not None
        ]
        sessions.sort(reverse=True)
        logger.info(f"Found {len(sessions)} sessions in {recordings_dir}")
        return sessions

    @staticmethod
    def validate_session(session_dir: Path) -> tuple[bool, str]:
        """Validate the minimum files required for session playback."""
        if not session_dir.exists():
            return False, f"Session directory does not exist: {session_dir}"
        if not session_dir.is_dir():
            return False, f"Path is not a directory: {session_dir}"
        manifest_path = SessionLoader._find_existing_path(session_dir, SessionLoader._SESSION_MANIFEST_CANDIDATES)
        if manifest_path is None:
            return False, "Missing required files: manifest.json or session_manifest.json"
        try:
            manifest = load_json(manifest_path, f"session manifest: {manifest_path}")
        except (ValueError, OSError) as exc:
            return False, str(exc)
        if not isinstance(manifest, dict):
            return False, "Session manifest is not a JSON object"
        left = safe_path(
            session_dir,
            manifest.get("session_left_video", "session_left.avi"),
            "session_left.avi",
        )
        right = safe_path(
            session_dir,
            manifest.get("session_right_video", "session_right.avi"),
            "session_right.avi",
        )
        if not left.exists() and not right.exists():
            return False, "Session videos not found (session_left.avi or session_right.avi)"
        logger.debug(f"Session validation passed: {session_dir}")
        return True, ""

    @staticmethod
    def load_session(session_dir: Path) -> LoadedSession:
        """Load a complete session and its compatible pitch artifacts."""
        logger.info(f"Loading session from {session_dir}")
        is_valid, error_msg = SessionLoader.validate_session(session_dir)
        if not is_valid:
            raise ValueError(f"Invalid session: {error_msg}")
        manifest_path = SessionLoader._find_existing_path(session_dir, SessionLoader._SESSION_MANIFEST_CANDIDATES)
        if manifest_path is None:
            raise ValueError(f"Invalid session: manifest not found in {session_dir}")
        manifest = load_json(manifest_path, "session manifest")
        validate_manifest(manifest)
        assert isinstance(manifest, dict)
        session_id = manifest.get("session_id") or manifest.get("session_name") or session_dir.name
        session_summary = SessionLoader._load_session_summary(session_dir, manifest)
        original_config = SessionLoader._load_original_config(session_dir, manifest)
        pitches = SessionLoader._load_pitches(session_dir)
        logger.info(f"Successfully loaded session '{session_id}' with {len(pitches)} pitches")
        return LoadedSession(
            session_id=session_id,
            session_dir=session_dir,
            manifest=manifest,
            pitches=pitches,
            left_video_path=safe_path(
                session_dir,
                manifest.get("session_left_video", "session_left.avi"),
                "session_left.avi",
            ),
            right_video_path=safe_path(
                session_dir,
                manifest.get("session_right_video", "session_right.avi"),
                "session_right.avi",
            ),
            left_timestamps_path=safe_path(
                session_dir,
                manifest.get("session_left_timestamps", "session_left_timestamps.csv"),
                "session_left_timestamps.csv",
            ),
            right_timestamps_path=safe_path(
                session_dir,
                manifest.get("session_right_timestamps", "session_right_timestamps.csv"),
                "session_right_timestamps.csv",
            ),
            session_summary=session_summary,
            calibration=None,
            original_config=original_config,
        )

    @staticmethod
    def _load_session_summary(session_dir: Path, manifest: dict) -> Optional[dict]:
        path = safe_path(
            session_dir,
            manifest.get("session_summary", "session_summary.json"),
            "session_summary.json",
        )
        if not path.exists():
            return None
        try:
            summary = load_json(path, "session summary")
            return summary if isinstance(summary, dict) else None
        except (ValueError, OSError) as exc:
            logger.warning(f"Failed to load session summary: {exc}")
            return None

    @staticmethod
    def _load_original_config(session_dir: Path, manifest: dict):
        config_value = manifest.get("config_path", "configs/default.yaml")
        if not isinstance(config_value, str):
            return None
        config_path = Path(config_value)
        safe = False
        if not config_path.is_absolute():
            safe = any(str(config_path).startswith(str(safe_dir)) for safe_dir in _SAFE_CONFIG_DIRS)
            session_config = safe_path(session_dir, config_value, "")
            if session_config != session_dir and session_config.exists():
                safe = True
                config_path = session_config
        if not safe or not config_path.exists():
            if config_value:
                logger.debug(f"Skipped config load from restricted path: {config_value}")
            return None
        try:
            config = load_config(config_path)
            logger.debug(f"Loaded original config: {config_path}")
            return config
        except (PitchTrackerError, OSError, ValueError, TypeError) as exc:
            logger.warning(f"Failed to load original config from {config_path}: {exc}")
            return None

    @staticmethod
    def _load_pitches(session_dir: Path) -> list[LoadedPitch]:
        """Load valid pitch directories and skip corrupt individual pitches."""
        pitches = []
        for item in session_dir.iterdir():
            if not item.is_dir():
                continue
            if SessionLoader._find_existing_path(item, SessionLoader._PITCH_MANIFEST_CANDIDATES) is None:
                continue
            try:
                pitches.append(SessionLoader._load_pitch(item))
            except (PitchTrackerError, OSError, ValueError, TypeError) as exc:
                logger.warning(f"Failed to load pitch {item.name}: {exc}")
        pitches.sort(key=lambda pitch: pitch.pitch_id)
        logger.debug(f"Loaded {len(pitches)} pitches from {session_dir}")
        return pitches

    @staticmethod
    def _load_pitch(pitch_dir: Path) -> LoadedPitch:
        """Load one pitch directory."""
        return load_pitch(pitch_dir)

    @staticmethod
    def _find_existing_path(base_dir: Path, candidates: tuple[str, ...]) -> Optional[Path]:
        """Return the first existing compatibility candidate."""
        return find_existing_path(base_dir, candidates)


__all__ = ["LoadedPitch", "LoadedSession", "SessionLoader"]

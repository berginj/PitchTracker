"""Session loader for review and training mode."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from configs.settings import AppConfig, load_config
from exceptions import PitchTrackerError
from log_config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LoadedPitch:
    """Represents a single pitch loaded from a recording.

    Attributes:
        pitch_id: Unique pitch identifier (e.g., "pitch-001")
        pitch_dir: Directory containing pitch data
        manifest: Parsed pitch manifest dictionary
        left_video_path: Path to left camera video file
        right_video_path: Path to right camera video file
        left_timestamps_path: Path to left camera timestamps CSV
        right_timestamps_path: Path to right camera timestamps CSV
        original_detections_left: Original left camera detections (if available)
        original_detections_right: Original right camera detections (if available)
        original_observations: Original 3D trajectory observations (if available)
        frame_files: List of saved frame PNG files (if available)
    """

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


@dataclass
class LoadedSession:
    """Represents a loaded recording session.

    Attributes:
        session_id: Session identifier (directory name)
        session_dir: Path to session directory
        manifest: Parsed session manifest dictionary
        pitches: List of loaded pitches
        left_video_path: Path to session-level left camera video
        right_video_path: Path to session-level right camera video
        left_timestamps_path: Path to left camera timestamps CSV
        right_timestamps_path: Path to right camera timestamps CSV
        session_summary: Session summary data (if available)
        calibration: Calibration data (if available)
        original_config: Original AppConfig used for this session
    """

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


def _safe_path(base_dir: Path, untrusted: str, default: str) -> Path:
    """Resolve a manifest path value safely within a base directory.

    Rejects absolute paths, '..' traversal, and non-string values.
    Falls back to *default* when the value is unsafe or missing.
    """
    if not isinstance(untrusted, str) or not untrusted:
        return base_dir / default
    # Reject absolute paths and traversal attempts
    if Path(untrusted).is_absolute() or ".." in Path(untrusted).parts:
        logger.warning(f"Rejected unsafe manifest path: {untrusted!r}")
        return base_dir / default
    resolved = (base_dir / untrusted).resolve()
    base_resolved = base_dir.resolve()
    if not str(resolved).startswith(str(base_resolved)):
        logger.warning(f"Path escapes session directory: {untrusted!r}")
        return base_dir / default
    return base_dir / untrusted


def _validate_session_manifest(manifest: dict) -> None:
    """Validate minimal session manifest structure.

    Raises:
        PitchTrackerError: If manifest is structurally invalid
    """
    if not isinstance(manifest, dict):
        raise PitchTrackerError("Session manifest is not a JSON object")
    # Validate path-bearing fields are strings when present
    path_fields = [
        "session_left_video",
        "session_right_video",
        "session_left_timestamps",
        "session_right_timestamps",
        "session_summary",
        "config_path",
    ]
    for field in path_fields:
        value = manifest.get(field)
        if value is not None and not isinstance(value, str):
            raise PitchTrackerError(f"Manifest field '{field}' must be a string, got {type(value).__name__}")


def _validate_pitch_manifest(manifest: dict) -> None:
    """Validate minimal pitch manifest structure.

    Raises:
        PitchTrackerError: If manifest is structurally invalid
    """
    if not isinstance(manifest, dict):
        raise PitchTrackerError("Pitch manifest is not a JSON object")
    path_fields = ["left_video", "right_video", "left_timestamps", "right_timestamps"]
    for field in path_fields:
        value = manifest.get(field)
        if value is not None and not isinstance(value, str):
            raise PitchTrackerError(f"Pitch manifest field '{field}' must be a string, got {type(value).__name__}")


_SAFE_CONFIG_DIRS = (Path("configs"),)


class SessionLoader:
    """Loads recorded sessions for review and training.

    Parses session directories, validates structure, and loads all
    associated data (videos, manifests, detections, etc.).
    """

    _SESSION_MANIFEST_CANDIDATES = ("manifest.json", "session_manifest.json")
    _PITCH_MANIFEST_CANDIDATES = ("manifest.json", "pitch_manifest.json")
    _DETECTIONS_LEFT_CANDIDATES = ("detections_left.json", "detections/left_detections.json")
    _DETECTIONS_RIGHT_CANDIDATES = ("detections_right.json", "detections/right_detections.json")
    _OBSERVATIONS_CANDIDATES = ("observations.json", "observations/stereo_observations.json")

    @staticmethod
    def get_available_sessions(recordings_dir: Path) -> list[Path]:
        """Scan recordings directory for available session directories.

        Args:
            recordings_dir: Base recordings directory

        Returns:
            List of session directory paths, sorted by date (newest first)

        Example:
            >>> sessions = SessionLoader.get_available_sessions(Path("recordings"))
            >>> print(sessions)
            [Path("recordings/session-2026-01-19_001"),
             Path("recordings/session-2026-01-18_002"), ...]
        """
        if not recordings_dir.exists():
            logger.warning(f"Recordings directory does not exist: {recordings_dir}")
            return []

        sessions = []
        for item in recordings_dir.iterdir():
            if (
                item.is_dir()
                and SessionLoader._find_existing_path(
                    item,
                    SessionLoader._SESSION_MANIFEST_CANDIDATES,
                )
                is not None
            ):
                sessions.append(item)

        # Sort by name (which includes timestamp) in descending order
        sessions.sort(reverse=True)

        logger.info(f"Found {len(sessions)} sessions in {recordings_dir}")
        return sessions

    @staticmethod
    def validate_session(session_dir: Path) -> tuple[bool, str]:
        """Validate that a session directory has required files.

        Args:
            session_dir: Path to session directory

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if session is valid, False otherwise
            - error_message: Empty if valid, error description otherwise

        Example:
            >>> is_valid, error = SessionLoader.validate_session(Path("recordings/session-2026-01-19_001"))
            >>> if not is_valid:
            ...     print(f"Invalid session: {error}")
        """
        if not session_dir.exists():
            return False, f"Session directory does not exist: {session_dir}"

        if not session_dir.is_dir():
            return False, f"Path is not a directory: {session_dir}"

        # Check for required session files
        if (
            SessionLoader._find_existing_path(
                session_dir,
                SessionLoader._SESSION_MANIFEST_CANDIDATES,
            )
            is None
        ):
            return False, "Missing required files: manifest.json or session_manifest.json"

        manifest_path = SessionLoader._find_existing_path(
            session_dir,
            SessionLoader._SESSION_MANIFEST_CANDIDATES,
        )
        manifest = {}
        if manifest_path is not None:
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
            except json.JSONDecodeError:
                return False, f"Failed to parse session manifest: {manifest_path}"

        # Check for session videos (at least one should exist)
        session_left = _safe_path(
            session_dir, manifest.get("session_left_video", "session_left.avi"), "session_left.avi"
        )
        session_right = _safe_path(
            session_dir, manifest.get("session_right_video", "session_right.avi"), "session_right.avi"
        )

        if not session_left.exists() and not session_right.exists():
            return False, "Session videos not found (session_left.avi or session_right.avi)"

        logger.debug(f"Session validation passed: {session_dir}")
        return True, ""

    @staticmethod
    def load_session(session_dir: Path) -> LoadedSession:
        """Load a complete session with all data.

        Args:
            session_dir: Path to session directory

        Returns:
            LoadedSession object with all session data

        Raises:
            FileNotFoundError: If session directory or required files don't exist
            ValueError: If session is invalid or data is corrupted

        Example:
            >>> session = SessionLoader.load_session(Path("recordings/session-2026-01-19_001"))
            >>> print(f"Loaded {len(session.pitches)} pitches")
            >>> for pitch in session.pitches:
            ...     print(f"  {pitch.pitch_id}: {pitch.manifest['measured_speed_mph']:.1f} mph")
        """
        logger.info(f"Loading session from {session_dir}")

        # Validate session
        is_valid, error_msg = SessionLoader.validate_session(session_dir)
        if not is_valid:
            raise ValueError(f"Invalid session: {error_msg}")

        # Load session manifest
        manifest_path = SessionLoader._find_existing_path(
            session_dir,
            SessionLoader._SESSION_MANIFEST_CANDIDATES,
        )
        if manifest_path is None:
            raise ValueError(f"Invalid session: manifest not found in {session_dir}")
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse session manifest: {e}")

        _validate_session_manifest(manifest)

        # Prefer manifest-provided contract fields, then fall back to directory name.
        session_id = manifest.get("session_id") or manifest.get("session_name") or session_dir.name

        # Load session-level video paths (with path safety)
        left_video_path = _safe_path(
            session_dir, manifest.get("session_left_video", "session_left.avi"), "session_left.avi"
        )
        right_video_path = _safe_path(
            session_dir, manifest.get("session_right_video", "session_right.avi"), "session_right.avi"
        )
        left_timestamps_path = _safe_path(
            session_dir,
            manifest.get("session_left_timestamps", "session_left_timestamps.csv"),
            "session_left_timestamps.csv",
        )
        right_timestamps_path = _safe_path(
            session_dir,
            manifest.get("session_right_timestamps", "session_right_timestamps.csv"),
            "session_right_timestamps.csv",
        )

        # Load session summary if available
        session_summary = None
        summary_path = _safe_path(
            session_dir, manifest.get("session_summary", "session_summary.json"), "session_summary.json"
        )
        if summary_path.exists():
            try:
                with open(summary_path, "r") as f:
                    session_summary = json.load(f)
                logger.debug(f"Loaded session summary: {summary_path}")
            except Exception as e:
                logger.warning(f"Failed to load session summary: {e}")

        # Load original configuration (restricted to known safe directories)
        original_config = None
        config_path_str = manifest.get("config_path", "configs/default.yaml")
        if isinstance(config_path_str, str):
            config_path = Path(config_path_str)
            # Only load configs from within session dir or known config directories
            safe = False
            if not config_path.is_absolute():
                for safe_dir in _SAFE_CONFIG_DIRS:
                    if str(config_path).startswith(str(safe_dir)):
                        safe = True
                        break
                # Also allow configs stored within the session
                session_config = _safe_path(session_dir, config_path_str, "")
                if session_config != session_dir and session_config.exists():
                    safe = True
                    config_path = session_config
            if safe and config_path.exists():
                try:
                    original_config = load_config(config_path)
                    logger.debug(f"Loaded original config: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load original config from {config_path}: {e}")
            elif config_path_str:
                logger.debug(f"Skipped config load from restricted path: {config_path_str}")

        # Load individual pitches
        pitches = SessionLoader._load_pitches(session_dir)

        logger.info(f"Successfully loaded session '{session_id}' with {len(pitches)} pitches")

        return LoadedSession(
            session_id=session_id,
            session_dir=session_dir,
            manifest=manifest,
            pitches=pitches,
            left_video_path=left_video_path,
            right_video_path=right_video_path,
            left_timestamps_path=left_timestamps_path,
            right_timestamps_path=right_timestamps_path,
            session_summary=session_summary,
            calibration=None,  # Future: Load calibration data from session directory
            original_config=original_config,
        )

    @staticmethod
    def _load_pitches(session_dir: Path) -> list[LoadedPitch]:
        """Load all pitch directories within a session.

        Args:
            session_dir: Path to session directory

        Returns:
            List of LoadedPitch objects, sorted by pitch ID
        """
        pitches = []

        # Find all pitch directories
        for item in session_dir.iterdir():
            if (
                item.is_dir()
                and SessionLoader._find_existing_path(
                    item,
                    SessionLoader._PITCH_MANIFEST_CANDIDATES,
                )
                is not None
            ):
                try:
                    pitch = SessionLoader._load_pitch(item)
                    pitches.append(pitch)
                except Exception as e:
                    logger.warning(f"Failed to load pitch {item.name}: {e}")

        # Sort by pitch ID
        pitches.sort(key=lambda p: p.pitch_id)

        logger.debug(f"Loaded {len(pitches)} pitches from {session_dir}")
        return pitches

    @staticmethod
    def _load_pitch(pitch_dir: Path) -> LoadedPitch:
        """Load a single pitch directory.

        Args:
            pitch_dir: Path to pitch directory

        Returns:
            LoadedPitch object

        Raises:
            FileNotFoundError: If required files don't exist
            ValueError: If pitch data is invalid
        """
        pitch_id = pitch_dir.name

        # Load pitch manifest
        manifest_path = SessionLoader._find_existing_path(
            pitch_dir,
            SessionLoader._PITCH_MANIFEST_CANDIDATES,
        )
        if manifest_path is None:
            raise FileNotFoundError(f"Pitch manifest not found in {pitch_dir}")

        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse pitch manifest: {e}")

        _validate_pitch_manifest(manifest)

        pitch_id = manifest.get("pitch_id") or pitch_id

        # Get video paths from manifest (with path safety)
        left_video_path = _safe_path(pitch_dir, manifest.get("left_video", "left.avi"), "left.avi")
        right_video_path = _safe_path(pitch_dir, manifest.get("right_video", "right.avi"), "right.avi")
        left_timestamps_path = _safe_path(
            pitch_dir, manifest.get("left_timestamps", "left_timestamps.csv"), "left_timestamps.csv"
        )
        right_timestamps_path = _safe_path(
            pitch_dir, manifest.get("right_timestamps", "right_timestamps.csv"), "right_timestamps.csv"
        )

        # Load original detections if available
        detections_left = None
        detections_left_path = SessionLoader._find_existing_path(
            pitch_dir,
            SessionLoader._DETECTIONS_LEFT_CANDIDATES,
        )
        if detections_left_path is not None and detections_left_path.exists():
            try:
                with open(detections_left_path, "r") as f:
                    detections_left = json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load left detections for {pitch_id}: {e}")

        detections_right = None
        detections_right_path = SessionLoader._find_existing_path(
            pitch_dir,
            SessionLoader._DETECTIONS_RIGHT_CANDIDATES,
        )
        if detections_right_path is not None and detections_right_path.exists():
            try:
                with open(detections_right_path, "r") as f:
                    detections_right = json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load right detections for {pitch_id}: {e}")

        # Load observations if available
        observations = None
        observations_path = SessionLoader._find_existing_path(
            pitch_dir,
            SessionLoader._OBSERVATIONS_CANDIDATES,
        )
        if observations_path is not None and observations_path.exists():
            try:
                with open(observations_path, "r") as f:
                    observations = json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load observations for {pitch_id}: {e}")

        # Find saved frame files if available
        frame_files = None
        frames_dir = pitch_dir / "frames"
        if frames_dir.exists() and frames_dir.is_dir():
            frame_files = sorted(frames_dir.glob("*.png"))

        logger.debug(f"Loaded pitch {pitch_id}")

        return LoadedPitch(
            pitch_id=pitch_id,
            pitch_dir=pitch_dir,
            manifest=manifest,
            left_video_path=left_video_path,
            right_video_path=right_video_path,
            left_timestamps_path=left_timestamps_path,
            right_timestamps_path=right_timestamps_path,
            original_detections_left=detections_left,
            original_detections_right=detections_right,
            original_observations=observations,
            frame_files=frame_files,
        )

    @staticmethod
    def _find_existing_path(base_dir: Path, candidates: tuple[str, ...]) -> Optional[Path]:
        """Return the first existing file from a set of compatibility candidates."""
        for candidate in candidates:
            candidate_path = base_dir / candidate
            if candidate_path.exists():
                return candidate_path
        return None

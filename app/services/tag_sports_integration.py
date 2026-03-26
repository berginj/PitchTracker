"""TAG Sports integration service for importing practice data.

This module provides the service layer for integrating TAG Sports practice data
into PitchTracker pitcher profiles. Supports manual JSON import (Phase 1) and
cloud API sync (Phase 2+).

Part of TAG Sports Partnership integration (March 2026).
See: docs/TAG_DEEP_INTEGRATION_API_SPEC.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from loguru import logger


# JSON Schema Version Support
SUPPORTED_SCHEMA_VERSIONS = ["1.0"]


@dataclass
class TagSportsPitch:
    """Individual pitch measurement from TAG Sports device."""

    pitch_number: int
    timestamp: datetime
    speed_mph: float
    pitch_type: str = ""  # Athlete-tagged type (e.g., "Fastball", "Changeup")
    notes: str = ""
    video_url: Optional[str] = None  # If TAG Sports stores video


@dataclass
class TagSportsSession:
    """TAG Sports practice session data."""

    session_id: str  # TAG Sports internal session ID
    date: datetime
    location: str  # Free-text location (e.g., "Backyard practice")
    session_type: str  # practice, bullpen, game, warmup, other
    total_pitches: int
    avg_speed_mph: float
    max_speed_mph: float
    min_speed_mph: float
    pitches: List[TagSportsPitch]
    notes: str = ""


@dataclass
class TagSportsAthleteData:
    """TAG Sports athlete information."""

    tag_user_id: str  # Unique TAG Sports user ID
    name: str
    birth_year: Optional[int] = None
    throws: Optional[str] = None  # "right", "left", "both"
    position: Optional[str] = None
    email: Optional[str] = None


@dataclass
class TagSportsImportResult:
    """Result of TAG Sports data import operation."""

    success: bool
    athlete_data: Optional[TagSportsAthleteData]
    sessions_imported: int
    pitches_imported: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class TagSportsIntegrationService:
    """Service for importing and managing TAG Sports practice data.

    Provides integration between TAG Sports consumer tracking and PitchTracker
    facility training. Supports:
    - Manual JSON import (Phase 1)
    - Cloud API sync (Phase 2+)
    - Session merging and deduplication
    - Data validation and error handling

    Example:
        >>> service = TagSportsIntegrationService()
        >>> result = service.import_from_file(Path("TAG_export_john_doe.json"))
        >>> if result.success:
        ...     print(f"Imported {result.sessions_imported} sessions")
    """

    def __init__(self):
        """Initialize TAG Sports integration service."""
        self._import_history: List[Path] = []

    def import_from_file(self, file_path: Path) -> TagSportsImportResult:
        """Import TAG Sports data from JSON export file.

        Args:
            file_path: Path to TAG Sports export JSON file

        Returns:
            Import result with success status, statistics, and any errors

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"TAG Sports export file not found: {file_path}")

        try:
            logger.info(f"Importing TAG Sports data from: {file_path}")

            # Read and parse JSON
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate schema version
            schema_version = data.get("schema_version")
            if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
                return TagSportsImportResult(
                    success=False,
                    athlete_data=None,
                    sessions_imported=0,
                    pitches_imported=0,
                    errors=[
                        f"Unsupported schema version: {schema_version}. "
                        f"Supported versions: {', '.join(SUPPORTED_SCHEMA_VERSIONS)}"
                    ],
                )

            # Validate required fields
            validation_errors = self._validate_required_fields(data)
            if validation_errors:
                return TagSportsImportResult(
                    success=False,
                    athlete_data=None,
                    sessions_imported=0,
                    pitches_imported=0,
                    errors=validation_errors,
                )

            # Extract athlete info
            athlete_data = self._parse_athlete_data(data["athlete"])

            # Extract and validate sessions
            sessions, session_warnings = self._parse_sessions(data["sessions"])

            # Calculate statistics
            total_pitches = sum(session.total_pitches for session in sessions)

            # Record import in history
            self._import_history.append(file_path)

            logger.info(
                f"Successfully imported {len(sessions)} sessions ({total_pitches} pitches) "
                f"for {athlete_data.name}"
            )

            return TagSportsImportResult(
                success=True,
                athlete_data=athlete_data,
                sessions_imported=len(sessions),
                pitches_imported=total_pitches,
                errors=[],
                warnings=session_warnings,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON file: {e}")
            return TagSportsImportResult(
                success=False,
                athlete_data=None,
                sessions_imported=0,
                pitches_imported=0,
                errors=[f"Invalid JSON file: {str(e)}"],
            )

        except Exception as e:
            logger.exception(f"Failed to import TAG Sports data: {e}")
            return TagSportsImportResult(
                success=False,
                athlete_data=None,
                sessions_imported=0,
                pitches_imported=0,
                errors=[f"Import failed: {str(e)}"],
            )

    def _validate_required_fields(self, data: dict) -> List[str]:
        """Validate required fields in TAG Sports export.

        Args:
            data: Parsed JSON data

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Top-level required fields
        required_top = ["schema_version", "export_metadata", "athlete", "sessions"]
        for field in required_top:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        if "athlete" in data:
            # Athlete required fields
            athlete = data["athlete"]
            required_athlete = ["tag_user_id", "name"]
            for field in required_athlete:
                if field not in athlete:
                    errors.append(f"Missing required athlete field: {field}")

        return errors

    def _parse_athlete_data(self, athlete_dict: dict) -> TagSportsAthleteData:
        """Parse athlete data from JSON.

        Args:
            athlete_dict: Athlete section of TAG Sports export

        Returns:
            Parsed athlete data
        """
        return TagSportsAthleteData(
            tag_user_id=athlete_dict["tag_user_id"],
            name=athlete_dict["name"],
            birth_year=athlete_dict.get("birth_year"),
            throws=athlete_dict.get("throws"),
            position=athlete_dict.get("position"),
            email=athlete_dict.get("email"),
        )

    def _parse_sessions(
        self, sessions_list: List[dict]
    ) -> tuple[List[TagSportsSession], List[str]]:
        """Parse session data from JSON.

        Args:
            sessions_list: List of session dictionaries

        Returns:
            Tuple of (parsed sessions, warnings)
        """
        sessions = []
        warnings = []

        for idx, session_dict in enumerate(sessions_list):
            try:
                # Parse pitches
                pitches = []
                for pitch_dict in session_dict.get("pitches", []):
                    pitch = TagSportsPitch(
                        pitch_number=pitch_dict["pitch_number"],
                        timestamp=datetime.fromisoformat(
                            pitch_dict["timestamp"].replace("Z", "+00:00")
                        ),
                        speed_mph=pitch_dict["speed_mph"],
                        pitch_type=pitch_dict.get("pitch_type", ""),
                        notes=pitch_dict.get("notes", ""),
                        video_url=pitch_dict.get("video_url"),
                    )
                    pitches.append(pitch)

                # Get summary stats
                summary = session_dict.get("summary", {})

                # Create session
                session = TagSportsSession(
                    session_id=session_dict["session_id"],
                    date=datetime.fromisoformat(
                        session_dict["date"].replace("Z", "+00:00")
                    ),
                    location=session_dict.get("location", "Unknown"),
                    session_type=session_dict.get("session_type", "practice"),
                    total_pitches=summary.get("total_pitches", len(pitches)),
                    avg_speed_mph=summary.get(
                        "avg_speed_mph",
                        sum(p.speed_mph for p in pitches) / len(pitches) if pitches else 0
                    ),
                    max_speed_mph=summary.get(
                        "max_speed_mph",
                        max((p.speed_mph for p in pitches), default=0)
                    ),
                    min_speed_mph=summary.get(
                        "min_speed_mph",
                        min((p.speed_mph for p in pitches), default=0)
                    ),
                    pitches=pitches,
                    notes=session_dict.get("notes", ""),
                )

                sessions.append(session)

            except Exception as e:
                warnings.append(f"Failed to parse session {idx + 1}: {str(e)}")
                logger.warning(f"Failed to parse session {idx + 1}: {e}")

        return sessions, warnings

    def validate_session_data(self, session: TagSportsSession) -> List[str]:
        """Validate session data for quality/sanity checks.

        Args:
            session: TAG Sports session to validate

        Returns:
            List of validation warnings (empty if all OK)
        """
        warnings = []

        # Check pitch count consistency
        if session.total_pitches != len(session.pitches):
            warnings.append(
                f"Session {session.session_id}: Summary says {session.total_pitches} pitches "
                f"but {len(session.pitches)} pitches in array"
            )

        # Check velocity ranges (sanity check)
        for pitch in session.pitches:
            if pitch.speed_mph < 20 or pitch.speed_mph > 120:
                warnings.append(
                    f"Session {session.session_id}, Pitch {pitch.pitch_number}: "
                    f"Unusual velocity ({pitch.speed_mph} mph) - possible measurement error"
                )

        # Check date ordering
        if session.pitches:
            timestamps = [p.timestamp for p in session.pitches]
            if timestamps != sorted(timestamps):
                warnings.append(
                    f"Session {session.session_id}: Pitch timestamps not in chronological order"
                )

        return warnings


# Future: Cloud API integration (Phase 2)
class TagSportsCloudAPIClient:
    """Client for PitchTracker cloud API (TAG Sports integration).

    Used by both TAG Sports mobile app and PitchTracker desktop app to
    sync athlete data via cloud platform.

    Phase 2 implementation (Months 4-6).
    See: docs/TAG_DEEP_INTEGRATION_API_SPEC.md
    """

    def __init__(self, api_base_url: str = "https://api.pitchtracker.io/v1"):
        """Initialize cloud API client.

        Args:
            api_base_url: Base URL for PitchTracker cloud API
        """
        self.api_base_url = api_base_url
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None

    # TODO: Implement OAuth authentication
    # TODO: Implement session upload/download
    # TODO: Implement athlete profile management
    # TODO: Implement webhook subscriptions


# Future: Bluetooth integration (Phase 3)
class TagSportsBluetoothService:
    """Bluetooth integration for TAG Sports devices.

    Enables TAG Sports devices to connect directly to facility PCs via Bluetooth,
    streaming real-time velocity measurements during PitchTracker sessions.

    Phase 3 implementation (Months 7-9).
    See: docs/TAG_DEEP_INTEGRATION_API_SPEC.md
    """

    def __init__(self):
        """Initialize Bluetooth service."""
        self._connected = False
        self._device_id: Optional[str] = None

    # TODO: Implement BLE device discovery
    # TODO: Implement BLE connection/pairing
    # TODO: Implement pitch data streaming via BLE notifications
    # TODO: Implement session control commands


__all__ = [
    "TagSportsIntegrationService",
    "TagSportsImportResult",
    "TagSportsSession",
    "TagSportsPitch",
    "TagSportsAthleteData",
    "TagSportsCloudAPIClient",  # Future
    "TagSportsBluetoothService",  # Future
]

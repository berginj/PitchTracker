"""TAG Sports integration service for importing practice data and staged runtime adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.services.tag_sports_adapters import (
    TagBluetoothAdapter,
    TagBluetoothDevice,
    TagBluetoothPitchMeasurement,
    TagCloudAdapter,
    TagCloudTokens,
    TagCloudUploadReceipt,
)
from app.services.tag_sports_flags import TagSportsFeatureFlags


SUPPORTED_SCHEMA_VERSIONS = ["1.0"]


class TagSportsFeatureDisabledError(RuntimeError):
    """Raised when a staged TAG feature is disabled by feature flag."""


class TagSportsAuthenticationError(RuntimeError):
    """Raised when a cloud operation is attempted before authentication."""


class TagSportsConfigurationError(RuntimeError):
    """Raised when a staged TAG runtime is enabled without a concrete adapter."""


@dataclass
class TagSportsPitch:
    """Individual pitch measurement from TAG Sports device."""

    pitch_number: int
    timestamp: datetime
    speed_mph: float
    pitch_type: str = ""
    notes: str = ""
    video_url: Optional[str] = None


@dataclass
class TagSportsSession:
    """TAG Sports practice session data."""

    session_id: str
    date: datetime
    location: str
    session_type: str
    total_pitches: int
    avg_speed_mph: float
    max_speed_mph: float
    min_speed_mph: float
    pitches: List[TagSportsPitch]
    notes: str = ""


@dataclass
class TagSportsAthleteData:
    """TAG Sports athlete information."""

    tag_user_id: str
    name: str
    birth_year: Optional[int] = None
    throws: Optional[str] = None
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
    """Service for importing and managing TAG Sports practice data."""

    def __init__(
        self,
        *,
        feature_flags: Optional[TagSportsFeatureFlags] = None,
        cloud_adapter: Optional[TagCloudAdapter] = None,
        bluetooth_adapter: Optional[TagBluetoothAdapter] = None,
    ):
        self._import_history: List[Path] = []
        self.feature_flags = feature_flags or TagSportsFeatureFlags.from_env()
        self.cloud_client = TagSportsCloudAPIClient(
            feature_flags=self.feature_flags,
            adapter=cloud_adapter,
        )
        self.bluetooth_service = TagSportsBluetoothService(
            feature_flags=self.feature_flags,
            adapter=bluetooth_adapter,
        )

    def import_from_file(self, file_path: Path) -> TagSportsImportResult:
        """Import TAG Sports data from JSON export file."""
        if not file_path.exists():
            raise FileNotFoundError(f"TAG Sports export file not found: {file_path}")

        try:
            logger.info(f"Importing TAG Sports data from: {file_path}")
            with open(file_path, "r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)

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

            validation_errors = self._validate_required_fields(data)
            if validation_errors:
                return TagSportsImportResult(
                    success=False,
                    athlete_data=None,
                    sessions_imported=0,
                    pitches_imported=0,
                    errors=validation_errors,
                )

            athlete_data = self._parse_athlete_data(data["athlete"])
            sessions, session_warnings = self._parse_sessions(data["sessions"])
            total_pitches = sum(session.total_pitches for session in sessions)

            self._import_history.append(file_path)
            logger.info(
                f"Successfully imported {len(sessions)} sessions ({total_pitches} pitches) " f"for {athlete_data.name}"
            )

            return TagSportsImportResult(
                success=True,
                athlete_data=athlete_data,
                sessions_imported=len(sessions),
                pitches_imported=total_pitches,
                errors=[],
                warnings=session_warnings,
            )

        except json.JSONDecodeError as exc:
            logger.error(f"Invalid JSON file: {exc}")
            return TagSportsImportResult(
                success=False,
                athlete_data=None,
                sessions_imported=0,
                pitches_imported=0,
                errors=[f"Invalid JSON file: {exc}"],
            )
        except Exception as exc:
            logger.exception(f"Failed to import TAG Sports data: {exc}")
            return TagSportsImportResult(
                success=False,
                athlete_data=None,
                sessions_imported=0,
                pitches_imported=0,
                errors=[f"Import failed: {exc}"],
            )

    def get_runtime_capabilities(self) -> dict[str, bool]:
        """Return feature-flag state for staged TAG integrations."""
        return {
            "cloud_sync_enabled": self.feature_flags.cloud_sync_enabled,
            "bluetooth_enabled": self.feature_flags.bluetooth_enabled,
        }

    def _validate_required_fields(self, data: dict) -> List[str]:
        errors = []
        required_top = ["schema_version", "export_metadata", "athlete", "sessions"]
        for field_name in required_top:
            if field_name not in data:
                errors.append(f"Missing required field: {field_name}")

        if "athlete" in data:
            athlete = data["athlete"]
            for field_name in ["tag_user_id", "name"]:
                if field_name not in athlete:
                    errors.append(f"Missing required athlete field: {field_name}")

        return errors

    def _parse_athlete_data(self, athlete_dict: dict) -> TagSportsAthleteData:
        return TagSportsAthleteData(
            tag_user_id=athlete_dict["tag_user_id"],
            name=athlete_dict["name"],
            birth_year=athlete_dict.get("birth_year"),
            throws=athlete_dict.get("throws"),
            position=athlete_dict.get("position"),
            email=athlete_dict.get("email"),
        )

    def _parse_sessions(self, sessions_list: List[dict]) -> tuple[List[TagSportsSession], List[str]]:
        sessions: List[TagSportsSession] = []
        warnings: List[str] = []

        for idx, session_dict in enumerate(sessions_list):
            try:
                pitches = []
                for pitch_dict in session_dict.get("pitches", []):
                    pitches.append(
                        TagSportsPitch(
                            pitch_number=pitch_dict["pitch_number"],
                            timestamp=datetime.fromisoformat(pitch_dict["timestamp"].replace("Z", "+00:00")),
                            speed_mph=pitch_dict["speed_mph"],
                            pitch_type=pitch_dict.get("pitch_type", ""),
                            notes=pitch_dict.get("notes", ""),
                            video_url=pitch_dict.get("video_url"),
                        )
                    )

                summary = session_dict.get("summary", {})
                session = TagSportsSession(
                    session_id=session_dict["session_id"],
                    date=datetime.fromisoformat(session_dict["date"].replace("Z", "+00:00")),
                    location=session_dict.get("location", "Unknown"),
                    session_type=session_dict.get("session_type", "practice"),
                    total_pitches=summary.get("total_pitches", len(pitches)),
                    avg_speed_mph=summary.get(
                        "avg_speed_mph",
                        sum(p.speed_mph for p in pitches) / len(pitches) if pitches else 0.0,
                    ),
                    max_speed_mph=summary.get(
                        "max_speed_mph",
                        max((p.speed_mph for p in pitches), default=0.0),
                    ),
                    min_speed_mph=summary.get(
                        "min_speed_mph",
                        min((p.speed_mph for p in pitches), default=0.0),
                    ),
                    pitches=pitches,
                    notes=session_dict.get("notes", ""),
                )

                warnings.extend(self.validate_session_data(session))
                sessions.append(session)
            except Exception as exc:
                warnings.append(f"Failed to parse session {idx + 1}: {exc}")
                logger.warning(f"Failed to parse session {idx + 1}: {exc}")

        return sessions, warnings

    def validate_session_data(self, session: TagSportsSession) -> List[str]:
        warnings = []

        if session.total_pitches != len(session.pitches):
            warnings.append(
                f"Session {session.session_id}: Summary says {session.total_pitches} pitches "
                f"but {len(session.pitches)} pitches in array"
            )

        for pitch in session.pitches:
            if pitch.speed_mph < 20 or pitch.speed_mph > 120:
                warnings.append(
                    f"Session {session.session_id}, Pitch {pitch.pitch_number}: "
                    f"Unusual velocity ({pitch.speed_mph} mph) - possible measurement error"
                )

        if session.pitches:
            timestamps = [pitch.timestamp for pitch in session.pitches]
            if timestamps != sorted(timestamps):
                warnings.append(f"Session {session.session_id}: Pitch timestamps not in chronological order")

        return warnings


class TagSportsCloudAPIClient:
    """Feature-flagged client for staged TAG cloud sync deliverables."""

    def __init__(
        self,
        *,
        api_base_url: str = "https://api.pitchtracker.io/v1",
        feature_flags: Optional[TagSportsFeatureFlags] = None,
        adapter: Optional[TagCloudAdapter] = None,
    ) -> None:
        self.api_base_url = api_base_url
        self._feature_flags = feature_flags or TagSportsFeatureFlags.from_env()
        self._adapter = adapter
        self._tokens: Optional[TagCloudTokens] = None

    def authenticate(self, client_id: str, client_secret: str) -> TagCloudTokens:
        adapter = self._require_enabled()
        self._tokens = adapter.authenticate(client_id, client_secret)
        return self._tokens

    def upload_session(
        self,
        athlete: TagSportsAthleteData,
        session: TagSportsSession,
    ) -> TagCloudUploadReceipt:
        adapter = self._require_authenticated()
        return adapter.upload_session(athlete, session)

    def download_sessions(self, athlete_id: str) -> List[TagSportsSession]:
        adapter = self._require_authenticated()
        return list(adapter.download_sessions(athlete_id))

    def _require_enabled(self) -> TagCloudAdapter:
        if not self._feature_flags.cloud_sync_enabled:
            raise TagSportsFeatureDisabledError(
                "TAG cloud sync is disabled. Enable PITCHTRACKER_TAG_CLOUD_SYNC_ENABLED to use it."
            )
        if self._adapter is None:
            raise TagSportsConfigurationError("TAG cloud sync is enabled, but no cloud adapter is configured.")
        return self._adapter

    def _require_authenticated(self) -> TagCloudAdapter:
        adapter = self._require_enabled()
        if self._tokens is None:
            raise TagSportsAuthenticationError("Authenticate the TAG cloud client before syncing.")
        return adapter


class TagSportsBluetoothService:
    """Feature-flagged Bluetooth service with a mock runtime adapter."""

    def __init__(
        self,
        *,
        feature_flags: Optional[TagSportsFeatureFlags] = None,
        adapter: Optional[TagBluetoothAdapter] = None,
    ) -> None:
        self._feature_flags = feature_flags or TagSportsFeatureFlags.from_env()
        self._adapter = adapter
        self._connected_device: Optional[TagBluetoothDevice] = None

    def discover_devices(self) -> List[TagBluetoothDevice]:
        adapter = self._require_enabled()
        return list(adapter.discover_devices())

    def connect(self, device_id: str) -> TagBluetoothDevice:
        adapter = self._require_enabled()
        self._connected_device = adapter.connect(device_id)
        return self._connected_device

    def disconnect(self) -> None:
        if not self._feature_flags.bluetooth_enabled:
            return
        if self._adapter is None:
            raise TagSportsConfigurationError(
                "TAG Bluetooth integration is enabled, but no Bluetooth adapter is configured."
            )
        self._adapter.disconnect()
        self._connected_device = None

    def read_measurements(self) -> List[TagBluetoothPitchMeasurement]:
        adapter = self._require_enabled()
        if self._connected_device is None:
            raise RuntimeError("Connect to a TAG Bluetooth device before reading measurements.")
        return list(adapter.read_measurements())

    def _require_enabled(self) -> TagBluetoothAdapter:
        if not self._feature_flags.bluetooth_enabled:
            raise TagSportsFeatureDisabledError(
                "TAG Bluetooth integration is disabled. Enable PITCHTRACKER_TAG_BLE_ENABLED to use it."
            )
        if self._adapter is None:
            raise TagSportsConfigurationError(
                "TAG Bluetooth integration is enabled, but no Bluetooth adapter is configured."
            )
        return self._adapter


__all__ = [
    "SUPPORTED_SCHEMA_VERSIONS",
    "TagSportsAthleteData",
    "TagSportsAuthenticationError",
    "TagSportsBluetoothService",
    "TagSportsConfigurationError",
    "TagSportsFeatureDisabledError",
    "TagSportsImportResult",
    "TagSportsIntegrationService",
    "TagSportsPitch",
    "TagSportsSession",
    "TagSportsCloudAPIClient",
]

"""Adapter interfaces and mock implementations for TAG Sports integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.services.tag_sports_integration import TagSportsAthleteData, TagSportsSession


@dataclass(frozen=True)
class TagCloudTokens:
    """Authenticated cloud-session tokens."""

    access_token: str
    refresh_token: str
    expires_at: datetime


@dataclass(frozen=True)
class TagCloudUploadReceipt:
    """Cloud upload acknowledgement."""

    athlete_id: str
    session_id: str
    uploaded_pitch_count: int
    uploaded_at: datetime


@dataclass(frozen=True)
class TagBluetoothDevice:
    """BLE device metadata exposed to the UI."""

    device_id: str
    name: str
    firmware_version: str
    battery_percent: int


@dataclass(frozen=True)
class TagBluetoothPitchMeasurement:
    """Single live measurement streamed from a TAG device."""

    pitch_number: int
    speed_mph: float
    measured_at: datetime


class TagCloudAdapter(ABC):
    """Boundary for TAG cloud sync implementations."""

    @abstractmethod
    def authenticate(self, client_id: str, client_secret: str) -> TagCloudTokens:
        """Authenticate against the TAG cloud surface."""

    @abstractmethod
    def upload_session(
        self,
        athlete: "TagSportsAthleteData",
        session: "TagSportsSession",
    ) -> TagCloudUploadReceipt:
        """Upload a session payload."""

    @abstractmethod
    def download_sessions(self, athlete_id: str) -> List["TagSportsSession"]:
        """Download sessions for an athlete."""


class TagBluetoothAdapter(ABC):
    """Boundary for TAG Bluetooth implementations."""

    @abstractmethod
    def discover_devices(self) -> List[TagBluetoothDevice]:
        """Return nearby TAG devices."""

    @abstractmethod
    def connect(self, device_id: str) -> TagBluetoothDevice:
        """Connect to a TAG device."""

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the current TAG device."""

    @abstractmethod
    def read_measurements(self) -> List[TagBluetoothPitchMeasurement]:
        """Read live pitch measurements from the current TAG device."""


class MockTagCloudAdapter(TagCloudAdapter):
    """In-memory cloud adapter for staged runtime wiring and tests."""

    def __init__(self) -> None:
        self._sessions_by_athlete: dict[str, list["TagSportsSession"]] = {}
        self._authenticated = False

    def authenticate(self, client_id: str, client_secret: str) -> TagCloudTokens:
        del client_id, client_secret
        self._authenticated = True
        return TagCloudTokens(
            access_token="mock-access-token",
            refresh_token="mock-refresh-token",
            expires_at=datetime.now(timezone.utc).replace(microsecond=0),
        )

    def upload_session(
        self,
        athlete: "TagSportsAthleteData",
        session: "TagSportsSession",
    ) -> TagCloudUploadReceipt:
        if not self._authenticated:
            raise RuntimeError("Cloud adapter is not authenticated")

        self._sessions_by_athlete.setdefault(athlete.tag_user_id, []).append(session)
        return TagCloudUploadReceipt(
            athlete_id=athlete.tag_user_id,
            session_id=session.session_id,
            uploaded_pitch_count=len(session.pitches),
            uploaded_at=datetime.now(timezone.utc).replace(microsecond=0),
        )

    def download_sessions(self, athlete_id: str) -> List["TagSportsSession"]:
        if not self._authenticated:
            raise RuntimeError("Cloud adapter is not authenticated")
        return list(self._sessions_by_athlete.get(athlete_id, []))


class MockTagBluetoothAdapter(TagBluetoothAdapter):
    """In-memory BLE adapter for staged runtime wiring and tests."""

    def __init__(
        self,
        devices: Optional[list[TagBluetoothDevice]] = None,
        measurements: Optional[list[TagBluetoothPitchMeasurement]] = None,
    ) -> None:
        self._devices = devices or [
            TagBluetoothDevice(
                device_id="tag-device-001",
                name="TAG Pocket Radar",
                firmware_version="mock-1.0.0",
                battery_percent=87,
            )
        ]
        self._measurements = measurements or [
            TagBluetoothPitchMeasurement(
                pitch_number=1,
                speed_mph=71.4,
                measured_at=datetime.now(timezone.utc).replace(microsecond=0),
            )
        ]
        self._connected_device_id: Optional[str] = None

    def discover_devices(self) -> List[TagBluetoothDevice]:
        return list(self._devices)

    def connect(self, device_id: str) -> TagBluetoothDevice:
        for device in self._devices:
            if device.device_id == device_id:
                self._connected_device_id = device_id
                return device
        raise ValueError(f"Unknown TAG device: {device_id}")

    def disconnect(self) -> None:
        self._connected_device_id = None

    def read_measurements(self) -> List[TagBluetoothPitchMeasurement]:
        if self._connected_device_id is None:
            raise RuntimeError("No TAG device connected")
        return list(self._measurements)

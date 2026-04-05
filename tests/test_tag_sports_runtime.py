"""Tests for staged TAG runtime adapters and feature flags."""

from datetime import datetime, timezone

import pytest

from app.services.tag_sports_adapters import MockTagBluetoothAdapter, MockTagCloudAdapter
from app.services.tag_sports_flags import TagSportsFeatureFlags
from app.services.tag_sports_integration import (
    TagSportsAthleteData,
    TagSportsBluetoothService,
    TagSportsCloudAPIClient,
    TagSportsConfigurationError,
    TagSportsFeatureDisabledError,
    TagSportsPitch,
    TagSportsSession,
)


def _athlete() -> TagSportsAthleteData:
    return TagSportsAthleteData(tag_user_id="athlete-001", name="Test Athlete")


def _session() -> TagSportsSession:
    return TagSportsSession(
        session_id="session-001",
        date=datetime(2026, 3, 26, 10, 30, tzinfo=timezone.utc),
        location="Bullpen",
        session_type="practice",
        total_pitches=1,
        avg_speed_mph=72.4,
        max_speed_mph=72.4,
        min_speed_mph=72.4,
        pitches=[
            TagSportsPitch(
                pitch_number=1,
                timestamp=datetime(2026, 3, 26, 10, 31, tzinfo=timezone.utc),
                speed_mph=72.4,
            )
        ],
    )


def test_cloud_client_round_trips_sessions_with_mock_adapter() -> None:
    flags = TagSportsFeatureFlags(cloud_sync_enabled=True)
    client = TagSportsCloudAPIClient(
        feature_flags=flags,
        adapter=MockTagCloudAdapter(),
    )

    tokens = client.authenticate("client-id", "secret")
    receipt = client.upload_session(_athlete(), _session())
    sessions = client.download_sessions("athlete-001")

    assert tokens.access_token == "mock-access-token"
    assert receipt.uploaded_pitch_count == 1
    assert len(sessions) == 1
    assert sessions[0].session_id == "session-001"


def test_cloud_client_respects_feature_flag() -> None:
    client = TagSportsCloudAPIClient(
        feature_flags=TagSportsFeatureFlags(cloud_sync_enabled=False),
        adapter=MockTagCloudAdapter(),
    )

    with pytest.raises(TagSportsFeatureDisabledError):
        client.authenticate("client-id", "secret")


def test_cloud_client_requires_configured_adapter_when_enabled() -> None:
    client = TagSportsCloudAPIClient(
        feature_flags=TagSportsFeatureFlags(cloud_sync_enabled=True),
        adapter=None,
    )

    with pytest.raises(TagSportsConfigurationError):
        client.authenticate("client-id", "secret")


def test_bluetooth_service_streams_mock_measurements() -> None:
    service = TagSportsBluetoothService(
        feature_flags=TagSportsFeatureFlags(bluetooth_enabled=True),
        adapter=MockTagBluetoothAdapter(),
    )

    devices = service.discover_devices()
    device = service.connect(devices[0].device_id)
    measurements = service.read_measurements()
    service.disconnect()

    assert device.device_id == devices[0].device_id
    assert measurements
    assert measurements[0].speed_mph > 0


def test_bluetooth_service_respects_feature_flag() -> None:
    service = TagSportsBluetoothService(
        feature_flags=TagSportsFeatureFlags(bluetooth_enabled=False),
        adapter=MockTagBluetoothAdapter(),
    )

    with pytest.raises(TagSportsFeatureDisabledError):
        service.discover_devices()


def test_bluetooth_service_requires_configured_adapter_when_enabled() -> None:
    service = TagSportsBluetoothService(
        feature_flags=TagSportsFeatureFlags(bluetooth_enabled=True),
        adapter=None,
    )

    with pytest.raises(TagSportsConfigurationError):
        service.discover_devices()

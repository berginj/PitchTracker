"""Tests for TAG Sports integration service.

Part of TAG Sports Partnership integration (March 2026).
Tests manual JSON import (Phase 1) and validates data handling.

Future phases:
- Phase 2: Cloud API integration tests
- Phase 3: Bluetooth integration tests
- Phase 4: Webhook and insights tests
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.tag_sports_integration import (
    TagSportsIntegrationService,
)


@pytest.fixture
def valid_tag_export_data():
    """Create valid TAG Sports export data for testing."""
    return {
        "schema_version": "1.0",
        "export_metadata": {
            "export_date": "2026-03-26T10:30:00Z",
            "export_source": "TAG_Sports_iOS",
            "app_version": "2.3.1",
        },
        "athlete": {
            "tag_user_id": "tag_test_123",
            "name": "Test Athlete",
            "birth_year": 2010,
            "throws": "right",
            "position": "pitcher",
            "email": "test@example.com",
        },
        "sessions": [
            {
                "session_id": "tag_session_001",
                "date": "2026-03-20T15:00:00Z",
                "location": "Test location",
                "session_type": "practice",
                "notes": "Test session",
                "pitches": [
                    {
                        "pitch_number": 1,
                        "timestamp": "2026-03-20T15:05:23Z",
                        "speed_mph": 72.3,
                        "pitch_type": "Fastball",
                    },
                    {
                        "pitch_number": 2,
                        "timestamp": "2026-03-20T15:06:10Z",
                        "speed_mph": 68.5,
                        "pitch_type": "Changeup",
                    },
                ],
                "summary": {
                    "total_pitches": 2,
                    "avg_speed_mph": 70.4,
                    "max_speed_mph": 72.3,
                    "min_speed_mph": 68.5,
                },
            }
        ],
    }


@pytest.fixture
def valid_tag_export_file(tmp_path, valid_tag_export_data):
    """Create valid TAG Sports export JSON file for testing."""
    file_path = tmp_path / "TAG_export_test.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(valid_tag_export_data, f, indent=2)
    return file_path


class TestTagSportsIntegrationService:
    """Tests for TAG Sports integration service."""

    def test_import_valid_file(self, valid_tag_export_file):
        """Test importing valid TAG Sports export file."""
        service = TagSportsIntegrationService()
        result = service.import_from_file(valid_tag_export_file)

        assert result.success is True
        assert result.athlete_data is not None
        assert result.athlete_data.name == "Test Athlete"
        assert result.athlete_data.tag_user_id == "tag_test_123"
        assert result.sessions_imported == 1
        assert result.pitches_imported == 2
        assert len(result.errors) == 0

    def test_import_nonexistent_file(self):
        """Test importing file that doesn't exist."""
        service = TagSportsIntegrationService()

        with pytest.raises(FileNotFoundError):
            service.import_from_file(Path("nonexistent.json"))

    def test_import_invalid_json(self, tmp_path):
        """Test importing file with invalid JSON."""
        file_path = tmp_path / "invalid.json"
        with open(file_path, "w") as f:
            f.write("{ invalid json }")

        service = TagSportsIntegrationService()
        result = service.import_from_file(file_path)

        assert result.success is False
        assert "Invalid JSON file" in result.errors[0]

    def test_import_unsupported_schema_version(self, tmp_path):
        """Test importing file with unsupported schema version."""
        data = {
            "schema_version": "99.0",  # Unsupported
            "export_metadata": {},
            "athlete": {"tag_user_id": "test", "name": "Test"},
            "sessions": [],
        }

        file_path = tmp_path / "unsupported_version.json"
        with open(file_path, "w") as f:
            json.dump(data, f)

        service = TagSportsIntegrationService()
        result = service.import_from_file(file_path)

        assert result.success is False
        assert "Unsupported schema version" in result.errors[0]

    def test_import_missing_required_fields(self, tmp_path):
        """Test importing file with missing required fields."""
        data = {
            "schema_version": "1.0",
            # Missing export_metadata, athlete, sessions
        }

        file_path = tmp_path / "missing_fields.json"
        with open(file_path, "w") as f:
            json.dump(data, f)

        service = TagSportsIntegrationService()
        result = service.import_from_file(file_path)

        assert result.success is False
        assert len(result.errors) > 0
        assert any("Missing required field" in error for error in result.errors)

    def test_import_multiple_sessions(self, tmp_path):
        """Test importing file with multiple sessions."""
        data = {
            "schema_version": "1.0",
            "export_metadata": {
                "export_date": "2026-03-26T10:30:00Z",
                "export_source": "TAG_Sports_iOS",
            },
            "athlete": {
                "tag_user_id": "tag_test_123",
                "name": "Test Athlete",
            },
            "sessions": [
                {
                    "session_id": f"session_{i}",
                    "date": f"2026-03-{20+i:02d}T15:00:00Z",
                    "pitches": [
                        {
                            "pitch_number": j + 1,
                            "timestamp": f"2026-03-{20+i:02d}T15:{j:02d}:00Z",
                            "speed_mph": 70.0 + j,
                        }
                        for j in range(10)
                    ],
                    "summary": {"total_pitches": 10, "avg_speed_mph": 74.5},
                }
                for i in range(5)
            ],
        }

        file_path = tmp_path / "multiple_sessions.json"
        with open(file_path, "w") as f:
            json.dump(data, f)

        service = TagSportsIntegrationService()
        result = service.import_from_file(file_path)

        assert result.success is True
        assert result.sessions_imported == 5
        assert result.pitches_imported == 50  # 5 sessions × 10 pitches

    def test_import_with_invalid_velocities(self, tmp_path):
        """Test importing file with invalid velocity values (sanity check warnings)."""
        data = {
            "schema_version": "1.0",
            "export_metadata": {
                "export_date": "2026-03-26T10:30:00Z",
                "export_source": "TAG_Sports_iOS",
            },
            "athlete": {
                "tag_user_id": "tag_test_123",
                "name": "Test Athlete",
            },
            "sessions": [
                {
                    "session_id": "session_001",
                    "date": "2026-03-20T15:00:00Z",
                    "pitches": [
                        {
                            "pitch_number": 1,
                            "timestamp": "2026-03-20T15:05:23Z",
                            "speed_mph": 200.0,  # Unrealistic
                        }
                    ],
                    "summary": {"total_pitches": 1, "avg_speed_mph": 200.0},
                }
            ],
        }

        file_path = tmp_path / "invalid_velocity.json"
        with open(file_path, "w") as f:
            json.dump(data, f)

        service = TagSportsIntegrationService()
        result = service.import_from_file(file_path)

        # Should import successfully but include warnings
        assert result.success is True
        assert len(result.warnings) > 0
        assert any("Unusual velocity" in warning for warning in result.warnings)


# Phase 2 Tests (Future - Cloud API)
@pytest.mark.skip(reason="Phase 2 not yet implemented - Cloud API integration")
class TestTagSportsCloudAPI:
    """Tests for TAG Sports cloud API integration (Phase 2)."""

    def test_oauth_authentication(self):
        """Test OAuth 2.0 authentication flow."""

    def test_athlete_profile_sync(self):
        """Test athlete profile creation and sync."""

    def test_session_upload(self):
        """Test uploading session data to cloud."""

    def test_session_download(self):
        """Test downloading athlete session history from cloud."""


# Phase 3 Tests (Future - Bluetooth)
@pytest.mark.skip(reason="Phase 3 not yet implemented - Bluetooth integration")
class TestTagSportsBluetoothIntegration:
    """Tests for TAG Sports Bluetooth PC integration (Phase 3)."""

    def test_device_discovery(self):
        """Test scanning for nearby TAG Sports devices."""

    def test_device_pairing(self):
        """Test pairing with TAG Sports device via Bluetooth."""

    def test_pitch_data_streaming(self):
        """Test receiving real-time pitch data via BLE notifications."""

    def test_cross_validation(self):
        """Test cross-validation of TAG velocity vs. PitchTracker stereo."""

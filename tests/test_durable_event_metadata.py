"""AGT-001: Durable metadata persistence and replay integration tests.

Tests that event metadata embedded in pitch manifests survives
serialization and is correctly loaded by the session loader,
including backwards-compatible handling of legacy artifacts
without metadata, and the old single-event shape.
"""

from __future__ import annotations

import json

from app.events.event_metadata import EventMetadata, make_event_metadata
from app.pipeline.recording.manifest import (
    create_pitch_manifest,
    create_session_manifest,
)
from app.review.session_loader import SessionLoader


class _FakeSummary:
    """Minimal PitchSummary substitute for manifest tests."""

    def __init__(self, pitch_id="pitch_00001"):
        self.pitch_id = pitch_id
        self.t_start_ns = 1000000
        self.t_end_ns = 2000000
        self.is_strike = True
        self.zone_row = 1
        self.zone_col = 1
        self.run_in = 2.0
        self.rise_in = 1.0
        self.speed_mph = 75.0
        self.rotation_rpm = None
        self.measurement_status = "USABLE"
        self.speed_source = "manual_override"
        self.correction_records = []
        self.quality_diagnostics = {}
        self.trajectory_plate_x_ft = 0.0
        self.trajectory_plate_y_ft = 2.5
        self.trajectory_plate_z_ft = 0.0
        self.trajectory_plate_t_ns = 1500000
        self.trajectory_model = "physics_drag"
        self.trajectory_mode = "stereo_3d"
        self.trajectory_expected_error_ft = 0.05
        self.trajectory_confidence = 0.9
        self.trajectory_comparison = None
        self.ray_rmse_px = None
        self.estimated_camera_time_offset_ms = None
        self.ray_failure_codes = None
        self.observation_quality_status = "PASS"
        self.observation_rejection_reasons = []
        self.observation_warning_reasons = []
        self.observation_mean_confidence = 0.8
        self.observation_mean_depth_sigma_ft = 0.02
        self.observation_max_depth_sigma_ft = 0.04
        self.observation_max_gap_ms = 5.0
        self.observation_z_span_ft = 45.0
        self.sample_count = 20


class TestPitchManifestLifecycleMetadata:
    """Verify lifecycle metadata round-trips through pitch manifest."""

    def test_lifecycle_metadata_embedded(self):
        lifecycle = {
            "pitch_start": make_event_metadata(
                "PitchStartEvent", correlation_id="pitch_00001",
                pitch_id="pitch_00001", session_id="s1", timestamp_ns=100,
            ).to_dict(),
            "pitch_end": make_event_metadata(
                "PitchEndEvent", correlation_id="pitch_00001",
                pitch_id="pitch_00001", session_id="s1", timestamp_ns=200,
            ).to_dict(),
            "pitch_analyzed": make_event_metadata(
                "PitchAnalyzedEvent", correlation_id="pitch_00001",
                pitch_id="pitch_00001", session_id="s1", timestamp_ns=200,
            ).to_dict(),
        }
        manifest = create_pitch_manifest(
            _FakeSummary(), "configs/default.yaml", event_metadata=lifecycle,
        )

        assert "event_metadata" in manifest
        em = manifest["event_metadata"]
        assert "pitch_start" in em
        assert "pitch_end" in em
        assert "pitch_analyzed" in em
        assert em["pitch_start"]["pitch_id"] == "pitch_00001"
        assert em["pitch_end"]["session_id"] == "s1"
        assert em["pitch_analyzed"]["correlation_id"] == "pitch_00001"

    def test_no_metadata_when_none(self):
        manifest = create_pitch_manifest(_FakeSummary(), "configs/default.yaml")
        assert "event_metadata" not in manifest

    def test_lifecycle_json_roundtrip(self):
        lifecycle = {
            "pitch_start": {"message_type": "PitchStartEvent", "correlation_id": "p1"},
            "pitch_end": {"message_type": "PitchEndEvent", "correlation_id": "p1"},
            "pitch_analyzed": {"message_type": "PitchAnalyzedEvent", "correlation_id": "p1"},
        }
        manifest = create_pitch_manifest(
            _FakeSummary(), "configs/default.yaml", event_metadata=lifecycle,
        )
        restored = json.loads(json.dumps(manifest))
        assert restored["event_metadata"]["pitch_start"]["correlation_id"] == "p1"


class TestSessionManifestMetadata:
    """Verify event_metadata in session manifest."""

    def test_session_manifest_with_metadata(self):
        meta = {"session_id": "bullpen", "message_type": "session_lifecycle"}
        manifest = create_session_manifest(
            pitch_id="pitch_00001", session_name="bullpen",
            mode="coaching", measured_speed_mph=0.0,
            config_path="configs/default.yaml", event_metadata=meta,
        )
        assert manifest["event_metadata"]["session_id"] == "bullpen"

    def test_session_manifest_without_metadata(self):
        manifest = create_session_manifest(
            pitch_id="pitch_00001", session_name="bullpen",
            mode="coaching", measured_speed_mph=0.0,
            config_path="configs/default.yaml",
        )
        assert "event_metadata" not in manifest


class TestSessionLoaderBackwardsCompatibility:
    """Loader handles legacy, old-single-event, and new lifecycle shapes."""

    def _make_session(self, tmp_path, pitch_manifest_data):
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        (session_dir / "manifest.json").write_text(json.dumps({
            "session_id": "test", "session_left_video": "session_left.avi",
            "session_right_video": "session_right.avi",
        }))
        (session_dir / "session_left.avi").write_bytes(b"")
        (session_dir / "session_right.avi").write_bytes(b"")
        pitch_dir = session_dir / "pitch_00001"
        pitch_dir.mkdir()
        (pitch_dir / "manifest.json").write_text(json.dumps(pitch_manifest_data))
        return session_dir

    def test_legacy_no_metadata(self, tmp_path):
        """Oldest artifacts: no event_metadata key at all."""
        sd = self._make_session(tmp_path, {
            "pitch_id": "pitch_00001",
            "left_video": "left.avi", "right_video": "right.avi",
        })
        loaded = SessionLoader.load_session(sd)
        assert loaded.pitches[0].event_metadata is None
        assert EventMetadata.from_dict(loaded.pitches[0].event_metadata) == EventMetadata()

    def test_old_single_event_shape(self, tmp_path):
        """Previous iteration: flat EventMetadata dict."""
        flat_meta = make_event_metadata(
            "PitchAnalyzedEvent", correlation_id="pitch_00001",
            pitch_id="pitch_00001", session_id="s1",
        ).to_dict()
        sd = self._make_session(tmp_path, {
            "pitch_id": "pitch_00001",
            "left_video": "left.avi", "right_video": "right.avi",
            "event_metadata": flat_meta,
        })
        loaded = SessionLoader.load_session(sd)
        em = loaded.pitches[0].event_metadata
        assert em is not None
        # Flat shape: has message_type at top level
        assert em["message_type"] == "PitchAnalyzedEvent"
        # Can still be deserialized as EventMetadata
        assert EventMetadata.from_dict(em).correlation_id == "pitch_00001"

    def test_new_lifecycle_shape(self, tmp_path):
        """Current iteration: lifecycle sub-keys."""
        lifecycle = {
            "pitch_start": {"correlation_id": "pitch_00001", "session_id": "s1"},
            "pitch_end": {"correlation_id": "pitch_00001", "session_id": "s1"},
            "pitch_analyzed": {"correlation_id": "pitch_00001", "session_id": "s1"},
        }
        sd = self._make_session(tmp_path, {
            "pitch_id": "pitch_00001",
            "left_video": "left.avi", "right_video": "right.avi",
            "event_metadata": lifecycle,
        })
        loaded = SessionLoader.load_session(sd)
        em = loaded.pitches[0].event_metadata
        assert em is not None
        assert "pitch_start" in em
        assert "pitch_analyzed" in em
        assert em["pitch_analyzed"]["correlation_id"] == "pitch_00001"


class TestRecordingServiceLifecycleIntegration:
    """Integration: publish start/end/analyzed → artifacts → reload."""

    def test_lifecycle_metadata_persists_through_recording(self, tmp_path):
        """Simulate the full RecordingService lifecycle path."""
        from app.events.event_types import PitchStartEvent, PitchEndEvent, PitchAnalyzedEvent
        from unittest.mock import MagicMock

        session_id = "bullpen_am"
        pitch_id = "pitch_00001"

        # Build lifecycle metadata as RecordingService would accumulate it
        lifecycle = {}
        start_event = PitchStartEvent(
            pitch_id, 1, 1000,
            metadata=make_event_metadata(
                "PitchStartEvent", correlation_id=pitch_id,
                timestamp_ns=1000, pitch_id=pitch_id, session_id=session_id,
            ),
        )
        lifecycle["pitch_start"] = start_event.metadata.to_dict()

        end_event = PitchEndEvent(
            pitch_id, [], 2000, 1000,
            metadata=make_event_metadata(
                "PitchEndEvent", correlation_id=pitch_id,
                timestamp_ns=2000, pitch_id=pitch_id, session_id=session_id,
            ),
        )
        lifecycle["pitch_end"] = end_event.metadata.to_dict()

        analyzed_event = PitchAnalyzedEvent(
            pitch_id, MagicMock(), MagicMock(),
            metadata=make_event_metadata(
                "PitchAnalyzedEvent", correlation_id=pitch_id,
                timestamp_ns=2000, pitch_id=pitch_id, session_id=session_id,
            ),
        )
        lifecycle["pitch_analyzed"] = analyzed_event.metadata.to_dict()

        # Write manifest as PitchRecorder would
        manifest = create_pitch_manifest(
            _FakeSummary(pitch_id), "configs/default.yaml",
            event_metadata=lifecycle,
        )

        # Persist to disk
        session_dir = tmp_path / "session_recording"
        session_dir.mkdir()
        (session_dir / "manifest.json").write_text(json.dumps({
            "session_id": session_id,
            "session_left_video": "session_left.avi",
            "session_right_video": "session_right.avi",
            "event_metadata": {"session_id": session_id, "message_type": "session_lifecycle"},
        }))
        (session_dir / "session_left.avi").write_bytes(b"")
        (session_dir / "session_right.avi").write_bytes(b"")
        pitch_dir = session_dir / pitch_id
        pitch_dir.mkdir()
        (pitch_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        # Reload via SessionLoader
        loaded = SessionLoader.load_session(session_dir)

        # Verify session-level
        assert loaded.session_id == session_id
        assert loaded.manifest["event_metadata"]["session_id"] == session_id

        # Verify pitch lifecycle survived
        pitch = loaded.pitches[0]
        em = pitch.event_metadata
        assert em is not None
        assert "pitch_start" in em
        assert "pitch_end" in em
        assert "pitch_analyzed" in em

        # All phases share same correlation and session
        for phase in ("pitch_start", "pitch_end", "pitch_analyzed"):
            assert em[phase]["correlation_id"] == pitch_id
            assert em[phase]["session_id"] == session_id
            assert em[phase]["pitch_id"] == pitch_id

        # Timestamps are present and ordered
        assert em["pitch_start"]["timestamp_ns"] == 1000
        assert em["pitch_end"]["timestamp_ns"] == 2000

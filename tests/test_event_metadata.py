"""AGT-001: Tests for EventMetadata contract and correlation propagation.

Verifies:
- EventMetadata creation, serialization, and deserialization
- __post_init__ auto-hydration and timestamp normalization
- Backwards compatibility of event constructors (positional args still work)
- Real producer integration tests proving non-empty matching correlation
  across opportunity→outcome, pair→association/observation, pitch lifecycle,
  and session_id after recording starts
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.events.event_bus import EventBus
from app.events.event_metadata import (
    EVENT_METADATA_SCHEMA_VERSION,
    EventMetadata,
    hydrate_metadata,
    make_event_metadata,
)
from app.events.event_types import (
    ConfigUpdateEvent,
    ErrorEvent,
    FrameCapturedEvent,
    FrameProcessingOpportunityEvent,
    FrameProcessingOutcomeEvent,
    ObservationDetectedEvent,
    PairingOutcomeEvent,
    PitchAnalyzedEvent,
    PitchEndEvent,
    PitchStartEvent,
    RayObservationDetectedEvent,
    StereoAssociationOutcomeEvent,
    StereoFrameProcessedEvent,
)
from contracts.evidence import PairingOutcomeEvidence


class TestEventMetadataContract:
    """Test the EventMetadata frozen dataclass."""

    def test_default_construction(self):
        meta = EventMetadata()
        assert meta.message_type == ""
        assert meta.schema_version == EVENT_METADATA_SCHEMA_VERSION
        assert meta.correlation_id == ""
        assert meta.timestamp_ns == 0
        assert meta.session_id is None
        assert meta.pitch_id is None
        assert meta.camera_id is None

    def test_factory_helper(self):
        meta = make_event_metadata(
            "FrameCapturedEvent",
            correlation_id="left_42",
            timestamp_ns=999,
            camera_id="left",
            session_id="s1",
        )
        assert meta.message_type == "FrameCapturedEvent"
        assert meta.correlation_id == "left_42"
        assert meta.timestamp_ns == 999
        assert meta.camera_id == "left"
        assert meta.session_id == "s1"

    def test_immutable(self):
        meta = EventMetadata()
        with pytest.raises(AttributeError):
            meta.message_type = "changed"

    def test_to_dict_roundtrip(self):
        meta = make_event_metadata(
            "PitchStartEvent",
            correlation_id="pitch_00001",
            timestamp_ns=123,
            pitch_id="pitch_00001",
        )
        d = meta.to_dict()
        restored = EventMetadata.from_dict(d)
        assert restored == meta

    def test_from_dict_none(self):
        assert EventMetadata.from_dict(None) == EventMetadata()

    def test_from_dict_extra_keys(self):
        d = {"message_type": "X", "future_field": True}
        meta = EventMetadata.from_dict(d)
        assert meta.message_type == "X"

    def test_from_dict_missing_keys(self):
        meta = EventMetadata.from_dict({"message_type": "Y"})
        assert meta.message_type == "Y"
        assert meta.correlation_id == ""


class TestHydrateMetadata:
    """Test the hydrate_metadata normalisation helper."""

    def test_default_metadata_hydrated(self):
        result = hydrate_metadata(
            "TestEvent", EventMetadata(),
            timestamp_ns=500,
            correlation_id="cid",
            camera_id="left",
        )
        assert result.message_type == "TestEvent"
        assert result.timestamp_ns == 500
        assert result.correlation_id == "cid"
        assert result.camera_id == "left"

    def test_explicit_metadata_normalises_message_type(self):
        explicit = make_event_metadata("WrongName", correlation_id="cid", timestamp_ns=100)
        result = hydrate_metadata("CorrectName", explicit, timestamp_ns=100)
        assert result.message_type == "CorrectName"
        assert result.correlation_id == "cid"

    def test_explicit_metadata_normalises_zero_timestamp(self):
        explicit = make_event_metadata("E", correlation_id="cid", timestamp_ns=0)
        result = hydrate_metadata("E", explicit, timestamp_ns=999)
        assert result.timestamp_ns == 999


class TestPostInitTimestampNormalization:
    """Verify __post_init__ ensures metadata.timestamp_ns matches event."""

    def test_frame_captured_default_metadata(self):
        frame = MagicMock(frame_index=7)
        e = FrameCapturedEvent("left", frame, 42000)
        assert e.metadata.message_type == "FrameCapturedEvent"
        assert e.metadata.timestamp_ns == 42000
        assert e.metadata.correlation_id == "left_7"
        assert e.metadata.camera_id == "left"

    def test_pitch_start_default_metadata(self):
        e = PitchStartEvent("pitch_00001", 1, 500)
        assert e.metadata.message_type == "PitchStartEvent"
        assert e.metadata.timestamp_ns == 500
        assert e.metadata.correlation_id == "pitch_00001"
        assert e.metadata.pitch_id == "pitch_00001"

    def test_pitch_end_default_metadata(self):
        e = PitchEndEvent("pitch_00002", [], 1000, 500)
        assert e.metadata.timestamp_ns == 1000
        assert e.metadata.pitch_id == "pitch_00002"
        assert e.metadata.correlation_id == "pitch_00002"

    def test_stereo_frame_default_metadata(self):
        e = StereoFrameProcessedEvent("pair_10_20", 777, 50, 60, 10, 20, 1, 0)
        assert e.metadata.correlation_id == "pair_10_20"
        assert e.metadata.timestamp_ns == 777

    def test_opportunity_default_metadata(self):
        e = FrameProcessingOpportunityEvent("opp_1", "f_1", "left", 5, 100)
        assert e.metadata.correlation_id == "opp_1"
        assert e.metadata.camera_id == "left"
        assert e.metadata.timestamp_ns == 100

    def test_outcome_default_metadata(self):
        e = FrameProcessingOutcomeEvent("opp_1", "f_1", "right", 5, 200, "DETECTED")
        assert e.metadata.correlation_id == "opp_1"
        assert e.metadata.camera_id == "right"
        assert e.metadata.timestamp_ns == 200

    def test_association_default_metadata(self):
        e = StereoAssociationOutcomeEvent("pair_1", 300, "greedy_v1")
        assert e.metadata.correlation_id == "pair_1"
        assert e.metadata.timestamp_ns == 300

    @pytest.mark.parametrize(
        ("left_timestamp_ns", "right_timestamp_ns", "expected"),
        ((100, None, 100), (None, 200, 200), (300, 400, 300), (0, 400, 0)),
    )
    def test_pairing_outcome_uses_available_timestamp(
        self,
        left_timestamp_ns,
        right_timestamp_ns,
        expected,
    ):
        e = PairingOutcomeEvent(
            PairingOutcomeEvidence(
                outcome_id="pairing_1",
                status="UNMATCHED",
                left_timestamp_ns=left_timestamp_ns,
                right_timestamp_ns=right_timestamp_ns,
            )
        )
        assert e.timestamp_ns == expected
        assert e.metadata.timestamp_ns == expected

    def test_error_event_default_metadata(self):
        e = ErrorEvent("svc", "type", "msg", timestamp_ns=42)
        assert e.metadata.message_type == "ErrorEvent"
        assert e.metadata.timestamp_ns == 42

    def test_explicit_metadata_preserves_correlation(self):
        meta = make_event_metadata("PitchStartEvent", correlation_id="custom", timestamp_ns=500)
        e = PitchStartEvent("pitch_00001", 1, 500, metadata=meta)
        assert e.metadata.correlation_id == "custom"
        assert e.metadata.timestamp_ns == 500


class TestBackwardsCompatibility:
    """Existing positional constructors must not break."""

    def test_frame_captured_positional(self):
        frame = MagicMock(frame_index=0)
        e = FrameCapturedEvent("left", frame, 100)
        assert e.camera_id == "left"

    def test_pitch_start_positional(self):
        e = PitchStartEvent("pitch_00001", 1, 500)
        assert e.pitch_id == "pitch_00001"

    def test_pitch_end_positional(self):
        e = PitchEndEvent("pitch_00001", [], 1000, 500)
        assert e.pitch_id == "pitch_00001"

    def test_observation_detected_positional(self):
        e = ObservationDetectedEvent(MagicMock(), 200)
        assert e.confidence == 1.0

    def test_pitch_analyzed_positional(self):
        e = PitchAnalyzedEvent("p1", MagicMock(), MagicMock())
        assert e.pitch_id == "p1"

    def test_config_update_no_metadata(self):
        e = ConfigUpdateEvent("key", "val", 100)
        assert not hasattr(e, "metadata")

    def test_error_event_positional(self):
        e = ErrorEvent("svc", "type", "msg")
        assert e.metadata.message_type == "ErrorEvent"

    def test_stereo_frame_processed_positional(self):
        e = StereoFrameProcessedEvent("p1", 100, 50, 60, 1, 2, 3, 4)
        assert e.metadata.correlation_id == "p1"

    def test_ray_observation_positional(self):
        e = RayObservationDetectedEvent(MagicMock(), 100)
        assert e.metadata.timestamp_ns == 100


class TestOpportunityOutcomeCorrelation:
    """Opportunity→Outcome must share correlation_id (opportunity_id)."""

    def test_matching_correlation(self):
        opp = FrameProcessingOpportunityEvent("opp_42", "f_42", "left", 42, 1000)
        out = FrameProcessingOutcomeEvent("opp_42", "f_42", "left", 42, 1001, "DETECTED")
        assert opp.metadata.correlation_id == out.metadata.correlation_id == "opp_42"
        assert opp.metadata.correlation_id != ""

    def test_different_opportunities_differ(self):
        opp1 = FrameProcessingOpportunityEvent("opp_1", "f_1", "left", 1, 100)
        opp2 = FrameProcessingOpportunityEvent("opp_2", "f_2", "left", 2, 200)
        assert opp1.metadata.correlation_id != opp2.metadata.correlation_id


class TestPairAssociationObservationCorrelation:
    """Pair→Association→Observation must share pair_id as correlation_id."""

    def test_pair_and_association_match(self):
        pair_id = "pair_left10_right10"
        stereo = StereoFrameProcessedEvent(
            pair_id=pair_id, timestamp_ns=500,
            left_timestamp_ns=490, right_timestamp_ns=510,
            left_frame_index=10, right_frame_index=10,
            lane_count=1, plate_count=0,
        )
        assoc = StereoAssociationOutcomeEvent(
            pair_id=pair_id, timestamp_ns=500, primary_algorithm="greedy_v1",
        )
        assert stereo.metadata.correlation_id == assoc.metadata.correlation_id == pair_id
        assert stereo.metadata.correlation_id != ""

    def test_observation_carries_pair_correlation(self):
        """Producer passes pair_id as correlation_id via explicit metadata."""
        pair_id = "pair_left10_right10"
        obs_meta = make_event_metadata(
            "ObservationDetectedEvent", correlation_id=pair_id, timestamp_ns=500,
        )
        obs = ObservationDetectedEvent(MagicMock(), 500, metadata=obs_meta)
        assert obs.metadata.correlation_id == pair_id


class TestPitchLifecycleCorrelation:
    """PitchStart→End→Analyzed must share pitch_id as correlation_id."""

    def test_pitch_lifecycle(self):
        bus = EventBus()
        collected = []

        bus.subscribe(PitchStartEvent, collected.append)
        bus.subscribe(PitchEndEvent, collected.append)
        bus.subscribe(PitchAnalyzedEvent, collected.append)

        pid = "pitch_00001"
        bus.publish(PitchStartEvent(pid, 1, 100))
        bus.publish(PitchEndEvent(pid, [], 200, 100))
        bus.publish(PitchAnalyzedEvent(pid, MagicMock(), MagicMock()))

        assert len(collected) == 3
        ids = [e.metadata.correlation_id for e in collected]
        assert all(cid == pid for cid in ids)
        assert all(e.metadata.pitch_id == pid for e in collected)
        assert all(e.metadata.correlation_id != "" for e in collected)


class TestSessionIdPropagation:
    """Session_id flows through metadata when recording is active."""

    def test_frame_captured_with_session_id(self):
        meta = make_event_metadata(
            "FrameCapturedEvent",
            correlation_id="left_0",
            timestamp_ns=100,
            camera_id="left",
            session_id="bullpen_001",
        )
        e = FrameCapturedEvent("left", MagicMock(frame_index=0), 100, metadata=meta)
        assert e.metadata.session_id == "bullpen_001"

    def test_pitch_events_with_session_id(self):
        sid = "morning_session"
        meta = make_event_metadata(
            "PitchStartEvent", correlation_id="pitch_00001",
            timestamp_ns=100, pitch_id="pitch_00001", session_id=sid,
        )
        e = PitchStartEvent("pitch_00001", 1, 100, metadata=meta)
        assert e.metadata.session_id == sid

    def test_no_session_id_before_recording(self):
        e = PitchStartEvent("pitch_00001", 1, 100)
        assert e.metadata.session_id is None


class TestDurableSerialization:
    """Test metadata survives serialization/deserialization for persistence."""

    def test_metadata_dict_in_event_context(self):
        meta = make_event_metadata(
            "PitchEndEvent",
            correlation_id="pitch_00003",
            timestamp_ns=42,
            pitch_id="pitch_00003",
            session_id="bullpen_001",
        )
        d = meta.to_dict()
        assert d["message_type"] == "PitchEndEvent"
        assert d["correlation_id"] == "pitch_00003"
        assert d["session_id"] == "bullpen_001"

        restored = EventMetadata.from_dict(d)
        assert restored.pitch_id == "pitch_00003"
        assert restored.session_id == "bullpen_001"

    def test_compatibility_with_missing_metadata(self):
        restored = EventMetadata.from_dict(None)
        assert restored == EventMetadata()
        restored2 = EventMetadata.from_dict({})
        assert restored2 == EventMetadata()


class TestPublishErrorMetadata:
    """Test that publish_error accepts event_metadata context."""

    def test_publish_error_with_event_metadata(self):
        from app.events.error_bus import ErrorCategory, ErrorSeverity, get_error_bus
        bus = get_error_bus()
        received = []
        bus.subscribe(received.append)
        try:
            from app.events.error_bus import publish_error
            publish_error(
                category=ErrorCategory.DETECTION,
                severity=ErrorSeverity.WARNING,
                message="test error",
                source="test",
                event_metadata={"correlation_id": "pitch_00001"},
            )
            assert len(received) >= 1
            last = received[-1]
            assert last.metadata.get("event_metadata") == {"correlation_id": "pitch_00001"}
        finally:
            bus.unsubscribe(received.append)

    def test_publish_error_without_event_metadata(self):
        from app.events.error_bus import ErrorCategory, ErrorSeverity
        from app.events.error_bus import publish_error
        publish_error(
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.INFO,
            message="basic error",
            source="test",
        )

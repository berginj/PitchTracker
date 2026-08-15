"""Characterization tests for evidence_assembly module and callback failure handling."""

from __future__ import annotations

from unittest.mock import MagicMock

from contracts.evidence import PairingOutcomeEvidence

from app.events.event_types import StereoAssociationOutcomeEvent
from app.pipeline.detection.evidence_assembly import (
    build_skew_rejection_event,
    emit_association_outcome,
    emit_pairing_outcomes,
)


class TestEmitPairingOutcomes:
    """Verify pairing outcome emission and callback failure resilience."""

    def test_emits_all_outcomes(self):
        outcomes = (
            PairingOutcomeEvidence(outcome_id="p1", status="PAIRED"),
            PairingOutcomeEvidence(outcome_id="p2", status="UNMATCHED"),
        )
        callback = MagicMock()
        emit_pairing_outcomes(outcomes, callback)
        assert callback.call_count == 2

    def test_none_callback_no_error(self):
        outcomes = (PairingOutcomeEvidence(outcome_id="p1", status="PAIRED"),)
        emit_pairing_outcomes(outcomes, None)

    def test_callback_failure_does_not_raise(self):
        outcomes = (
            PairingOutcomeEvidence(outcome_id="p1", status="PAIRED"),
            PairingOutcomeEvidence(outcome_id="p2", status="PAIRED"),
        )
        callback = MagicMock(side_effect=RuntimeError("boom"))
        emit_pairing_outcomes(outcomes, callback)
        assert callback.call_count == 2


class TestEmitAssociationOutcome:
    """Verify association outcome emission and callback failure resilience."""

    def test_callback_invoked(self):
        event = StereoAssociationOutcomeEvent(
            pair_id="pair:abc",
            timestamp_ns=1_000_000,
            primary_algorithm="greedy_v1",
        )
        callback = MagicMock()
        emit_association_outcome(event, callback)
        callback.assert_called_once_with(event)

    def test_none_callback_no_error(self):
        event = StereoAssociationOutcomeEvent(
            pair_id="pair:abc",
            timestamp_ns=1_000_000,
            primary_algorithm="greedy_v1",
        )
        emit_association_outcome(event, None)

    def test_callback_failure_does_not_raise(self):
        event = StereoAssociationOutcomeEvent(
            pair_id="pair:abc",
            timestamp_ns=1_000_000,
            primary_algorithm="greedy_v1",
        )
        callback = MagicMock(side_effect=RuntimeError("callback crash"))
        emit_association_outcome(event, callback)


class TestBuildSkewRejectionEvent:
    """Verify skew rejection event has correct rejection reason."""

    def test_skew_rejection_has_reason(self):
        event = build_skew_rejection_event("pair:xyz", 5_000_000)
        assert "PAIR_SKEW_OUT_OF_TOLERANCE" in event.rejection_reasons
        assert event.pair_id == "pair:xyz"
        assert event.timestamp_ns == 5_000_000

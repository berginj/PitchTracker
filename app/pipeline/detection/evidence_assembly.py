"""Evidence event building and callback emission."""

from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple

from contracts.evidence import PairingOutcomeEvidence
from stereo.association import PairTiming

from app.events.event_types import StereoAssociationOutcomeEvent
from app.pipeline.detection.association_graph import AssociationResult

logger = logging.getLogger(__name__)


def emit_pairing_outcomes(
    outcomes: Tuple[PairingOutcomeEvidence, ...],
    callback: Optional[Callable[[PairingOutcomeEvidence], None]],
) -> None:
    """Emit pairing outcome evidence to the registered callback."""
    if callback is None:
        return
    for outcome in outcomes:
        try:
            callback(outcome)
        except Exception:
            logger.exception("Pairing outcome callback failed for %s", outcome.outcome_id)


def build_association_outcome_event(
    result: AssociationResult,
    timing: PairTiming,
) -> StereoAssociationOutcomeEvent:
    """Construct the association outcome event from an AssociationResult."""
    observations = result.triangulation.observations
    return StereoAssociationOutcomeEvent(
        pair_id=result.pair_id,
        timestamp_ns=timing.timestamp_ns,
        primary_algorithm=result.assignment.primary_algorithm,
        edges=result.association_edges,
        assigned_edge_ids=tuple(sorted(set(result.triangulation.final_edge_ids))),
        shadow_assigned_edge_ids=result.assignment.shadow_assigned_edge_ids,
        unmatched_candidate_ids=tuple(
            sorted(result.all_candidate_ids - result.assigned_candidate_ids)
        ),
        triangulations=tuple(result.triangulation.evidence),
        rejection_reasons=() if observations else ("NO_VALID_STEREO_ASSOCIATION",),
    )


def build_skew_rejection_event(
    pair_id: str,
    timestamp_ns: int,
) -> StereoAssociationOutcomeEvent:
    """Build an association outcome for pairs rejected due to skew."""
    return StereoAssociationOutcomeEvent(
        pair_id=pair_id,
        timestamp_ns=timestamp_ns,
        primary_algorithm="greedy_v1",
        rejection_reasons=("PAIR_SKEW_OUT_OF_TOLERANCE",),
    )


def emit_association_outcome(
    event: StereoAssociationOutcomeEvent,
    callback: Optional[Callable[[StereoAssociationOutcomeEvent], None]],
) -> None:
    """Emit a stereo association outcome event to the registered callback."""
    if callback is None:
        return
    try:
        callback(event)
    except Exception:
        logger.exception("Association outcome callback failed for %s", event.pair_id)

"""Stereo triangulation loop and evidence assembly."""

from __future__ import annotations

import logging
from dataclasses import replace
from contracts import StereoObservation
from contracts.evidence import TriangulationDecisionEvidence
from stereo import StereoMatcher

from app.pipeline.detection.decision_ids import (
    association_edge_id,
    detection_decision_id,
    observation_decision_id,
)

logger = logging.getLogger(__name__)


class TriangulationResult:
    """Result of triangulating a set of stereo matches."""

    __slots__ = ("observations", "evidence", "final_edge_ids")

    def __init__(
        self,
        observations: list[StereoObservation],
        evidence: list[TriangulationDecisionEvidence],
        final_edge_ids: list[str],
    ):
        self.observations = observations
        self.evidence = evidence
        self.final_edge_ids = final_edge_ids


def triangulate_matches(
    pair_id: str,
    matches: list,
    stereo_matcher: StereoMatcher,
) -> TriangulationResult:
    """Triangulate a list of stereo matches and produce evidence records.

    Args:
        pair_id: Deterministic stereo pair ID.
        matches: StereoMatch objects to triangulate.
        stereo_matcher: Matcher providing triangulate().

    Returns:
        TriangulationResult with observations, evidence, and edge IDs.
    """
    observations: list[StereoObservation] = []
    evidence: list[TriangulationDecisionEvidence] = []
    final_edge_ids: list[str] = []

    for match in matches:
        edge_id = association_edge_id(
            pair_id,
            detection_decision_id(match.left),
            detection_decision_id(match.right),
        )
        final_edge_ids.append(edge_id)
        obs_id = observation_decision_id(edge_id)

        try:
            raw_observation = stereo_matcher.triangulate(match)
        except Exception as exc:
            evidence.append(
                TriangulationDecisionEvidence(
                    observation_id=obs_id,
                    edge_id=edge_id,
                    status="FAILED",
                    diagnostics={"exception_type": exc.__class__.__name__},
                    rejection_reasons=("TRIANGULATION_EXCEPTION",),
                )
            )
            logger.exception("Triangulation failed for %s", edge_id)
            continue

        observation = replace(
            raw_observation,
            observation_id=obs_id,
            match_id=edge_id,
        )
        observations.append(observation)

        depth_sigma = None
        if observation.covariance is not None:
            depth_sigma = max(0.0, float(observation.covariance[2][2])) ** 0.5
        accepted = observation.quality > 0.0
        evidence.append(
            TriangulationDecisionEvidence(
                observation_id=obs_id,
                edge_id=edge_id,
                status="ACCEPTED" if accepted else "REJECTED",
                xyz_ft=(observation.X, observation.Y, observation.Z),
                covariance=observation.covariance,
                quality=observation.quality,
                confidence=observation.confidence,
                depth_sigma_ft=depth_sigma,
                rejection_reasons=() if accepted else ("TRIANGULATION_QUALITY_ZERO",),
            )
        )

    return TriangulationResult(observations, evidence, final_edge_ids)

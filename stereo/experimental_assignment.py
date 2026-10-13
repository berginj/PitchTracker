"""Experimental global assignment with uncertainty and explicit ambiguity."""

from __future__ import annotations
from dataclasses import replace
from typing import Any, TYPE_CHECKING
import numpy as np
from contracts.evidence import AssociationEdgeEvidence
from app.pipeline.detection.decision_ids import association_edge_id, detection_decision_id
from stereo.association import StereoMatch

if TYPE_CHECKING:
    from stereo.global_assignment import StereoAssignmentDecision


def motion_cost(detection):
    if detection.prediction_center_px is None or detection.prediction_covariance_px2 is None:
        return 0.0
    residual = np.array([detection.u, detection.v]) - detection.prediction_center_px
    covariance = np.array(detection.prediction_covariance_px2) + np.array(detection.pixel_covariance_px2)
    return float(residual @ np.linalg.solve(covariance, residual))


def evaluate(pair_id, left, right, matcher) -> StereoAssignmentDecision:
    from stereo.global_assignment import StereoAssignmentDecision, _global_edge_ids

    edges: list[AssociationEdgeEvidence] = []
    matches: dict[str, StereoMatch] = {}
    for ldet in sorted(left, key=detection_decision_id):
        for rdet in sorted(right, key=detection_decision_id):
            edge_id = association_edge_id(pair_id, detection_decision_id(ldet), detection_decision_id(rdet))
            match = matcher.match(ldet, rdet) if matcher is not None else None
            diagnostic: dict[str, Any] = {"valid": False, "reason": "EPIPOLAR_GATE_FAILED"}
            if match is not None:
                method = getattr(matcher, "geometric_diagnostics", None)
                diagnostic = method(match) if method else {"valid": False, "reason": "CALIBRATED_GEOMETRY_REQUIRED"}
            terms = {}
            if diagnostic["valid"]:
                terms = {
                    "epipolar": diagnostic["epipolar_normalized"] ** 2 / 9,
                    "reprojection": diagnostic["reprojection_q"] / 36,
                    "motion": (motion_cost(ldet) + motion_cost(rdet)) / 18,
                }
                if terms["motion"] > 1:
                    diagnostic.update(valid=False, reason="MOTION_GATE_FAILED")
            valid = diagnostic["valid"]
            edge = AssociationEdgeEvidence(
                edge_id,
                detection_decision_id(ldet),
                detection_decision_id(rdet),
                valid,
                "VALID_UNASSIGNED" if valid else "REJECTED",
                int(round(sum(terms.values()) / max(1, len(terms)) * 1_000_000)) if valid else 1_000_000_000,
                match.epipolar_error_px if match else None,
                match.score if match else 0.0,
                cost_components=terms,
                gate_results={"geometry": valid},
                rejection_reasons=() if valid else (diagnostic["reason"],),
            )
            edges.append(edge)
            if valid and match is not None:
                matches[edge_id] = match
    selected = _global_edge_ids(left, right, edges)
    total = sum(e.total_cost_units for e in edges if e.edge_id in selected)
    ambiguous = set()
    for chosen in selected:
        alternative_edges = [replace(e, valid=False) if e.edge_id == chosen else e for e in edges]
        alternative = _global_edge_ids(left, right, alternative_edges)
        # Fewer matches is not an equal-coverage ambiguity alternative.
        if len(alternative) != len(selected):
            continue
        alternative_cost = sum(e.total_cost_units for e in edges if e.edge_id in alternative)
        if alternative_cost - total <= max(1, 0.1 * max(1, total)):
            ambiguous.update(set(selected) - set(alternative))
    final = tuple(edge_id for edge_id in selected if edge_id not in ambiguous)
    edges = [
        replace(
            e,
            decision="ASSIGNED" if e.edge_id in final else "AMBIGUOUS" if e.edge_id in ambiguous else e.decision,
            rejection_reasons=("AMBIGUOUS_ASSIGNMENT",) if e.edge_id in ambiguous else e.rejection_reasons,
        )
        for e in edges
    ]
    assigned = {c for e in edges if e.edge_id in final for c in (e.left_candidate_id, e.right_candidate_id)}
    return StereoAssignmentDecision(
        "global_v3",
        tuple(matches[e] for e in final),
        tuple(edges),
        final,
        (),
        tuple(sorted({detection_decision_id(d) for d in (*left, *right)} - assigned)),
    )

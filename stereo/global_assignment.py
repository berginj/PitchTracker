"""Auditable stereo edge evaluation and deterministic global assignment."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Optional

import numpy as np

from app.pipeline.detection.decision_ids import association_edge_id, detection_decision_id
from contracts import Detection
from contracts.evidence import AssociationEdgeEvidence
from stereo.association import StereoMatch, StereoMatcher

try:
    from scipy.optimize import linear_sum_assignment
except Exception:  # pragma: no cover - production global mode fails closed
    linear_sum_assignment = None


@dataclass(frozen=True)
class StereoAssignmentDecision:
    primary_algorithm: str
    primary_matches: tuple[StereoMatch, ...]
    edges: tuple[AssociationEdgeEvidence, ...]
    assigned_edge_ids: tuple[str, ...]
    shadow_assigned_edge_ids: tuple[str, ...]
    unmatched_candidate_ids: tuple[str, ...]


def evaluate_stereo_assignment(
    pair_id: str,
    left_detections: Iterable[Detection],
    right_detections: Iterable[Detection],
    *,
    epipolar_tolerance: float,
    matcher: Optional[StereoMatcher],
    mode: str = "greedy_v1",
) -> StereoAssignmentDecision:
    """Evaluate every edge and select primary/shadow one-to-one assignments."""

    left_original = list(left_detections)
    right_original = list(right_detections)
    left = sorted(left_original, key=detection_decision_id)
    right = sorted(right_original, key=detection_decision_id)
    match_by_edge: dict[str, StereoMatch] = {}
    raw_edges: list[AssociationEdgeEvidence] = []
    for left_candidate in left:
        for right_candidate in right:
            left_id = detection_decision_id(left_candidate)
            right_id = detection_decision_id(right_candidate)
            edge_id = association_edge_id(pair_id, left_id, right_id)
            match = _evaluate_match(left_candidate, right_candidate, epipolar_tolerance, matcher)
            if match is None:
                raw_edges.append(
                    AssociationEdgeEvidence(
                        edge_id=edge_id,
                        left_candidate_id=left_id,
                        right_candidate_id=right_id,
                        valid=False,
                        decision="REJECTED",
                        total_cost_units=1_000_000_000,
                        epipolar_error_px=None,
                        score=0.0,
                        gate_results={"epipolar": False},
                        rejection_reasons=("EPIPOLAR_GATE_FAILED",),
                    )
                )
                continue
            epipolar_component = min(1.0, max(0.0, match.epipolar_error_px / max(epipolar_tolerance, 1e-9)))
            confidence_component = 1.0 - min(1.0, max(0.0, match.score))
            total_cost_units = int(round((0.7 * epipolar_component + 0.3 * confidence_component) * 1_000_000))
            raw_edges.append(
                AssociationEdgeEvidence(
                    edge_id=edge_id,
                    left_candidate_id=left_id,
                    right_candidate_id=right_id,
                    valid=True,
                    decision="VALID_UNASSIGNED",
                    total_cost_units=total_cost_units,
                    epipolar_error_px=float(match.epipolar_error_px),
                    score=float(match.score),
                    cost_components={
                        "epipolar": epipolar_component,
                        "confidence_penalty": confidence_component,
                    },
                    gate_results={"epipolar": True},
                )
            )
            match_by_edge[edge_id] = match

    greedy_ids, greedy_matches = _greedy_assignment(
        pair_id,
        left_original,
        right_original,
        match_by_edge,
    )
    normalized_mode = str(mode or "greedy_v1").lower()
    global_ids = (
        _global_edge_ids(left, right, raw_edges)
        if normalized_mode in {"global_v2", "shadow", "shadow_v2", "global_shadow"}
        else ()
    )
    global_matches = tuple(match_by_edge[edge_id] for edge_id in global_ids)

    if normalized_mode == "global_v2":
        if linear_sum_assignment is None:
            raise RuntimeError("global_v2 stereo assignment requires scipy")
        primary_algorithm = "global_v2"
        primary_matches = global_matches
        primary_ids = global_ids
        shadow_ids: tuple[str, ...] = greedy_ids
    else:
        primary_algorithm = "greedy_v1"
        primary_matches = greedy_matches
        primary_ids = greedy_ids
        shadow_ids = global_ids if normalized_mode in {"shadow", "shadow_v2", "global_shadow"} else ()

    primary_id_set = set(primary_ids)
    edges = tuple(
        replace(edge, decision="ASSIGNED" if edge.edge_id in primary_id_set else edge.decision)
        for edge in raw_edges
    )
    assigned_candidates = {
        candidate_id
        for edge in edges
        if edge.edge_id in primary_id_set
        for candidate_id in (edge.left_candidate_id, edge.right_candidate_id)
    }
    all_candidates = {detection_decision_id(item) for item in (*left, *right)}
    return StereoAssignmentDecision(
        primary_algorithm=primary_algorithm,
        primary_matches=primary_matches,
        edges=edges,
        assigned_edge_ids=primary_ids,
        shadow_assigned_edge_ids=shadow_ids,
        unmatched_candidate_ids=tuple(sorted(all_candidates - assigned_candidates)),
    )


def _evaluate_match(
    left: Detection,
    right: Detection,
    tolerance: float,
    matcher: Optional[StereoMatcher],
) -> Optional[StereoMatch]:
    if matcher is not None:
        return matcher.match(left, right)
    error = abs(float(left.v) - float(right.v))
    if error > tolerance:
        return None
    return StereoMatch(left, right, error, min(float(left.confidence), float(right.confidence)))


def _greedy_assignment(
    pair_id: str,
    left: list[Detection],
    right: list[Detection],
    match_by_edge: dict[str, StereoMatch],
) -> tuple[tuple[str, ...], tuple[StereoMatch, ...]]:
    candidates: list[tuple[float, float, int, int, str, StereoMatch]] = []
    for left_index, left_candidate in enumerate(left):
        for right_index, right_candidate in enumerate(right):
            edge_id = association_edge_id(
                pair_id,
                detection_decision_id(left_candidate),
                detection_decision_id(right_candidate),
            )
            match = match_by_edge.get(edge_id)
            if match is not None:
                candidates.append(
                    (
                        float(match.epipolar_error_px),
                        -float(match.score),
                        left_index,
                        right_index,
                        edge_id,
                        match,
                    )
                )
    used_left: set[int] = set()
    used_right: set[int] = set()
    selected_ids: list[str] = []
    selected_matches: list[StereoMatch] = []
    for _, _, left_index, right_index, edge_id, match in sorted(candidates, key=lambda item: item[:4]):
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        selected_ids.append(edge_id)
        selected_matches.append(match)
    return tuple(selected_ids), tuple(selected_matches)


def _global_edge_ids(
    left: list[Detection],
    right: list[Detection],
    edges: list[AssociationEdgeEvidence],
) -> tuple[str, ...]:
    if not left or not right:
        return ()
    if linear_sum_assignment is None:
        return ()
    n_left = len(left)
    n_right = len(right)
    size = n_left + n_right
    invalid = 10**15
    unmatched = 1_000_001
    tie_scale = size**3 + 1
    matrix = np.full((size, size), float(invalid * tie_scale), dtype=np.float64)
    edge_by_candidates = {(edge.left_candidate_id, edge.right_candidate_id): edge for edge in edges}
    for row, left_candidate in enumerate(left):
        for col, right_candidate in enumerate(right):
            edge = edge_by_candidates[(detection_decision_id(left_candidate), detection_decision_id(right_candidate))]
            if edge.valid:
                tie_rank = row * max(1, n_right) + col
                matrix[row, col] = float(edge.total_cost_units * tie_scale + tie_rank)
        matrix[row, n_right + row] = float(unmatched * tie_scale)
    for right_index in range(n_right):
        matrix[n_left + right_index, right_index] = float(unmatched * tie_scale)
        matrix[n_left + right_index, n_right:] = 0.0
    rows, cols = linear_sum_assignment(matrix)
    selected: list[str] = []
    for row, col in zip(rows, cols):
        if row >= n_left or col >= n_right:
            continue
        edge = edge_by_candidates[(detection_decision_id(left[row]), detection_decision_id(right[col]))]
        if edge.valid:
            selected.append(edge.edge_id)
    return tuple(sorted(selected))


def _edge_id_for_match(pair_id: str, match: StereoMatch) -> str:
    return association_edge_id(pair_id, detection_decision_id(match.left), detection_decision_id(match.right))


__all__ = ["StereoAssignmentDecision", "evaluate_stereo_assignment"]

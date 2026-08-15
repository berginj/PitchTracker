"""Association graph decisions and stereo gate filtering."""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from configs.settings import AppConfig
from contracts import Detection, Frame
from stereo import StereoLaneGate, StereoMatcher
from stereo.global_assignment import StereoAssignmentDecision, evaluate_stereo_assignment

from app.pipeline.detection.decision_ids import detection_decision_id, stereo_pair_id
from app.pipeline.detection.triangulation import TriangulationResult, triangulate_matches


class AssociationResult:
    """Result of the full stereo association + triangulation pipeline step."""

    __slots__ = (
        "pair_id",
        "assignment",
        "filtered_matches",
        "triangulation",
        "association_edges",
        "assigned_candidate_ids",
        "all_candidate_ids",
    )

    def __init__(
        self,
        pair_id: str,
        assignment: StereoAssignmentDecision,
        filtered_matches: list,
        triangulation: TriangulationResult,
        association_edges: tuple,
        assigned_candidate_ids: set,
        all_candidate_ids: set,
    ):
        self.pair_id = pair_id
        self.assignment = assignment
        self.filtered_matches = filtered_matches
        self.triangulation = triangulation
        self.association_edges = association_edges
        self.assigned_candidate_ids = assigned_candidate_ids
        self.all_candidate_ids = all_candidate_ids


def run_association(
    left_frame: Frame,
    right_frame: Frame,
    left_gated: list[Detection],
    right_gated: list[Detection],
    config: Optional[AppConfig],
    stereo_matcher: StereoMatcher,
    stereo_gate: Optional[StereoLaneGate],
) -> AssociationResult:
    """Run full stereo association, gate filtering, and triangulation.

    Returns:
        AssociationResult with all decision evidence needed by the event emitter.
    """
    epipolar_tolerance = 10.0
    if config is not None:
        epipolar_tolerance = float(config.stereo.epipolar_epsilon_px)

    pair_id = stereo_pair_id(left_frame, right_frame)
    association_mode = "greedy_v1"
    if config is not None:
        association_mode = str(getattr(config.stereo, "association_mode", "greedy_v1"))

    assignment = evaluate_stereo_assignment(
        pair_id,
        left_gated,
        right_gated,
        epipolar_tolerance=epipolar_tolerance,
        matcher=stereo_matcher,
        mode=association_mode,
    )

    matches = list(assignment.primary_matches)
    if stereo_gate is not None:
        matches = stereo_gate.filter_matches(matches)

    triangulation = triangulate_matches(pair_id, matches, stereo_matcher)

    final_assigned = set(triangulation.final_edge_ids)
    association_edges = tuple(
        replace(
            edge,
            decision=(
                "ASSIGNED"
                if edge.edge_id in final_assigned
                else "VALID_UNASSIGNED"
                if edge.valid
                else "REJECTED"
            ),
        )
        for edge in assignment.edges
    )
    assigned_candidate_ids = {
        candidate_id
        for edge in association_edges
        if edge.edge_id in final_assigned
        for candidate_id in (edge.left_candidate_id, edge.right_candidate_id)
    }
    all_candidate_ids = {
        detection_decision_id(d) for d in (*left_gated, *right_gated)
    }

    return AssociationResult(
        pair_id=pair_id,
        assignment=assignment,
        filtered_matches=matches,
        triangulation=triangulation,
        association_edges=association_edges,
        assigned_candidate_ids=assigned_candidate_ids,
        all_candidate_ids=all_candidate_ids,
    )

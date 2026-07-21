"""Verify frame conservation and deterministic assignment from a decision journal."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

try:
    from scipy.optimize import linear_sum_assignment
except Exception:  # pragma: no cover
    linear_sum_assignment = None


@dataclass(frozen=True)
class DecisionReplayReport:
    valid: bool
    digest: str
    errors: tuple[str, ...]
    metrics: dict[str, Any]


def reconcile_decision_journal(
    records: Iterable[dict[str, Any]],
    *,
    expected_bindings: dict[str, str] | None = None,
) -> DecisionReplayReport:
    records = list(records)
    opportunities: dict[str, dict[str, Any]] = {}
    outcomes: dict[str, dict[str, Any]] = {}
    pairing_by_frame: dict[str, dict[str, Any]] = {}
    terminal_counts: Counter[str] = Counter()
    unmatched_counts: Counter[str] = Counter()
    errors: list[str] = []
    artifact_values: dict[str, set[str]] = {
        key: set()
        for key in (
            "config_sha256",
            "calibration_sha256",
            "roi_sha256",
            "detector_name",
            "detector_version",
            "model_sha256",
        )
    }

    for record in records:
        stream = str(record.get("stream"))
        payload = dict(record.get("payload") or {})
        bindings = dict(payload.get("bindings") or {})
        for key in artifact_values:
            if bindings.get(key) is not None:
                artifact_values[key].add(str(bindings[key]))
        for key, expected in (expected_bindings or {}).items():
            if bindings.get(key) is not None and str(bindings[key]) != str(expected):
                errors.append(f"artifact binding mismatch for {key}")
        if stream == "FrameProcessingOpportunityEvent":
            opportunity_id = str(payload.get("opportunity_id"))
            if opportunity_id in opportunities:
                errors.append(f"duplicate opportunity: {opportunity_id}")
            opportunities[opportunity_id] = payload
        elif stream == "FrameProcessingOutcomeEvent":
            opportunity_id = str(payload.get("opportunity_id"))
            if opportunity_id in outcomes:
                errors.append(f"duplicate terminal outcome: {opportunity_id}")
            outcomes[opportunity_id] = payload
            terminal_counts[str(payload.get("status"))] += 1
        elif stream == "PairingOutcomeEvent":
            outcome = dict(payload.get("outcome") or {})
            frame_ids = [outcome.get("left_frame_id"), outcome.get("right_frame_id")]
            for frame_id in (str(item) for item in frame_ids if item):
                if frame_id in pairing_by_frame:
                    errors.append(f"duplicate pairing terminal outcome: {frame_id}")
                pairing_by_frame[frame_id] = outcome
            if outcome.get("status") == "UNMATCHED":
                reasons = list(outcome.get("reason_codes") or ["UNSPECIFIED"])
                unmatched_counts[str(reasons[0])] += len([item for item in frame_ids if item])
        elif stream == "StereoAssociationOutcomeEvent":
            errors.extend(_verify_association(payload))

    missing_terminal = sorted(set(opportunities) - set(outcomes))
    orphan_terminal = sorted(set(outcomes) - set(opportunities))
    if missing_terminal:
        errors.append(f"missing terminal outcomes: {missing_terminal}")
    if orphan_terminal:
        errors.append(f"orphan terminal outcomes: {orphan_terminal}")
    for key, values in artifact_values.items():
        if len(values) > 1:
            errors.append(f"inconsistent artifact binding for {key}: {sorted(values)}")
    if expected_bindings:
        for key in expected_bindings:
            if key in artifact_values and not artifact_values[key]:
                errors.append(f"required artifact binding missing: {key}")

    completed_frame_ids = {
        str(payload.get("frame_id"))
        for payload in outcomes.values()
        if payload.get("status") == "PROCESSING_COMPLETE"
    }
    missing_pairing = sorted(completed_frame_ids - set(pairing_by_frame))
    orphan_pairing = sorted(set(pairing_by_frame) - completed_frame_ids)
    if missing_pairing:
        errors.append(f"missing pairing outcomes: {missing_pairing}")
    if orphan_pairing:
        errors.append(f"orphan pairing outcomes: {orphan_pairing}")

    offered = len(opportunities)
    terminal = len(outcomes)
    pairing_denominator = len(pairing_by_frame)
    total_unmatched = sum(unmatched_counts.values())
    metrics = {
        "frame_conservation": {
            "offered": offered,
            "terminal": terminal,
            "missing": len(missing_terminal),
            "orphan": len(orphan_terminal),
            "balanced": not missing_terminal and not orphan_terminal,
            "terminal_outcomes": dict(sorted(terminal_counts.items())),
        },
        "pairing": {
            "denominator_frames": pairing_denominator,
            "unmatched": total_unmatched,
            "unmatched_rate": _rate(total_unmatched, pairing_denominator),
            "unmatched_counts": dict(sorted(unmatched_counts.items())),
        },
    }
    digest_payload = [
        {"stream": record.get("stream"), "payload": record.get("payload")}
        for record in records
        if record.get("stream")
        in {
            "FrameProcessingOpportunityEvent",
            "FrameProcessingOutcomeEvent",
            "PairingOutcomeEvent",
            "StereoAssociationOutcomeEvent",
        }
    ]
    digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return DecisionReplayReport(not errors, digest, tuple(errors), metrics)


def _verify_association(payload: dict[str, Any]) -> list[str]:
    pair_id = str(payload.get("pair_id"))
    edges = list(payload.get("edges") or [])
    edge_by_id = {str(edge.get("edge_id")): edge for edge in edges}
    assigned = tuple(str(item) for item in payload.get("assigned_edge_ids") or [])
    shadow = tuple(str(item) for item in payload.get("shadow_assigned_edge_ids") or [])
    errors: list[str] = []
    used_left: set[str] = set()
    used_right: set[str] = set()
    for edge_id in assigned:
        edge = edge_by_id.get(edge_id)
        if edge is None:
            errors.append(f"{pair_id}: assigned edge missing from graph: {edge_id}")
            continue
        if not edge.get("valid"):
            errors.append(f"{pair_id}: invalid edge assigned: {edge_id}")
        left = str(edge.get("left_candidate_id"))
        right = str(edge.get("right_candidate_id"))
        if left in used_left or right in used_right:
            errors.append(f"{pair_id}: assignment is not one-to-one")
        used_left.add(left)
        used_right.add(right)

    expected_global = _solve_recorded_graph(edges)
    primary_algorithm = str(payload.get("primary_algorithm"))
    if primary_algorithm == "global_v2" and tuple(sorted(assigned)) != expected_global:
        errors.append(f"{pair_id}: global primary assignment does not replay")
    if shadow and tuple(sorted(shadow)) != expected_global:
        errors.append(f"{pair_id}: global shadow assignment does not replay")

    triangulated_edges = {str(item.get("edge_id")) for item in payload.get("triangulations") or []}
    missing_triangulations = sorted(set(assigned) - triangulated_edges)
    if missing_triangulations:
        errors.append(f"{pair_id}: assigned edges lack triangulation outcomes: {missing_triangulations}")
    return errors


def _solve_recorded_graph(edges: list[dict[str, Any]]) -> tuple[str, ...]:
    valid_edges = [edge for edge in edges if edge.get("valid")]
    if not valid_edges:
        return ()
    if linear_sum_assignment is None:
        raise RuntimeError("decision replay requires scipy for global assignments")
    left = sorted({str(edge["left_candidate_id"]) for edge in valid_edges})
    right = sorted({str(edge["right_candidate_id"]) for edge in valid_edges})
    n_left, n_right = len(left), len(right)
    size = n_left + n_right
    tie_scale = size**3 + 1
    unmatched = 1_000_001
    matrix = np.full((size, size), float(10**15 * tie_scale), dtype=np.float64)
    by_pair = {(str(edge["left_candidate_id"]), str(edge["right_candidate_id"])): edge for edge in valid_edges}
    for row, left_id in enumerate(left):
        for col, right_id in enumerate(right):
            edge = by_pair.get((left_id, right_id))
            if edge is not None:
                matrix[row, col] = float(int(edge["total_cost_units"]) * tie_scale + row * n_right + col)
        matrix[row, n_right + row] = float(unmatched * tie_scale)
    for col in range(n_right):
        matrix[n_left + col, col] = float(unmatched * tie_scale)
        matrix[n_left + col, n_right:] = 0.0
    rows, cols = linear_sum_assignment(matrix)
    selected: list[str] = []
    for row, col in zip(rows, cols):
        if row >= n_left or col >= n_right:
            continue
        edge = by_pair.get((left[row], right[col]))
        if edge is not None:
            selected.append(str(edge["edge_id"]))
    return tuple(sorted(selected))


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "value": (float(numerator) / float(denominator)) if denominator > 0 else None,
    }


__all__ = ["DecisionReplayReport", "reconcile_decision_journal"]

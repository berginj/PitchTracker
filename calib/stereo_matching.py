"""Stereo pair correspondence matching for calibration."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

from calib.calibration_io import CornerDetection

MIN_CHARUCO_STEREO_CORNERS = 8


def _match_stereo_pairs(
    left_detections: List[CornerDetection],
    right_detections: List[CornerDetection],
) -> Tuple[
    List[np.ndarray],
    List[np.ndarray],
    List[np.ndarray],
    List[str],
    List[dict],
]:
    """Match left and right corner detections by index.

    Returns:
        objpoints: Matched object points
        left_imgpoints: Matched left image points
        right_imgpoints: Matched right image points
        rejection_report: List of rejection messages for user feedback
        pair_diagnostics: Per-pair accepted/rejected diagnostics
    """
    left_by_index = {det.index: det for det in left_detections}
    right_by_index = {det.index: det for det in right_detections}
    left_set = set(left_by_index)
    right_set = set(right_by_index)
    common_indices = sorted(left_set & right_set)

    left_only = left_set - right_set
    right_only = right_set - left_set
    rejection_report: List[str] = []
    pair_diagnostics: List[dict] = []

    _report_unmatched(
        left_only, right_only, left_by_index, right_by_index,
        rejection_report, pair_diagnostics,
    )

    matched_obj: List[np.ndarray] = []
    matched_left: List[np.ndarray] = []
    matched_right: List[np.ndarray] = []

    for idx in common_indices:
        left = left_by_index[idx]
        right = right_by_index[idx]

        result = _match_single_pair(idx, left, right, rejection_report,
                                    pair_diagnostics)
        if result is not None:
            obj, lp, rp = result
            matched_obj.append(obj)
            matched_left.append(lp)
            matched_right.append(rp)

    return (
        matched_obj, matched_left, matched_right,
        rejection_report, pair_diagnostics,
    )


def _report_unmatched(
    left_only: set,
    right_only: set,
    left_by_index: dict,
    right_by_index: dict,
    rejection_report: List[str],
    pair_diagnostics: List[dict],
) -> None:
    """Add rejection entries for images that only detected in one camera."""
    if left_only:
        names = [left_by_index[i].path.name for i in sorted(left_only)]
        rejection_report.append(
            f"Rejected {len(left_only)} images (left detected, right failed):"
            f" {', '.join(names[:5])}"
            + ("..." if len(names) > 5 else "")
        )
        for i in sorted(left_only):
            pair_diagnostics.append({
                "index": i, "status": "rejected",
                "reason": "right_detection_failed",
                "left_image": left_by_index[i].path.name,
                "right_image": None,
                "left_corners": int(len(left_by_index[i].imgpoints)),
                "right_corners": 0,
            })

    if right_only:
        names = [right_by_index[i].path.name for i in sorted(right_only)]
        rejection_report.append(
            f"Rejected {len(right_only)} images (right detected, left "
            f"failed): {', '.join(names[:5])}"
            + ("..." if len(names) > 5 else "")
        )
        for i in sorted(right_only):
            pair_diagnostics.append({
                "index": i, "status": "rejected",
                "reason": "left_detection_failed",
                "left_image": None,
                "right_image": right_by_index[i].path.name,
                "left_corners": 0,
                "right_corners": int(len(right_by_index[i].imgpoints)),
            })


def _match_single_pair(
    idx: int,
    left: CornerDetection,
    right: CornerDetection,
    rejection_report: List[str],
    pair_diagnostics: List[dict],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Match a single left/right pair, returning points or None."""
    if left.kind != right.kind:
        reason = f"mixed_detection_types:{left.kind}:{right.kind}"
        rejection_report.append(
            f"Rejected pair {left.path.name}/{right.path.name}: mixed "
            f"detection types ({left.kind} vs {right.kind})"
        )
        pair_diagnostics.append(
            _pair_diag(idx, left, right, "rejected", reason, 0)
        )
        return None

    if left.kind == "charuco":
        return _match_charuco_pair(
            idx, left, right, rejection_report, pair_diagnostics
        )

    if (len(left.objpoints) != len(right.objpoints)
            or len(left.imgpoints) != len(right.imgpoints)):
        reason = "checkerboard_corner_count_mismatch"
        rejection_report.append(
            f"Rejected pair {left.path.name}/{right.path.name}: "
            "checkerboard corner counts differ"
        )
        pair_diagnostics.append(
            _pair_diag(idx, left, right, "rejected", reason, 0)
        )
        return None

    pair_diagnostics.append(_pair_diag(
        idx, left, right, "accepted", "checkerboard_index_order",
        len(left.imgpoints),
    ))
    return left.objpoints, left.imgpoints, right.imgpoints


def _match_charuco_pair(
    idx: int,
    left: CornerDetection,
    right: CornerDetection,
    rejection_report: List[str],
    pair_diagnostics: List[dict],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Match a ChArUco pair by shared corner IDs."""
    if left.corner_ids is None or right.corner_ids is None:
        reason = "missing_charuco_corner_ids"
        rejection_report.append(
            f"Rejected pair {left.path.name}/{right.path.name}: "
            "missing ChArUco corner IDs"
        )
        pair_diagnostics.append(
            _pair_diag(idx, left, right, "rejected", reason, 0)
        )
        return None

    left_id_to_pos = {
        int(cid): pos for pos, cid in enumerate(left.corner_ids)
    }
    right_id_to_pos = {
        int(cid): pos for pos, cid in enumerate(right.corner_ids)
    }
    shared_ids = sorted(set(left_id_to_pos) & set(right_id_to_pos))

    if len(shared_ids) < MIN_CHARUCO_STEREO_CORNERS:
        reason = f"too_few_shared_charuco_corners:{len(shared_ids)}"
        rejection_report.append(
            f"Rejected pair {left.path.name}/{right.path.name}: only "
            f"{len(shared_ids)} shared ChArUco corners "
            f"(need {MIN_CHARUCO_STEREO_CORNERS})"
        )
        pair_diagnostics.append(_pair_diag(
            idx, left, right, "rejected", reason, len(shared_ids),
        ))
        return None

    left_rows = [left_id_to_pos[cid] for cid in shared_ids]
    right_rows = [right_id_to_pos[cid] for cid in shared_ids]
    pair_diagnostics.append(_pair_diag(
        idx, left, right, "accepted", "shared_charuco_ids", len(shared_ids),
    ))
    return (
        left.objpoints[left_rows],
        left.imgpoints[left_rows],
        right.imgpoints[right_rows],
    )


def _pair_diag(
    index: int,
    left: CornerDetection,
    right: CornerDetection,
    status: str,
    reason: str,
    shared_corners: int,
) -> dict:
    return {
        "index": index,
        "status": status,
        "reason": reason,
        "left_image": left.path.name,
        "right_image": right.path.name,
        "detection_type": (
            left.kind if left.kind == right.kind
            else f"{left.kind}/{right.kind}"
        ),
        "left_corners": int(len(left.imgpoints)),
        "right_corners": int(len(right.imgpoints)),
        "shared_corners": int(shared_corners),
    }

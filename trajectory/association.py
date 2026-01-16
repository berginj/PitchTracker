"""Joint association between left/right detections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from trajectory.camera_model import CameraModel

try:
    from scipy.optimize import linear_sum_assignment
except Exception:  # pragma: no cover
    linear_sum_assignment = None


@dataclass(frozen=True)
class MatchedPair:
    t_ns: int
    left_uv: Tuple[float, float]
    right_uv: Tuple[float, float]


class JointAssociator:
    def __init__(self, camera_left: Optional[CameraModel], camera_right: Optional[CameraModel]) -> None:
        self._left = camera_left
        self._right = camera_right

    def associate(
        self,
        t_ns: int,
        left_dets: List[Tuple[float, float]],
        right_dets: List[Tuple[float, float]],
    ) -> List[MatchedPair]:
        if not left_dets or not right_dets:
            return []
        cost = np.zeros((len(left_dets), len(right_dets)), dtype=float)
        for i, left in enumerate(left_dets):
            for j, right in enumerate(right_dets):
                cost[i, j] = self._pair_cost(np.array(left), np.array(right))
        if linear_sum_assignment is None:
            return _greedy_match(t_ns, left_dets, right_dets, cost)
        row_ind, col_ind = linear_sum_assignment(cost)
        pairs: List[MatchedPair] = []
        for r, c in zip(row_ind, col_ind):
            if cost[r, c] > 25.0:
                continue
            pairs.append(MatchedPair(t_ns=t_ns, left_uv=left_dets[r], right_uv=right_dets[c]))
        return pairs

    def _pair_cost(self, left_uv: np.ndarray, right_uv: np.ndarray) -> float:
        if self._left is not None:
            dist = self._left.epipolar_distance(left_uv, right_uv)
            if dist is not None:
                return float(dist)
        return float(abs(left_uv[1] - right_uv[1]))


def _greedy_match(
    t_ns: int,
    left_dets: List[Tuple[float, float]],
    right_dets: List[Tuple[float, float]],
    cost: np.ndarray,
) -> List[MatchedPair]:
    pairs: List[MatchedPair] = []
    used_right = set()
    for i in range(cost.shape[0]):
        best = None
        best_j = None
        for j in range(cost.shape[1]):
            if j in used_right:
                continue
            if best is None or cost[i, j] < best:
                best = cost[i, j]
                best_j = j
        if best_j is not None and best is not None and best < 25.0:
            used_right.add(best_j)
            pairs.append(MatchedPair(t_ns=t_ns, left_uv=left_dets[i], right_uv=right_dets[best_j]))
    return pairs

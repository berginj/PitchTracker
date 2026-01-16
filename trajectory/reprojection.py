"""Reprojection EKF and RTS smoother."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from trajectory.camera_model import CameraModel


@dataclass
class EKFState:
    t_ns: int
    x: np.ndarray
    P: np.ndarray


class ReprojectionEKF:
    def __init__(
        self,
        camera_left: CameraModel,
        camera_right: CameraModel,
        process_var: float = 0.5,
        meas_var_px: float = 2.0,
    ) -> None:
        self._left = camera_left
        self._right = camera_right
        self._process_var = process_var
        self._meas_var = meas_var_px
        self._states: List[EKFState] = []

    def run(self, matches: List[Tuple[int, Tuple[float, float], Tuple[float, float]]]) -> List[EKFState]:
        self._states = []
        if not matches:
            return []
        t0, left_uv, right_uv = matches[0]
        x0 = np.array([0.0, 5.0, 50.0, 0.0, 0.0, 0.0], dtype=float)
        P0 = np.eye(6) * 10.0
        state = EKFState(t_ns=t0, x=x0, P=P0)
        self._states.append(state)
        for t_ns, left_uv, right_uv in matches[1:]:
            dt = max((t_ns - state.t_ns) / 1e9, 1e-3)
            x_pred, F = _predict_state(state.x, dt)
            Q = np.eye(6) * self._process_var
            P_pred = F @ state.P @ F.T + Q
            z = np.array([left_uv[0], left_uv[1], right_uv[0], right_uv[1]], dtype=float)
            z_pred, H = _project_measurement(self._left, self._right, x_pred[:3])
            R = np.eye(4) * (self._meas_var ** 2)
            y = z - z_pred
            S = H @ P_pred @ H.T + R
            K = P_pred @ H.T @ np.linalg.pinv(S)
            x_upd = x_pred + K @ y
            P_upd = (np.eye(6) - K @ H) @ P_pred
            state = EKFState(t_ns=t_ns, x=x_upd, P=P_upd)
            self._states.append(state)
        return self._states

    @property
    def states(self) -> List[EKFState]:
        return self._states


class RTSSmoother:
    def smooth(self, states: List[EKFState]) -> List[EKFState]:
        if not states:
            return []
        smoothed = [state for state in states]
        for i in range(len(states) - 2, -1, -1):
            dt = max((states[i + 1].t_ns - states[i].t_ns) / 1e9, 1e-3)
            x_pred, F = _predict_state(states[i].x, dt)
            Q = np.eye(6) * 0.5
            P_pred = F @ states[i].P @ F.T + Q
            C = states[i].P @ F.T @ np.linalg.pinv(P_pred)
            x_smooth = states[i].x + C @ (smoothed[i + 1].x - x_pred)
            P_smooth = states[i].P + C @ (smoothed[i + 1].P - P_pred) @ C.T
            smoothed[i] = EKFState(t_ns=states[i].t_ns, x=x_smooth, P=P_smooth)
        return smoothed


def _predict_state(x: np.ndarray, dt: float) -> Tuple[np.ndarray, np.ndarray]:
    F = np.eye(6)
    for i in range(3):
        F[i, i + 3] = dt
    x_pred = F @ x
    x_pred[1] += 0.5 * (-32.174) * dt * dt
    x_pred[4] += -32.174 * dt
    return x_pred, F


def _project_measurement(
    left: CameraModel,
    right: CameraModel,
    xyz: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    left_uv = left.project(xyz)
    right_uv = right.project(xyz)
    z_pred = np.array([left_uv[0], left_uv[1], right_uv[0], right_uv[1]], dtype=float)
    J_left = left.jacobian_project(xyz)
    J_right = right.jacobian_project(xyz)
    H = np.zeros((4, 6), dtype=float)
    H[0:2, 0:3] = J_left
    H[2:4, 0:3] = J_right
    return z_pred, H

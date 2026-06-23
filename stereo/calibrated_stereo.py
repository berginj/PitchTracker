"""Calibrated stereo matcher using saved camera matrices."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from contracts import StereoObservation
from stereo.association import StereoMatch, StereoMatcher


MM_PER_FOOT = 304.8


@dataclass(frozen=True)
class CalibratedStereoGeometry:
    mtx_left: np.ndarray
    dist_left: np.ndarray
    mtx_right: np.ndarray
    dist_right: np.ndarray
    R: np.ndarray
    T: np.ndarray
    F: np.ndarray
    img_size: Tuple[int, int]
    epipolar_epsilon_px: float
    z_min_ft: float
    z_max_ft: float
    time_sync_offset_ns: int = 0

    @classmethod
    def from_npz(
        cls,
        path: Path,
        epipolar_epsilon_px: float,
        z_min_ft: float,
        z_max_ft: float,
        time_sync_offset_ns: int = 0,
    ) -> "CalibratedStereoGeometry":
        data = np.load(path, allow_pickle=True)
        img_size_raw = data["img_size"]
        mtx_left = np.asarray(data["mtx_left"], dtype=np.float64)
        mtx_right = np.asarray(data["mtx_right"], dtype=np.float64)
        rmat = np.asarray(data["R"], dtype=np.float64)
        tvec = np.asarray(data["T"], dtype=np.float64).reshape(3, 1)
        fmat = (
            np.asarray(data["F"], dtype=np.float64)
            if "F" in data
            else _fundamental_from_rt(mtx_left, mtx_right, rmat, tvec)
        )

        # Basic validation of loaded arrays
        if mtx_left.shape != (3, 3) or mtx_right.shape != (3, 3):
            raise ValueError("Loaded calibration matrices must be 3x3")
        if tvec.shape not in ((3, 1), (3,)):
            raise ValueError("Loaded translation vector has unexpected shape")

        return cls(
            mtx_left=mtx_left,
            dist_left=np.asarray(data["dist_left"], dtype=np.float64),
            mtx_right=mtx_right,
            dist_right=np.asarray(data["dist_right"], dtype=np.float64),
            R=rmat,
            T=tvec,
            F=fmat,
            img_size=(int(img_size_raw[0]), int(img_size_raw[1])),
            epipolar_epsilon_px=float(epipolar_epsilon_px),
            z_min_ft=float(z_min_ft),
            z_max_ft=float(z_max_ft),
            time_sync_offset_ns=int(time_sync_offset_ns),
        )


class CalibratedStereoMatcher(StereoMatcher):
    """Stereo matcher that uses the calibrated fundamental matrix and projection matrices."""

    def __init__(self, geometry: CalibratedStereoGeometry) -> None:
        self._geometry = geometry
        self._p_left = geometry.mtx_left @ np.hstack([np.eye(3), np.zeros((3, 1))])
        self._p_right = geometry.mtx_right @ np.hstack([geometry.R, geometry.T])
        # Time sync offset in nanoseconds to be applied to right timestamps when pairing
        self._time_sync_offset_ns = int(getattr(geometry, "time_sync_offset_ns", 0))

    def match(self, left, right) -> Optional[StereoMatch]:
        error = self._symmetric_epipolar_error(left.u, left.v, right.u, right.v)
        if error > self._geometry.epipolar_epsilon_px:
            return None
        return StereoMatch(
            left=left,
            right=right,
            epipolar_error_px=float(error),
            score=min(left.confidence, right.confidence),
        )

    def triangulate(self, match: StereoMatch) -> StereoObservation:
        left_pt = np.array([[match.left.u], [match.left.v]], dtype=np.float64)
        right_pt = np.array([[match.right.u], [match.right.v]], dtype=np.float64)
        homogeneous = cv2.triangulatePoints(self._p_left, self._p_right, left_pt, right_pt)
        xyz_mm = (homogeneous[:3] / homogeneous[3]).reshape(3)
        xyz_ft = xyz_mm / MM_PER_FOOT
        z_ft = float(xyz_ft[2])
        in_range = self._geometry.z_min_ft <= z_ft <= self._geometry.z_max_ft
        timestamp_ns, applied = self.pair_timestamp(
            match.left.t_capture_monotonic_ns,
            match.right.t_capture_monotonic_ns,
        )
        confidence = match.score if in_range else 0.0
        return StereoObservation(
            t_ns=timestamp_ns,
            left=(match.left.u, match.left.v),
            right=(match.right.u, match.right.v),
            X=float(xyz_ft[0]),
            Y=float(xyz_ft[1]),
            Z=z_ft,
            quality=1.0 if in_range else 0.0,
            confidence=confidence,
        )

    def pair_timestamp(self, left_ns: int, right_ns: int) -> Tuple[int, bool]:
        """Apply configured time sync offset (added to right timestamp) before averaging.

        Returns (paired_timestamp_ns, offset_applied_bool)
        """
        if self._time_sync_offset_ns != 0:
            right_ns_adj = int(right_ns + self._time_sync_offset_ns)
            return (left_ns + right_ns_adj) // 2, True
        return (left_ns + right_ns) // 2, False

    def _symmetric_epipolar_error(self, left_u: float, left_v: float, right_u: float, right_v: float) -> float:
        left_pt = np.array([left_u, left_v, 1.0], dtype=np.float64)
        right_pt = np.array([right_u, right_v, 1.0], dtype=np.float64)
        line_right = self._geometry.F @ left_pt
        line_left = self._geometry.F.T @ right_pt
        err_right = _point_line_distance(right_pt, line_right)
        err_left = _point_line_distance(left_pt, line_left)
        return float((err_left + err_right) * 0.5)


def _point_line_distance(point: np.ndarray, line: np.ndarray) -> float:
    denom = float(np.hypot(line[0], line[1]))
    if denom <= 1e-12:
        return float("inf")
    return abs(float(point @ line)) / denom


def _fundamental_from_rt(
    mtx_left: np.ndarray,
    mtx_right: np.ndarray,
    rmat: np.ndarray,
    tvec: np.ndarray,
) -> np.ndarray:
    tx = np.array(
        [
            [0.0, -tvec[2, 0], tvec[1, 0]],
            [tvec[2, 0], 0.0, -tvec[0, 0]],
            [-tvec[1, 0], tvec[0, 0], 0.0],
        ],
        dtype=np.float64,
    )
    return np.linalg.inv(mtx_right).T @ tx @ rmat @ np.linalg.inv(mtx_left)

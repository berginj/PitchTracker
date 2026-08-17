"""Stereo rectification.

``StereoRectifier`` turns a calibrated stereo geometry into per-camera
rectification maps (``cv2.stereoRectify`` + ``cv2.initUndistortRectifyMap``) and
applies them to frames so corresponding points land on the same image row. This
is the piece the architecture note flagged as missing: ``SimpleStereoMatcher``
assumed rectified coordinates but nothing ever produced them.

The rectified projection matrices ``P1``/``P2`` are exposed so callers (and
tests) can verify row alignment analytically without rendering.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

import cv2
import numpy as np

from contracts import Frame
from log_config.logger import get_logger
from stereo.calibrated_stereo import CalibratedStereoGeometry

logger = get_logger(__name__)


class Rectifier(ABC):
    @abstractmethod
    def rectify(self, frame: Frame) -> Frame:
        """Rectify an input frame."""


class StereoRectifier:
    """Rectifies left/right frames into a row-aligned (epipolar) geometry.

    Build with :meth:`from_geometry`. ``rectify_pair`` remaps a synchronized
    left/right image pair; ``rectify_left``/``rectify_right`` remap a single
    side. The class is independent of the per-frame :class:`Rectifier` ABC
    because stereo rectification is inherently a two-camera operation.
    """

    def __init__(
        self,
        map_left: Tuple[np.ndarray, np.ndarray],
        map_right: Tuple[np.ndarray, np.ndarray],
        r_left: np.ndarray,
        r_right: np.ndarray,
        p_left: np.ndarray,
        p_right: np.ndarray,
        q: np.ndarray,
        image_size: Tuple[int, int],
    ) -> None:
        self._map_left = map_left
        self._map_right = map_right
        self.R1 = r_left
        self.R2 = r_right
        self.P1 = p_left
        self.P2 = p_right
        self.Q = q
        self.image_size = image_size

    @classmethod
    def from_geometry(
        cls,
        geometry: CalibratedStereoGeometry,
        alpha: float = 0.0,
    ) -> "StereoRectifier":
        """Build rectification maps from a calibrated stereo geometry.

        Args:
            geometry: Calibrated intrinsics/extrinsics for the rig.
            alpha: Free scaling for ``stereoRectify`` (0 crops to valid pixels,
                1 keeps all source pixels).

        Returns:
            A ready-to-use :class:`StereoRectifier`.
        """
        width, height = geometry.img_size
        r_left, r_right, p_left, p_right, q, _, _ = cv2.stereoRectify(
            geometry.mtx_left,
            geometry.dist_left,
            geometry.mtx_right,
            geometry.dist_right,
            (width, height),
            geometry.R,
            geometry.T,
            flags=cv2.CALIB_ZERO_DISPARITY,
            alpha=alpha,
        )
        map_left = cv2.initUndistortRectifyMap(
            geometry.mtx_left,
            geometry.dist_left,
            r_left,
            p_left,
            (width, height),
            cv2.CV_32FC1,
        )
        map_right = cv2.initUndistortRectifyMap(
            geometry.mtx_right,
            geometry.dist_right,
            r_right,
            p_right,
            (width, height),
            cv2.CV_32FC1,
        )
        logger.info(
            "Built stereo rectifier: image_size={}x{} alpha={}",
            width,
            height,
            alpha,
        )
        return cls(
            map_left=map_left,
            map_right=map_right,
            r_left=np.asarray(r_left, dtype=np.float64),
            r_right=np.asarray(r_right, dtype=np.float64),
            p_left=np.asarray(p_left, dtype=np.float64),
            p_right=np.asarray(p_right, dtype=np.float64),
            q=np.asarray(q, dtype=np.float64),
            image_size=(width, height),
        )

    def rectify_left(self, image: np.ndarray) -> np.ndarray:
        """Remap a left-camera image into the rectified frame."""
        return np.asarray(cv2.remap(image, self._map_left[0], self._map_left[1], cv2.INTER_LINEAR))

    def rectify_right(self, image: np.ndarray) -> np.ndarray:
        """Remap a right-camera image into the rectified frame."""
        return np.asarray(cv2.remap(image, self._map_right[0], self._map_right[1], cv2.INTER_LINEAR))

    def rectify_pair(self, left: np.ndarray, right: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Remap a synchronized left/right pair into the rectified frame."""
        return self.rectify_left(left), self.rectify_right(right)

    def rectified_row(self, point_3d: np.ndarray) -> Tuple[float, float]:
        """Return the image rows a 3D point projects to in each rectified view.

        Useful for verifying alignment: a correctly rectified rig yields equal
        rows for both cameras. ``point_3d`` is in the left (unrectified) camera
        frame, in the same metric units as the calibration (typically mm).
        """
        point = np.asarray(point_3d, dtype=np.float64).reshape(3)
        homog = np.append(point, 1.0)
        left = self.P1 @ homog
        right = self.P2 @ homog
        return float(left[1] / left[2]), float(right[1] / right[2])

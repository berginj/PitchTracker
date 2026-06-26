"""Targetless stereo-setup logic: overlap validation and coarse rectification.

These are pure, synthetic-testable functions that operate on a synchronized
left/right grayscale frame pair. They prove the rig can *compare* and *coarsely
calibrate* the two views before any pitch-tracking logic matters:

* ``validate_overlap`` — feature-match the pair and score the shared field of
  view (setup step 5). Gates rectification.
* ``coarse_rectify`` — estimate the fundamental matrix and uncalibrated
  rectifying homographies, reporting epipolar error before/after (step 6).

Both return frozen contracts from :mod:`contracts.setup` so results flow
straight into manifests and the calibration quality report.
"""

from __future__ import annotations

from calib.stereo_setup.overlap import OverlapConfig, validate_overlap
from calib.stereo_setup.rectify import (
    RectifyConfig,
    coarse_rectify,
    rectify_from_correspondences,
)

__all__ = [
    "OverlapConfig",
    "validate_overlap",
    "RectifyConfig",
    "coarse_rectify",
    "rectify_from_correspondences",
]

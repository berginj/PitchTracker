"""AprilTag fiducial detection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - handled by consumers
    cv2 = None  # type: ignore[assignment]


@dataclass(frozen=True)
class FiducialDetection:
    tag_id: int
    corners: List[Tuple[float, float]]


def detect_apriltags(gray: np.ndarray) -> Tuple[List[FiducialDetection], Optional[str]]:
    """Detect AprilTag 36h11 tags in a grayscale image."""
    if cv2 is None or not hasattr(cv2, "aruco"):
        return [], "AprilTag detection unavailable (opencv-contrib-python required)."
    try:
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
        detector = cv2.aruco.ArucoDetector(dictionary)
        corners, ids, _ = detector.detectMarkers(gray)
    except Exception as exc:  # noqa: BLE001 - surface detector issues
        return [], str(exc)
    detections: List[FiducialDetection] = []
    if ids is None:
        return detections, None
    for corner, tag_id in zip(corners, ids.flatten()):
        pts = [(float(x), float(y)) for x, y in corner[0]]
        detections.append(FiducialDetection(tag_id=int(tag_id), corners=pts))
    return detections, None

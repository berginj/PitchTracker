"""Shared ChArUco board and detector helpers.

Single source of truth for the marker-to-square ratio, the predefined
dictionary, and ArUco detector parameters. Previously each call site
hand-rolled these, which led to two real bugs:

* boards generated at a 0.73 marker ratio but detected expecting 0.75, and
* copy-pasted ``DetectorParameters`` blocks whose ``minMarkerPerimeterRate``
  disagreed (0.01 vs 0.03) between the auto-scan and fast paths.

Import from here so generated boards always match what the detectors expect.
"""

from __future__ import annotations

import cv2

# Marker side length as a fraction of the square side length. ChArUco markers
# sit inside the white squares; 0.75 is the value the detection code assumes.
MARKER_RATIO = 0.75

# Default predefined ArUco dictionary used across calibration.
DEFAULT_DICTIONARY_ID = cv2.aruco.DICT_6X6_250


def get_dictionary(dictionary_id: int = DEFAULT_DICTIONARY_ID):
    """Return a predefined ArUco dictionary."""
    return cv2.aruco.getPredefinedDictionary(dictionary_id)


def make_charuco_board(
    cols: int,
    rows: int,
    square_size: float,
    dictionary=None,
    marker_ratio: float = MARKER_RATIO,
):
    """Build a ChArUco board, handling both OpenCV API generations.

    Args:
        cols: Number of squares across.
        rows: Number of squares down.
        square_size: Square side length in the caller's units (mm or m).
        dictionary: ArUco dictionary; defaults to :data:`DEFAULT_DICTIONARY_ID`.
        marker_ratio: Marker/square ratio; defaults to :data:`MARKER_RATIO`.

    Returns:
        A ``cv2.aruco.CharucoBoard`` instance.
    """
    if dictionary is None:
        dictionary = get_dictionary()
    marker_size = square_size * marker_ratio
    try:
        # OpenCV 4.7+ object API.
        return cv2.aruco.CharucoBoard((cols, rows), square_size, marker_size, dictionary)
    except (AttributeError, TypeError):
        # Legacy factory API.
        return cv2.aruco.CharucoBoard_create(cols, rows, square_size, marker_size, dictionary)


def charuco_detector_params(aggressive: bool = False):
    """Return ArUco ``DetectorParameters`` with unified, consistent values.

    Args:
        aggressive: When True, use the permissive settings for the initial
            dictionary auto-scan (smaller minimum marker perimeter, closer to
            the image border). When False, use the stricter settings for the
            steady-state fast path.

    Returns:
        A configured ``cv2.aruco.DetectorParameters`` instance.
    """
    try:
        params = cv2.aruco.DetectorParameters()
    except AttributeError:
        params = cv2.aruco.DetectorParameters_create()

    params.adaptiveThreshWinSizeMin = 3
    params.adaptiveThreshWinSizeMax = 23
    params.adaptiveThreshWinSizeStep = 10
    params.adaptiveThreshConstant = 7
    params.minMarkerPerimeterRate = 0.01 if aggressive else 0.03
    params.maxMarkerPerimeterRate = 4.0
    params.polygonalApproxAccuracyRate = 0.05
    params.minCornerDistanceRate = 0.05
    params.minDistanceToBorder = 1 if aggressive else 3
    try:
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        params.cornerRefinementWinSize = 5
        params.cornerRefinementMaxIterations = 30
        params.cornerRefinementMinAccuracy = 0.1
    except AttributeError:
        pass
    return params


def make_aruco_detector(dictionary, aggressive: bool = False):
    """Return ``(marker_corners, marker_ids, rejected)`` detector callable.

    Hides the OpenCV 4.7+ ``ArucoDetector`` vs legacy ``detectMarkers`` split.
    Returns a function ``detect(gray) -> (corners, ids, rejected)``.
    """
    params = charuco_detector_params(aggressive=aggressive)
    try:
        detector = cv2.aruco.ArucoDetector(dictionary, params)

        def detect(gray):
            return detector.detectMarkers(gray)

    except AttributeError:

        def detect(gray):
            return cv2.aruco.detectMarkers(gray, dictionary, parameters=params)

    return detect

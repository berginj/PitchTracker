"""Tests for the shared ChArUco helpers (calib.charuco)."""

from __future__ import annotations

import cv2
import numpy as np

from calib.charuco import (
    DEFAULT_DICTIONARY_ID,
    MARKER_RATIO,
    charuco_detector_params,
    get_dictionary,
    make_aruco_detector,
    make_charuco_board,
)


def test_marker_ratio_is_canonical():
    # Detection code assumes 0.75; generated boards must match.
    assert MARKER_RATIO == 0.75


def test_get_dictionary_default():
    d = get_dictionary()
    assert d is not None
    assert DEFAULT_DICTIONARY_ID == cv2.aruco.DICT_6X6_250


def test_make_charuco_board_dimensions():
    board = make_charuco_board(9, 6, 30.0)
    # Board exposes its chessboard corner count (8x5 inner corners for 9x6).
    chessboard = board.getChessboardCorners()
    assert chessboard.shape[0] == (9 - 1) * (6 - 1)


def test_detector_params_aggressive_vs_strict():
    aggressive = charuco_detector_params(aggressive=True)
    strict = charuco_detector_params(aggressive=False)
    assert aggressive.minMarkerPerimeterRate == 0.01
    assert strict.minMarkerPerimeterRate == 0.03
    assert aggressive.minDistanceToBorder == 1
    assert strict.minDistanceToBorder == 3


def test_detector_params_shared_values_consistent():
    p = charuco_detector_params()
    assert p.maxMarkerPerimeterRate == 4.0
    assert p.polygonalApproxAccuracyRate == 0.05


def test_make_aruco_detector_runs_on_board_render():
    board = make_charuco_board(5, 5, 60.0)
    try:
        img = board.generateImage((600, 600))
    except AttributeError:
        img = board.draw((600, 600))
    detect = make_aruco_detector(get_dictionary(), aggressive=True)
    corners, ids, _ = detect(img)
    # The rendered board's markers should be detected.
    assert ids is not None and len(ids) > 0


def test_generated_board_detected_at_same_ratio():
    # Generate a board with the shared factory and confirm detection finds
    # markers -- guards against the 0.73/0.75 ratio mismatch regression.
    board = make_charuco_board(7, 5, 80.0)
    try:
        img = board.generateImage((900, 700))
    except AttributeError:
        img = board.draw((900, 700))
    assert isinstance(img, np.ndarray)
    detect = make_aruco_detector(get_dictionary(), aggressive=True)
    _, ids, _ = detect(img)
    assert ids is not None and len(ids) >= 4

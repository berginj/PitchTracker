"""Test ChArUco board detection."""

import cv2
import numpy as np
from pathlib import Path


def test_charuco_detection():
    """Test that ChArUco board can be detected from generated image."""
    # Load the generated board
    board_path = Path("alignment_checks/test_charuco_board.png")
    if not board_path.exists():
        print("Error: Test board not found. Run generate_charuco_board.py first.")
        return False

    image = cv2.imread(str(board_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        print("Error: Failed to load board image")
        return False

    print(f"Loaded board image: {image.shape}")

    # Create ChArUco board definition (must match generator)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

    try:
        # Try newer API first (OpenCV 4.7+)
        board = cv2.aruco.CharucoBoard(
            (9, 6),
            30.0,
            22.5,
            aruco_dict
        )
    except (AttributeError, TypeError):
        # Fall back to older API
        board = cv2.aruco.CharucoBoard_create(
            9,
            6,
            30.0,
            22.5,
            aruco_dict
        )

    # Detect markers
    try:
        # Try newer API first (OpenCV 4.7+)
        detector_params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
        marker_corners, marker_ids, rejected = detector.detectMarkers(image)
    except AttributeError:
        # Fall back to older API
        detector_params = cv2.aruco.DetectorParameters_create()
        marker_corners, marker_ids, rejected = cv2.aruco.detectMarkers(
            image, aruco_dict, parameters=detector_params
        )

    if marker_ids is None or len(marker_ids) == 0:
        print("Error: No ArUco markers detected!")
        return False

    print(f"Detected {len(marker_ids)} ArUco markers")

    # Interpolate ChArUco corners
    try:
        # Try newer API first (OpenCV 4.7+)
        num_corners, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
            marker_corners, marker_ids, image, board
        )
    except TypeError:
        # Fall back to older API
        num_corners, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
            marker_corners, marker_ids, image, board
        )

    if num_corners is None or num_corners < 4:
        corner_count = num_corners if num_corners is not None else 0
        print(f"Error: Not enough ChArUco corners detected ({corner_count}/4+)")
        return False

    print(f"Detected {num_corners} ChArUco corners")
    print("OK: ChArUco detection test passed!")
    return True


if __name__ == "__main__":
    success = test_charuco_detection()
    exit(0 if success else 1)

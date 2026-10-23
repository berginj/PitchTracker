"""ChArUco detection must assert success without a workstation-local board image."""

import cv2

from calib.charuco import get_dictionary, make_aruco_detector, make_charuco_board


def test_charuco_detection():
    """Detect the generated board through the shared production board/detector helpers."""
    board = make_charuco_board(9, 6, 30.0)
    image = board.generateImage((1800, 1200), marginSize=40)
    detect = make_aruco_detector(get_dictionary())
    marker_corners, marker_ids, _ = detect(image)
    assert marker_ids is not None and len(marker_ids) > 0, "No ArUco markers detected"
    num_corners, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
        marker_corners, marker_ids, image, board)
    assert num_corners == 40, "Expected all 8 × 5 inner corners on the synthetic board"
    assert charuco_corners is not None and charuco_ids is not None
    assert len(set(charuco_ids.ravel())) == 40


if __name__ == "__main__":
    test_charuco_detection()

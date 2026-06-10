"""Test calibration corner detection with ChArUco and checkerboard fallback."""

import cv2
import numpy as np
import pytest
from pathlib import Path
import tempfile
from typing import Tuple

# Import the function we're testing
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from calib.quick_calibrate import _collect_corners


def create_checkerboard_image(
    pattern_size: Tuple[int, int], square_px: int = 50, add_noise: bool = False
) -> np.ndarray:
    """Create a synthetic checkerboard pattern image.

    Args:
        pattern_size: Number of squares (cols, rows)
        square_px: Size of each square in pixels
        add_noise: Add random noise to simulate real-world conditions

    Returns:
        Grayscale image with checkerboard pattern
    """
    height = pattern_size[1] * square_px
    width = pattern_size[0] * square_px
    image = np.zeros((height, width), dtype=np.uint8)

    for i in range(pattern_size[1]):
        for j in range(pattern_size[0]):
            if (i + j) % 2 == 0:
                image[i * square_px : (i + 1) * square_px, j * square_px : (j + 1) * square_px] = 255

    if add_noise:
        noise = np.random.normal(0, 10, image.shape).astype(np.int16)
        image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return image


def create_charuco_board_image(pattern_size: Tuple[int, int], square_px: int = 50) -> np.ndarray:
    """Create a synthetic ChArUco board image.

    Args:
        pattern_size: Number of squares (cols, rows)
        square_px: Size of each square in pixels

    Returns:
        Grayscale image with ChArUco pattern
    """
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

    try:
        # Try newer API first (OpenCV 4.7+)
        board = cv2.aruco.CharucoBoard(
            (pattern_size[0], pattern_size[1]), float(square_px), float(square_px) * 0.75, aruco_dict
        )
        img_size = (pattern_size[0] * square_px, pattern_size[1] * square_px)
        image = board.generateImage(img_size)
    except (AttributeError, TypeError):
        # Fall back to older API
        board = cv2.aruco.CharucoBoard_create(
            pattern_size[0], pattern_size[1], float(square_px), float(square_px) * 0.75, aruco_dict
        )
        img_size = (pattern_size[0] * square_px, pattern_size[1] * square_px)
        image = board.draw(img_size)

    return image


def test_collect_corners_charuco_success():
    """Test successful ChArUco corner detection."""
    pattern_size = (9, 6)
    square_mm = 30.0

    # Create temporary directory for test images
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create ChArUco board images
        image1 = create_charuco_board_image(pattern_size, square_px=50)
        image2 = create_charuco_board_image(pattern_size, square_px=50)

        path1 = tmpdir_path / "charuco1.png"
        path2 = tmpdir_path / "charuco2.png"
        cv2.imwrite(str(path1), image1)
        cv2.imwrite(str(path2), image2)

        # Test corner detection
        detections, img_size = _collect_corners([path1, path2], pattern_size, square_mm)

        # Verify results
        assert len(detections) == 2, "Should detect corners in both images"
        assert [det.index for det in detections] == [0, 1], "Both images should succeed"
        assert img_size[0] > 0 and img_size[1] > 0, "Image size should be valid"

        # Verify corner count (ChArUco boards have (cols-1)*(rows-1) internal corners)
        expected_corners = (pattern_size[0] - 1) * (pattern_size[1] - 1)
        for det in detections:
            obj_pts = det.objpoints
            img_pts = det.imgpoints
            assert det.kind == "charuco"
            assert det.corner_ids is not None
            assert len(obj_pts) > 0, "Should have object points"
            assert len(img_pts) > 0, "Should have image points"
            assert len(obj_pts) == len(img_pts), "Object and image points should match"


def test_collect_corners_checkerboard_fallback():
    """Test fallback to plain checkerboard when ChArUco markers not detected."""
    pattern_size = (9, 6)
    square_mm = 30.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create plain checkerboard images (no ArUco markers)
        image1 = create_checkerboard_image(pattern_size, square_px=50)
        image2 = create_checkerboard_image(pattern_size, square_px=50, add_noise=True)

        path1 = tmpdir_path / "checkerboard1.png"
        path2 = tmpdir_path / "checkerboard2.png"
        cv2.imwrite(str(path1), image1)
        cv2.imwrite(str(path2), image2)

        # Test corner detection with fallback
        detections, img_size = _collect_corners([path1, path2], pattern_size, square_mm)

        # Verify results
        assert len(detections) == 2, "Should detect corners in both images using fallback"
        assert [det.index for det in detections] == [0, 1], "Both images should succeed"

        # Verify corner count for plain checkerboard (internal corners only)
        internal_corners = (pattern_size[0] - 1) * (pattern_size[1] - 1)
        for det in detections:
            obj_pts = det.objpoints
            img_pts = det.imgpoints
            assert det.kind == "checkerboard"
            assert len(obj_pts) == internal_corners, f"Should have {internal_corners} corners"
            assert len(img_pts) == internal_corners, f"Should have {internal_corners} image points"

            # Verify object points are properly scaled
            assert obj_pts[0, 2] == 0, "Z coordinate should be 0 (planar board)"
            max_coord = max(obj_pts[:, 0].max(), obj_pts[:, 1].max())
            expected_max = (max(pattern_size[0], pattern_size[1]) - 2) * square_mm
            assert abs(max_coord - expected_max) < 1.0, "Object points should be scaled by square_mm"


def test_collect_corners_mixed_detection():
    """Test mixed scenario: some images use ChArUco, others use checkerboard fallback."""
    pattern_size = (7, 5)
    square_mm = 25.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create mix of ChArUco and plain checkerboard images
        charuco_image = create_charuco_board_image(pattern_size, square_px=60)
        checker_image = create_checkerboard_image(pattern_size, square_px=60)

        path1 = tmpdir_path / "charuco.png"
        path2 = tmpdir_path / "checkerboard.png"
        cv2.imwrite(str(path1), charuco_image)
        cv2.imwrite(str(path2), checker_image)

        # Test corner detection
        detections, img_size = _collect_corners([path1, path2], pattern_size, square_mm)

        # Verify results
        assert len(detections) == 2, "Should detect corners in both images"
        assert [det.index for det in detections] == [0, 1], "Both images should succeed"

        # Both should have valid corners (exact count may vary for ChArUco)
        for det in detections:
            obj_pts = det.objpoints
            img_pts = det.imgpoints
            assert len(obj_pts) >= 4, "Should have at least MIN_CORNERS (4)"
            assert len(obj_pts) == len(img_pts), "Object and image points should match"


def test_collect_corners_complete_failure():
    """Test failure when neither ChArUco nor checkerboard can be detected."""
    pattern_size = (9, 6)
    square_mm = 30.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create image with no detectable pattern (random noise)
        noise_image = np.random.randint(0, 255, (400, 600), dtype=np.uint8)

        path = tmpdir_path / "noise.png"
        cv2.imwrite(str(path), noise_image)

        # Test corner detection - should fail but not crash
        detections, img_size = _collect_corners([path], pattern_size, square_mm)

        # Verify failure handling
        assert len(detections) == 0, "Should not detect any corners in noise"


def test_collect_corners_partial_success():
    """Test scenario where some images succeed and others fail."""
    pattern_size = (8, 6)
    square_mm = 28.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create mix: valid checkerboard, noise, valid ChArUco
        checker_image = create_checkerboard_image(pattern_size, square_px=55)
        noise_image = np.random.randint(0, 255, (400, 600), dtype=np.uint8)
        charuco_image = create_charuco_board_image(pattern_size, square_px=55)

        path1 = tmpdir_path / "checkerboard.png"
        path2 = tmpdir_path / "noise.png"
        path3 = tmpdir_path / "charuco.png"
        cv2.imwrite(str(path1), checker_image)
        cv2.imwrite(str(path2), noise_image)
        cv2.imwrite(str(path3), charuco_image)

        # Test corner detection
        detections, img_size = _collect_corners([path1, path2, path3], pattern_size, square_mm)

        # Verify results
        assert len(detections) == 2, "Should detect corners in 2 out of 3 images"
        assert [det.index for det in detections] == [0, 2], "First and third images should succeed"


def test_collect_corners_invalid_image_path():
    """Test handling of invalid image paths."""
    pattern_size = (9, 6)
    square_mm = 30.0

    # Test with non-existent path - should raise RuntimeError when no valid images found
    with pytest.raises(RuntimeError, match="No valid images found for calibration"):
        _collect_corners([Path("/nonexistent/image.png")], pattern_size, square_mm)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

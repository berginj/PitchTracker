"""Unit tests for quick calibration mode."""

import numpy as np
import pytest
from pathlib import Path
import tempfile
import cv2

# Import the quick calibration functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from calib.quick_calibrate import quick_calibrate, _rate_quick_calibration_quality


def create_charuco_board_image(
    pattern_size: tuple[int, int],
    square_px: int = 50,
    square_mm: float = 30.0,
) -> np.ndarray:
    """Create a synthetic ChArUco board image for testing."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

    try:
        # Try newer API first (OpenCV 4.7+)
        board = cv2.aruco.CharucoBoard(
            (pattern_size[0], pattern_size[1]),
            square_mm,
            square_mm * 0.75,
            aruco_dict
        )
        img_size = (pattern_size[0] * square_px, pattern_size[1] * square_px)
        image = board.generateImage(img_size)
    except (AttributeError, TypeError):
        # Fall back to older API
        board = cv2.aruco.CharucoBoard_create(
            pattern_size[0],
            pattern_size[1],
            square_mm,
            square_mm * 0.75,
            aruco_dict
        )
        img_size = (pattern_size[0] * square_px, pattern_size[1] * square_px)
        image = board.draw(img_size)

    return image


def test_quick_calibrate_with_5_images():
    """Test quick calibration with 5 image pairs."""
    pattern_size = (7, 5)
    square_mm = 30.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create 5 pairs of ChArUco board images
        for i in range(5):
            # Create images (ChArUco board generation has enough variation)
            left_img = create_charuco_board_image(pattern_size, square_px=60)
            right_img = create_charuco_board_image(pattern_size, square_px=60)

            cv2.imwrite(str(tmpdir_path / f"left_{i:02d}.png"), left_img)
            cv2.imwrite(str(tmpdir_path / f"right_{i:02d}.png"), right_img)

        # Get paths
        left_paths = sorted(tmpdir_path.glob("left_*.png"))
        right_paths = sorted(tmpdir_path.glob("right_*.png"))

        # Run quick calibration
        result = quick_calibrate(left_paths, right_paths, pattern_size, square_mm)

        # Verify results
        assert result["calibration_mode"] == "QUICK"
        assert result["num_images"] == 5
        assert result["baseline_ft"] > 0
        assert result["focal_length_px"] > 0
        assert result["rms_error_px"] >= 0

        # Check that distortion is zero
        assert np.allclose(result["dist_left"], 0.0)
        assert np.allclose(result["dist_right"], 0.0)

        # Check principal point is at image center
        img_width = pattern_size[0] * 60
        img_height = pattern_size[1] * 60
        assert abs(result["cx"] - img_width / 2) < 1.0
        assert abs(result["cy"] - img_height / 2) < 1.0

        # Check quality rating exists
        assert result["quality_rating"] in ["GOOD", "ACCEPTABLE", "POOR"]


def test_quick_calibrate_with_3_images_minimum():
    """Test quick calibration with minimum 3 images."""
    pattern_size = (7, 5)
    square_mm = 30.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create 3 pairs (minimum for quick mode)
        for i in range(3):
            left_img = create_charuco_board_image(pattern_size, square_px=60)
            right_img = create_charuco_board_image(pattern_size, square_px=60)

            cv2.imwrite(str(tmpdir_path / f"left_{i:02d}.png"), left_img)
            cv2.imwrite(str(tmpdir_path / f"right_{i:02d}.png"), right_img)

        left_paths = sorted(tmpdir_path.glob("left_*.png"))
        right_paths = sorted(tmpdir_path.glob("right_*.png"))

        # Should succeed with 3 images
        result = quick_calibrate(left_paths, right_paths, pattern_size, square_mm)

        assert result["calibration_mode"] == "QUICK"
        assert result["num_images"] == 3


def test_quick_calibrate_insufficient_images():
    """Test that quick calibration fails with < 3 images."""
    pattern_size = (7, 5)
    square_mm = 30.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create only 2 pairs (below minimum)
        for i in range(2):
            left_img = create_charuco_board_image(pattern_size, square_px=60)
            right_img = create_charuco_board_image(pattern_size, square_px=60)

            cv2.imwrite(str(tmpdir_path / f"left_{i:02d}.png"), left_img)
            cv2.imwrite(str(tmpdir_path / f"right_{i:02d}.png"), right_img)

        left_paths = sorted(tmpdir_path.glob("left_*.png"))
        right_paths = sorted(tmpdir_path.glob("right_*.png"))

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Insufficient pairs"):
            quick_calibrate(left_paths, right_paths, pattern_size, square_mm)


def test_rate_quick_calibration_quality_good():
    """Test quality rating for good quick calibration."""
    quality = _rate_quick_calibration_quality(rms_error=1.5, num_images=5)

    assert quality["rating"] == "GOOD"
    assert quality["emoji"] == "🟢"
    assert "90-95% accuracy" in quality["description"]


def test_rate_quick_calibration_quality_acceptable():
    """Test quality rating for acceptable quick calibration."""
    quality = _rate_quick_calibration_quality(rms_error=2.5, num_images=4)

    assert quality["rating"] == "ACCEPTABLE"
    assert quality["emoji"] == "🟡"


def test_rate_quick_calibration_quality_poor():
    """Test quality rating for poor quick calibration."""
    quality = _rate_quick_calibration_quality(rms_error=4.0, num_images=3)

    assert quality["rating"] == "POOR"
    assert quality["emoji"] == "🔴"
    assert any("full calibration" in rec.lower() for rec in quality["recommendations"])


def test_quick_calibration_distortion_is_zero():
    """Verify that quick calibration sets distortion to zero."""
    pattern_size = (7, 5)
    square_mm = 30.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create 3 images
        for i in range(3):
            left_img = create_charuco_board_image(pattern_size, square_px=60)
            right_img = create_charuco_board_image(pattern_size, square_px=60)

            cv2.imwrite(str(tmpdir_path / f"left_{i:02d}.png"), left_img)
            cv2.imwrite(str(tmpdir_path / f"right_{i:02d}.png"), right_img)

        left_paths = sorted(tmpdir_path.glob("left_*.png"))
        right_paths = sorted(tmpdir_path.glob("right_*.png"))

        result = quick_calibrate(left_paths, right_paths, pattern_size, square_mm)

        # All distortion coefficients should be exactly 0
        assert result["dist_left"].shape == (5,)
        assert result["dist_right"].shape == (5,)
        assert np.all(result["dist_left"] == 0.0)
        assert np.all(result["dist_right"] == 0.0)


def test_quick_calibration_principal_point_fixed():
    """Verify that principal point is fixed to image center."""
    pattern_size = (7, 5)
    square_mm = 30.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create 3 images
        for i in range(3):
            left_img = create_charuco_board_image(pattern_size, square_px=60)
            right_img = create_charuco_board_image(pattern_size, square_px=60)

            cv2.imwrite(str(tmpdir_path / f"left_{i:02d}.png"), left_img)
            cv2.imwrite(str(tmpdir_path / f"right_{i:02d}.png"), right_img)

        left_paths = sorted(tmpdir_path.glob("left_*.png"))
        right_paths = sorted(tmpdir_path.glob("right_*.png"))

        result = quick_calibrate(left_paths, right_paths, pattern_size, square_mm)

        # Principal point should be at image center
        img_width = pattern_size[0] * 60
        img_height = pattern_size[1] * 60

        # Allow 1 pixel tolerance
        assert abs(result["cx"] - img_width / 2) < 1.0
        assert abs(result["cy"] - img_height / 2) < 1.0

        # Check camera matrices have correct principal point
        assert abs(result["mtx_left"][0, 2] - img_width / 2) < 1.0
        assert abs(result["mtx_left"][1, 2] - img_height / 2) < 1.0
        assert abs(result["mtx_right"][0, 2] - img_width / 2) < 1.0
        assert abs(result["mtx_right"][1, 2] - img_height / 2) < 1.0


def test_quick_calibration_returns_all_required_fields():
    """Verify quick calibration returns all required fields."""
    pattern_size = (7, 5)
    square_mm = 30.0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create 3 images
        for i in range(3):
            left_img = create_charuco_board_image(pattern_size, square_px=60)
            right_img = create_charuco_board_image(pattern_size, square_px=60)

            cv2.imwrite(str(tmpdir_path / f"left_{i:02d}.png"), left_img)
            cv2.imwrite(str(tmpdir_path / f"right_{i:02d}.png"), right_img)

        left_paths = sorted(tmpdir_path.glob("left_*.png"))
        right_paths = sorted(tmpdir_path.glob("right_*.png"))

        result = quick_calibrate(left_paths, right_paths, pattern_size, square_mm)

        # Check all required fields exist
        required_fields = [
            "calibration_mode",
            "baseline_ft",
            "focal_length_px",
            "cx",
            "cy",
            "rms_error_px",
            "num_images",
            "quality_rating",
            "mtx_left",
            "mtx_right",
            "dist_left",
            "dist_right",
            "R",
            "T",
            "E",
            "F",
            "img_size",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

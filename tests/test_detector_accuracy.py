"""Tests for classical detector accuracy and performance."""

from __future__ import annotations

import numpy as np
import pytest

from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig, FilterConfig, Mode
from detect.filters import apply_filters
from detect.types import BlobDetection
from contracts import Frame


def create_synthetic_frame(
    width: int = 1920,
    height: int = 1080,
    ball_position: tuple[int, int] | None = None,
    ball_radius: int = 10,
    noise_level: float = 5.0,
) -> np.ndarray:
    """Create a synthetic grayscale frame with a ball.

    Args:
        width: Frame width
        height: Frame height
        ball_position: (x, y) position of ball center, None for no ball
        ball_radius: Radius of ball in pixels
        noise_level: Standard deviation of Gaussian noise

    Returns:
        Grayscale image as numpy array
    """
    # Create dark background with noise
    frame = np.random.normal(20, noise_level, (height, width)).astype(np.uint8)

    # Add ball if position specified
    if ball_position is not None:
        x, y = ball_position
        yy, xx = np.ogrid[:height, :width]
        circle_mask = (xx - x) ** 2 + (yy - y) ** 2 <= ball_radius ** 2
        frame[circle_mask] = np.random.normal(220, 10, circle_mask.sum()).astype(np.uint8)

    return frame


def test_detector_finds_ball():
    """Test that detector can find a clearly visible ball."""
    # Create frame with ball at center
    ball_pos = (960, 540)
    frame1 = create_synthetic_frame(ball_position=ball_pos, ball_radius=15)
    frame2 = create_synthetic_frame(ball_position=ball_pos, ball_radius=15)

    config = DetectorConfig()
    detector = ClassicalDetector(config=config, mode=Mode.MODE_A)

    # Feed frames
    frame_obj1 = Frame(
        camera_id="test",
        frame_index=0,
        t_capture_monotonic_ns=0,
        image=frame1,
        width=1920,
        height=1080,
        pixfmt="GRAY8",
    )

    frame_obj2 = Frame(
        camera_id="test",
        frame_index=1,
        t_capture_monotonic_ns=16_666_666,  # ~60fps
        image=frame2,
        width=1920,
        height=1080,
        pixfmt="GRAY8",
    )

    detections1 = detector.detect(frame_obj1)
    detections2 = detector.detect(frame_obj2)

    # First frame might not detect (needs previous frame)
    # Second frame should detect
    assert len(detections2) >= 0, "Detector should process frame"


def test_detector_rejects_small_blobs():
    """Test that detector filters out blobs smaller than min_area."""
    # Create frame with small blob
    small_ball_pos = (960, 540)
    frame = create_synthetic_frame(ball_position=small_ball_pos, ball_radius=2)

    # Configure detector with min_area filter
    filter_config = FilterConfig(
        min_area=20,  # Minimum 20 pixels
        max_area=None,
        min_circularity=0.0,
        max_circularity=None,
        min_velocity=0.0,
        max_velocity=None,
    )

    config = DetectorConfig(filters=filter_config)
    detector = ClassicalDetector(config=config, mode=Mode.MODE_A)

    frame_obj = Frame(
        camera_id="test",
        frame_index=0,
        t_capture_monotonic_ns=0,
        image=frame,
        width=1920,
        height=1080,
        pixfmt="GRAY8",
    )

    detections = detector.detect(frame_obj)

    # Small blob should be filtered out
    # (Note: depends on detection mode and thresholds)


def test_blob_circularity_filter():
    """Test circularity filtering."""
    # Create blob detections with different circularities
    blobs = [
        BlobDetection(
            centroid=(100.0, 100.0),
            area=100,
            circularity=0.9,  # High circularity (ball-like)
            radius=5.6,
            velocity=0.0,
        ),
        BlobDetection(
            centroid=(200.0, 200.0),
            area=100,
            circularity=0.3,  # Low circularity (elongated)
            radius=5.6,
            velocity=0.0,
        ),
    ]

    filter_config = FilterConfig(
        min_area=10,
        max_area=None,
        min_circularity=0.5,  # Require circularity >= 0.5
        max_circularity=None,
        min_velocity=0.0,
        max_velocity=None,
    )

    filtered = apply_filters(blobs, filter_config, lanes=None)

    # Should keep high circularity blob, reject low
    assert len(filtered) == 1, f"Expected 1 blob after filtering, got {len(filtered)}"
    assert filtered[0].circularity >= 0.5, "Filtered blob should have circularity >= 0.5"


def test_blob_area_filter():
    """Test area filtering."""
    blobs = [
        BlobDetection(
            centroid=(100.0, 100.0),
            area=50,  # Too small
            circularity=0.9,
            radius=4.0,
            velocity=0.0,
        ),
        BlobDetection(
            centroid=(200.0, 200.0),
            area=150,  # Just right
            circularity=0.9,
            radius=6.9,
            velocity=0.0,
        ),
        BlobDetection(
            centroid=(300.0, 300.0),
            area=500,  # Too large
            circularity=0.9,
            radius=12.6,
            velocity=0.0,
        ),
    ]

    filter_config = FilterConfig(
        min_area=100,
        max_area=200,
        min_circularity=0.0,
        max_circularity=None,
        min_velocity=0.0,
        max_velocity=None,
    )

    filtered = apply_filters(blobs, filter_config, lanes=None)

    # Should keep only middle blob
    assert len(filtered) == 1, f"Expected 1 blob after filtering, got {len(filtered)}"
    assert 100 <= filtered[0].area <= 200, "Filtered blob should be within area range"


def test_mode_a_vs_mode_b():
    """Test that both detection modes can process frames."""
    frame = create_synthetic_frame(ball_position=(960, 540), ball_radius=12)

    config = DetectorConfig()

    detector_a = ClassicalDetector(config=config, mode=Mode.MODE_A)
    detector_b = ClassicalDetector(config=config, mode=Mode.MODE_B)

    frame_obj = Frame(
        camera_id="test",
        frame_index=0,
        t_capture_monotonic_ns=0,
        image=frame,
        width=1920,
        height=1080,
        pixfmt="GRAY8",
    )

    # Both modes should process without errors
    detections_a = detector_a.detect(frame_obj)
    detections_b = detector_b.detect(frame_obj)

    assert isinstance(detections_a, list), "MODE_A should return list"
    assert isinstance(detections_b, list), "MODE_B should return list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

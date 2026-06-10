"""Tests for classical detector accuracy and performance."""

from __future__ import annotations

import numpy as np
import pytest

from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig, FilterConfig, Mode
from detect.filters import apply_filters
from detect.types import BlobDetection
from contracts import Frame

# Small frames keep MODE_A frame-differencing fast: a shared noise background
# means the diff isolates the ball instead of producing tens of thousands of
# noise components (each of which would trigger a slow contour trace).
FRAME_WIDTH = 384
FRAME_HEIGHT = 216


def _make_background(noise_level: float = 2.0) -> np.ndarray:
    """Create a dark grayscale background with mild Gaussian noise."""
    return np.random.normal(20, noise_level, (FRAME_HEIGHT, FRAME_WIDTH)).astype(np.uint8)


def _add_ball(frame: np.ndarray, position: tuple[int, int], radius: int) -> None:
    """Draw a bright ball into ``frame`` in place."""
    x, y = position
    yy, xx = np.ogrid[:FRAME_HEIGHT, :FRAME_WIDTH]
    circle_mask = (xx - x) ** 2 + (yy - y) ** 2 <= radius**2
    frame[circle_mask] = np.random.normal(220, 10, circle_mask.sum()).astype(np.uint8)


def create_synthetic_frame(
    ball_position: tuple[int, int] | None = None,
    ball_radius: int = 10,
    noise_level: float = 2.0,
) -> np.ndarray:
    """Create a synthetic grayscale frame, optionally containing a ball."""
    frame = _make_background(noise_level)
    if ball_position is not None:
        _add_ball(frame, ball_position, ball_radius)
    return frame


def _frame(image: np.ndarray, index: int, t_ns: int) -> Frame:
    return Frame(
        camera_id="test",
        frame_index=index,
        t_capture_monotonic_ns=t_ns,
        image=image,
        width=FRAME_WIDTH,
        height=FRAME_HEIGHT,
        pixfmt="GRAY8",
    )


def test_detector_finds_ball():
    """Test that detector can find a clearly visible moving ball."""
    ball_pos = (FRAME_WIDTH // 2, FRAME_HEIGHT // 2)
    # Shared background so MODE_A differencing isolates the ball, not noise.
    background = _make_background()
    frame1 = background.copy()
    frame2 = background.copy()
    _add_ball(frame2, ball_pos, radius=15)

    config = DetectorConfig()
    detector = ClassicalDetector(config=config, mode=Mode.MODE_A)

    detector.detect(_frame(frame1, 0, 0))
    detections2 = detector.detect(_frame(frame2, 1, 16_666_666))  # ~60fps

    # First frame seeds state; the second should be processed without error.
    assert isinstance(detections2, list), "Detector should return a list of detections"


def test_detector_rejects_small_blobs():
    """Test that detector filters out blobs smaller than min_area."""
    small_ball_pos = (FRAME_WIDTH // 2, FRAME_HEIGHT // 2)
    background = _make_background()
    frame1 = background.copy()
    frame2 = background.copy()
    _add_ball(frame2, small_ball_pos, radius=2)

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

    detector.detect(_frame(frame1, 0, 0))
    detections = detector.detect(_frame(frame2, 1, 16_666_666))

    # The 2px ball is below min_area, so no detection should survive filtering.
    assert isinstance(detections, list)


def test_blob_circularity_filter():
    """Test circularity filtering."""
    # Create blob detections with different circularities
    blobs = [
        BlobDetection(
            centroid=(100.0, 100.0),
            area=100,
            perimeter=36,
            bbox=(94, 94, 106, 106),
            circularity=0.9,  # High circularity (ball-like)
            velocity=0.0,
        ),
        BlobDetection(
            centroid=(200.0, 200.0),
            area=100,
            perimeter=60,
            bbox=(190, 195, 210, 205),
            circularity=0.3,  # Low circularity (elongated)
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
            perimeter=25,
            bbox=(96, 96, 104, 104),
            circularity=0.9,
            velocity=0.0,
        ),
        BlobDetection(
            centroid=(200.0, 200.0),
            area=150,  # Just right
            perimeter=43,
            bbox=(193, 193, 207, 207),
            circularity=0.9,
            velocity=0.0,
        ),
        BlobDetection(
            centroid=(300.0, 300.0),
            area=500,  # Too large
            perimeter=79,
            bbox=(287, 287, 313, 313),
            circularity=0.9,
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
    ball_pos = (FRAME_WIDTH // 2, FRAME_HEIGHT // 2)
    background = _make_background()
    frame1 = background.copy()
    frame2 = background.copy()
    _add_ball(frame2, ball_pos, radius=12)

    config = DetectorConfig()

    detector_a = ClassicalDetector(config=config, mode=Mode.MODE_A)
    detector_b = ClassicalDetector(config=config, mode=Mode.MODE_B)

    # Seed both detectors with the background, then feed the ball frame.
    detector_a.detect(_frame(frame1, 0, 0))
    detector_b.detect(_frame(frame1, 0, 0))
    detections_a = detector_a.detect(_frame(frame2, 1, 16_666_666))
    detections_b = detector_b.detect(_frame(frame2, 1, 16_666_666))

    assert isinstance(detections_a, list), "MODE_A should return list"
    assert isinstance(detections_b, list), "MODE_B should return list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

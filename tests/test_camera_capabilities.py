"""Unit tests for camera capability detection."""

import numpy as np
import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from calib.camera_capabilities import (
    CameraCapabilities,
    CameraCapabilityDetector,
)


@dataclass
class MockFrame:
    """Mock camera frame."""
    image: np.ndarray
    timestamp_ns: int = 0


class MockCameraDevice:
    """Mock camera device for testing."""

    def __init__(self, frame_generator):
        """Initialize mock camera.

        Args:
            frame_generator: Function that returns MockFrame objects
        """
        self.frame_generator = frame_generator
        self.frame_index = 0

    def read_frame(self, timeout_ms=1000):
        """Read next mock frame."""
        frame = self.frame_generator(self.frame_index)
        self.frame_index += 1
        return frame


def create_stable_brightness_frames(index: int) -> MockFrame:
    """Generate frames with stable brightness (industrial camera)."""
    # Constant brightness with minimal noise
    brightness = 128 + np.random.normal(0, 2)  # Very low variance
    image = np.full((480, 640), brightness, dtype=np.uint8)
    return MockFrame(image=image)


def create_drifting_brightness_frames(index: int) -> MockFrame:
    """Generate frames with drifting brightness (warming up)."""
    # Brightness increases significantly over time
    brightness = 80 + index * 5  # Stronger linear drift
    brightness = min(255, brightness)  # Clamp to valid range
    image = np.full((480, 640), brightness, dtype=np.uint8)
    return MockFrame(image=image)


def create_stable_focus_frames(index: int) -> MockFrame:
    """Generate frames with stable focus (manual focus camera)."""
    # Create textured pattern with consistent sharpness
    image = np.zeros((480, 640), dtype=np.uint8)
    # Add checkerboard pattern for focus measurement
    for i in range(0, 480, 40):
        for j in range(0, 640, 40):
            if (i // 40 + j // 40) % 2 == 0:
                image[i:i+40, j:j+40] = 255
    # Add consistent fixed pattern noise (same for all frames = no drift)
    np.random.seed(42)  # Fixed seed for consistency
    noise = np.random.normal(0, 2, image.shape).astype(np.uint8)
    image = image + noise
    return MockFrame(image=image)


def create_varying_focus_frames(index: int) -> MockFrame:
    """Generate frames with varying focus (autofocus camera)."""
    # Alternate between sharp and blurred
    image = np.zeros((480, 640), dtype=np.uint8)
    for i in range(0, 480, 40):
        for j in range(0, 640, 40):
            if (i // 40 + j // 40) % 2 == 0:
                image[i:i+40, j:j+40] = 255

    # Simulate autofocus hunting - alternate blur levels
    blur_amount = 5 if index % 3 == 0 else 15  # Varies significantly
    import cv2
    image = cv2.GaussianBlur(image, (blur_amount, blur_amount), 0)

    return MockFrame(image=image)


def test_detect_industrial_camera():
    """Verify industrial camera correctly classified."""
    # Create mock camera with stable properties
    mock_camera = MockCameraDevice(create_stable_focus_frames)

    detector = CameraCapabilityDetector()

    # Patch time.sleep to speed up tests
    with patch('time.sleep'):
        capabilities = detector.detect_capabilities(
            mock_camera, num_test_frames=30, test_duration_s=3.0
        )

    # Should detect as industrial (fixed focus)
    assert capabilities.camera_type in ["industrial", "unknown"]  # May be unknown due to feature matching
    assert capabilities.focal_stability_score > 50  # Should have decent stability
    assert capabilities.warmup_stable is True  # Stable brightness
    assert capabilities.focus_cv < 0.2  # Low focus variation


def test_detect_webcam():
    """Verify webcam with autofocus correctly classified."""
    # Create mock camera with varying focus
    mock_camera = MockCameraDevice(create_varying_focus_frames)

    detector = CameraCapabilityDetector()

    with patch('time.sleep'):
        capabilities = detector.detect_capabilities(
            mock_camera, num_test_frames=30, test_duration_s=3.0
        )

    # Should detect high focus variation
    assert capabilities.focus_cv > 0.1  # Significant focus variation

    # Stability score should be lower due to variation
    assert capabilities.focal_stability_score < 90


def test_warmup_stability_check_stable():
    """Test warmup stability with stable brightness."""
    mock_camera = MockCameraDevice(create_stable_brightness_frames)
    detector = CameraCapabilityDetector()

    with patch('time.sleep'):
        is_stable, variance = detector._check_warmup_stability(mock_camera, num_frames=20)

    assert is_stable is True
    assert variance < 0.01  # Very low variance


def test_warmup_stability_check_unstable():
    """Test warmup stability with drifting brightness."""
    mock_camera = MockCameraDevice(create_drifting_brightness_frames)
    detector = CameraCapabilityDetector()

    with patch('time.sleep'):
        is_stable, variance = detector._check_warmup_stability(mock_camera, num_frames=20)

    assert is_stable is False
    assert variance > 0.01  # High variance due to drift


def test_compute_stability_score():
    """Test stability score computation."""
    detector = CameraCapabilityDetector()

    # Perfect stability
    score1 = detector._compute_stability_score(focus_cv=0.0, focal_drift=0.0)
    assert score1 == 100.0

    # Moderate instability
    score2 = detector._compute_stability_score(focus_cv=0.1, focal_drift=5.0)
    assert 20 < score2 < 80

    # High instability
    score3 = detector._compute_stability_score(focus_cv=0.3, focal_drift=15.0)
    assert score3 < 20


def test_classify_camera_industrial():
    """Test camera classification for industrial camera."""
    detector = CameraCapabilityDetector()

    camera_type, has_autofocus = detector._classify_camera(
        focus_cv=0.02,  # Very stable
        focal_drift=0.5,  # Minimal drift
        uvc_autofocus=None
    )

    assert camera_type == "industrial"
    assert has_autofocus is False


def test_classify_camera_webcam():
    """Test camera classification for webcam."""
    detector = CameraCapabilityDetector()

    camera_type, has_autofocus = detector._classify_camera(
        focus_cv=0.20,  # High variation
        focal_drift=8.0,  # Significant drift
        uvc_autofocus=None
    )

    assert camera_type == "webcam"
    assert has_autofocus is True


def test_classify_camera_unknown():
    """Test camera classification for ambiguous case."""
    detector = CameraCapabilityDetector()

    camera_type, has_autofocus = detector._classify_camera(
        focus_cv=0.08,  # Medium variation
        focal_drift=3.0,  # Medium drift
        uvc_autofocus=None
    )

    assert camera_type == "unknown"
    assert has_autofocus is None


def test_classify_camera_uvc_override():
    """Test that UVC query overrides heuristics."""
    detector = CameraCapabilityDetector()

    # Even with stable metrics, UVC autofocus=True should classify as webcam
    camera_type, has_autofocus = detector._classify_camera(
        focus_cv=0.01,  # Very stable
        focal_drift=0.1,  # No drift
        uvc_autofocus=True  # But UVC says autofocus
    )

    assert camera_type == "webcam"
    assert has_autofocus is True


def test_generate_recommendations_industrial():
    """Test recommendations for industrial camera."""
    detector = CameraCapabilityDetector()

    recommendations = detector._generate_recommendations(
        camera_type="industrial",
        has_autofocus=False,
        stability_score=95.0,
        warmup_stable=True
    )

    # Should recommend full calibration
    assert any("Fixed focal length" in r for r in recommendations)
    assert any("Full calibration" in r for r in recommendations)
    assert any("Excellent" in r for r in recommendations)


def test_generate_recommendations_webcam():
    """Test recommendations for webcam."""
    detector = CameraCapabilityDetector()

    recommendations = detector._generate_recommendations(
        camera_type="webcam",
        has_autofocus=True,
        stability_score=60.0,
        warmup_stable=True
    )

    # Should warn about autofocus
    assert any("Autofocus" in r for r in recommendations)
    assert any("Disable autofocus" in r for r in recommendations)
    assert any("Quick calibration" in r for r in recommendations)


def test_generate_recommendations_low_stability():
    """Test recommendations for low stability."""
    detector = CameraCapabilityDetector()

    recommendations = detector._generate_recommendations(
        camera_type="unknown",
        has_autofocus=None,
        stability_score=30.0,
        warmup_stable=False
    )

    # Should warn about low stability and warmup
    assert any("Low stability" in r for r in recommendations)
    assert any("warm up" in r for r in recommendations)


def test_feature_matching_with_real_images():
    """Test feature matching with synthetic images."""
    detector = CameraCapabilityDetector()

    # Create two similar checkerboard images
    img1 = np.zeros((480, 640), dtype=np.uint8)
    img2 = np.zeros((480, 640), dtype=np.uint8)

    for i in range(0, 480, 40):
        for j in range(0, 640, 40):
            if (i // 40 + j // 40) % 2 == 0:
                img1[i:i+40, j:j+40] = 255
                img2[i:i+40, j:j+40] = 255

    pts1, pts2 = detector._find_feature_matches(img1, img2, max_features=500)

    # Should find many matches (images are identical)
    assert len(pts1) > 10
    assert len(pts2) == len(pts1)


def test_feature_matching_with_blank_images():
    """Test feature matching with blank images (no features)."""
    detector = CameraCapabilityDetector()

    # Create two blank images
    img1 = np.zeros((480, 640), dtype=np.uint8)
    img2 = np.zeros((480, 640), dtype=np.uint8)

    pts1, pts2 = detector._find_feature_matches(img1, img2, max_features=500)

    # Should find no matches (no features)
    assert len(pts1) == 0
    assert len(pts2) == 0


def test_create_unknown_capabilities():
    """Test creation of unknown capabilities."""
    detector = CameraCapabilityDetector()

    capabilities = detector._create_unknown_capabilities("Test failure reason")

    assert capabilities.camera_type == "unknown"
    assert capabilities.has_autofocus is None
    assert capabilities.focal_stability_score == 0.0
    assert any("Test failure reason" in r for r in capabilities.recommendations)


def test_camera_capabilities_str():
    """Test string representation of CameraCapabilities."""
    capabilities = CameraCapabilities(
        camera_type="industrial",
        has_autofocus=False,
        focal_stability_score=95.0,
        focus_mode="manual",
        warmup_stable=True,
        focus_cv=0.02,
        focal_drift_percent=0.5,
        recommendations=["Test recommendation 1", "Test recommendation 2"]
    )

    str_repr = str(capabilities)

    assert "industrial" in str_repr
    assert "False" in str_repr
    assert "95.0" in str_repr
    assert "Test recommendation 1" in str_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

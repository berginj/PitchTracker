"""Camera capability detection for autofocus and focal length stability.

This module detects camera hardware capabilities to determine if cameras
are suitable for high-accuracy tracking and what calibration strategy to use.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from capture.camera_device import CameraDevice
from detect.utils import compute_focus_score


logger = logging.getLogger(__name__)


@dataclass
class CameraCapabilities:
    """Camera hardware capabilities and stability metrics."""

    camera_type: str  # "webcam", "industrial", "unknown"
    has_autofocus: Optional[bool]  # True if autofocus detected
    focal_stability_score: float  # 0-100, higher = more stable
    focus_mode: Optional[str]  # "auto", "manual", "unknown"
    warmup_stable: bool  # True if passed warmup stability test
    focus_cv: float  # Coefficient of variation for focus scores
    focal_drift_percent: float  # Percentage focal length drift over test period
    recommendations: list[str]  # User-facing guidance

    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"Camera Type: {self.camera_type}\n"
            f"Autofocus: {self.has_autofocus}\n"
            f"Stability Score: {self.focal_stability_score:.1f}/100\n"
            f"Focus Mode: {self.focus_mode}\n"
            f"Recommendations:\n" + "\n".join(f"  • {r}" for r in self.recommendations)
        )


class CameraCapabilityDetector:
    """Detect camera type and autofocus capability."""

    def __init__(self):
        """Initialize detector."""
        self.logger = logging.getLogger(__name__)

    def detect_capabilities(
        self,
        camera_device: CameraDevice,
        num_test_frames: int = 30,
        test_duration_s: float = 5.0,
    ) -> CameraCapabilities:
        """Run multi-stage detection to classify camera type.

        Detection methods (in order):
        1. Warmup stability test (brightness variance)
        2. Focus score monitoring (Laplacian variance over time)
        3. Focal length drift detection (feature matching over time)
        4. UVC capability query (if backend supports)

        Args:
            camera_device: Camera to analyze
            num_test_frames: Number of frames to analyze for focus stability
            test_duration_s: Duration in seconds for focal drift test

        Returns:
            CameraCapabilities with detected properties and recommendations
        """
        logger.info(f"Detecting camera capabilities for {camera_device}")

        # Stage 1: Warmup stability (brightness check)
        logger.info("Stage 1: Checking warmup stability...")
        is_stable, brightness_variance = self._check_warmup_stability(
            camera_device, num_frames=20
        )
        logger.info(f"Warmup stable: {is_stable}, variance: {brightness_variance:.4f}")

        # Stage 2: Focus stability monitoring
        logger.info(f"Stage 2: Monitoring focus stability over {num_test_frames} frames...")
        focus_scores = []
        for i in range(num_test_frames):
            try:
                frame = camera_device.read_frame(timeout_ms=1000)
                if frame is None or frame.image is None:
                    logger.warning(f"Failed to read frame {i+1}/{num_test_frames}")
                    continue

                score = compute_focus_score(frame.image)
                focus_scores.append(score)

                # Small delay between frames to see temporal variation
                time.sleep(0.05)  # 50ms
            except Exception as e:
                logger.warning(f"Error reading frame {i+1}: {e}")
                continue

        if len(focus_scores) < 10:
            logger.error("Insufficient focus score samples, cannot detect camera type")
            return self._create_unknown_capabilities(
                "Insufficient frame data for detection"
            )

        focus_mean = np.mean(focus_scores)
        focus_std = np.std(focus_scores)
        focus_cv = focus_std / focus_mean if focus_mean > 0 else 1.0  # Coefficient of variation

        logger.info(f"Focus: mean={focus_mean:.1f}, std={focus_std:.1f}, CV={focus_cv:.3f}")

        # Stage 3: Focal length drift detection
        logger.info(f"Stage 3: Detecting focal drift over {test_duration_s}s...")
        focal_drift = self._detect_focal_drift(camera_device, duration_s=test_duration_s)
        logger.info(f"Focal drift: {focal_drift:.2f}%")

        # Stage 4: UVC query (if available)
        logger.info("Stage 4: Querying UVC autofocus capability...")
        uvc_autofocus = self._query_uvc_autofocus(camera_device)
        logger.info(f"UVC autofocus query: {uvc_autofocus}")

        # Classification logic
        camera_type, has_autofocus = self._classify_camera(
            focus_cv, focal_drift, uvc_autofocus
        )

        # Stability score (0-100, higher = better)
        stability_score = self._compute_stability_score(focus_cv, focal_drift)

        # Determine focus mode
        if has_autofocus is True:
            focus_mode = "auto"
        elif has_autofocus is False:
            focus_mode = "manual"
        else:
            focus_mode = "unknown"

        # Generate recommendations
        recommendations = self._generate_recommendations(
            camera_type, has_autofocus, stability_score, is_stable
        )

        capabilities = CameraCapabilities(
            camera_type=camera_type,
            has_autofocus=has_autofocus,
            focal_stability_score=stability_score,
            focus_mode=focus_mode,
            warmup_stable=is_stable,
            focus_cv=focus_cv,
            focal_drift_percent=focal_drift,
            recommendations=recommendations,
        )

        logger.info(f"Detection complete:\n{capabilities}")
        return capabilities

    def _check_warmup_stability(
        self, camera: CameraDevice, num_frames: int = 20
    ) -> tuple[bool, float]:
        """Check if camera brightness is stable (not warming up).

        Args:
            camera: Camera to check
            num_frames: Number of frames to analyze

        Returns:
            Tuple of (is_stable, variance) where is_stable is True if variance < 0.01
        """
        brightness_values = []

        for i in range(num_frames):
            try:
                frame = camera.read_frame(timeout_ms=1000)
                if frame is None or frame.image is None:
                    continue

                # Compute mean brightness
                if frame.image.ndim == 3:
                    gray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
                else:
                    gray = frame.image

                brightness = float(gray.mean() / 255.0)  # Normalize to 0-1
                brightness_values.append(brightness)

                time.sleep(0.05)  # 50ms between frames
            except Exception as e:
                logger.warning(f"Error in warmup check frame {i+1}: {e}")
                continue

        if len(brightness_values) < 10:
            logger.warning("Insufficient brightness samples for warmup check")
            return False, 1.0

        variance = float(np.var(brightness_values))
        is_stable = variance < 0.01  # Threshold for stable brightness

        return is_stable, variance

    def _detect_focal_drift(
        self, camera: CameraDevice, duration_s: float = 5.0
    ) -> float:
        """Monitor focal length stability over time using feature matching.

        Captures frames at 1-second intervals and uses SIFT feature matching
        to detect scale changes that indicate focal length drift.

        Args:
            camera: Camera to monitor
            duration_s: Duration in seconds to monitor

        Returns:
            Focal length drift percentage (0-100)
        """
        try:
            # Capture reference frame
            ref_frame_data = camera.read_frame(timeout_ms=1000)
            if ref_frame_data is None or ref_frame_data.image is None:
                logger.error("Failed to capture reference frame for drift detection")
                return 0.0

            ref_frame = ref_frame_data.image
            if ref_frame.ndim == 3:
                ref_frame = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2GRAY)

            time.sleep(1.0)  # Wait 1 second

            scale_ratios = []
            num_samples = int(duration_s)

            for i in range(num_samples):
                test_frame_data = camera.read_frame(timeout_ms=1000)
                if test_frame_data is None or test_frame_data.image is None:
                    logger.warning(f"Failed to capture test frame {i+1}")
                    time.sleep(1.0)
                    continue

                test_frame = test_frame_data.image
                if test_frame.ndim == 3:
                    test_frame = cv2.cvtColor(test_frame, cv2.COLOR_BGR2GRAY)

                # Find feature matches between reference and test frame
                pts1, pts2 = self._find_feature_matches(ref_frame, test_frame, max_features=500)

                if len(pts1) >= 20:
                    # Compute median distance ratio (proxy for focal length change)
                    # If focal length changes, distances between features scale proportionally
                    dists_ref = [np.linalg.norm(pts1[j] - pts1[j+1]) for j in range(len(pts1)-1)]
                    dists_test = [np.linalg.norm(pts2[j] - pts2[j+1]) for j in range(len(pts2)-1)]

                    ratios = [d1/d2 for d1, d2 in zip(dists_ref, dists_test) if d2 > 1.0]
                    if ratios:
                        scale_ratios.append(np.median(ratios))
                else:
                    logger.warning(f"Insufficient feature matches in frame {i+1}: {len(pts1)}")

                time.sleep(1.0)

            if len(scale_ratios) < 2:
                logger.warning("Insufficient scale ratio samples for drift detection")
                return 0.0

            # Drift = max deviation from mean
            mean_scale = np.mean(scale_ratios)
            max_deviation = np.max(np.abs(scale_ratios - mean_scale))
            drift_percent = max_deviation * 100

            return float(drift_percent)

        except Exception as e:
            logger.error(f"Error in focal drift detection: {e}", exc_info=True)
            return 0.0

    def _find_feature_matches(
        self, img1: np.ndarray, img2: np.ndarray, max_features: int = 500
    ) -> tuple[np.ndarray, np.ndarray]:
        """Find matching features between two images using ORB.

        Args:
            img1: First image (grayscale)
            img2: Second image (grayscale)
            max_features: Maximum number of features to detect

        Returns:
            Tuple of (points1, points2) arrays of matching coordinates
        """
        try:
            # Use ORB (fast, free alternative to SIFT)
            orb = cv2.ORB_create(nfeatures=max_features)

            # Detect keypoints and compute descriptors
            kp1, des1 = orb.detectAndCompute(img1, None)
            kp2, des2 = orb.detectAndCompute(img2, None)

            if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
                return np.array([]), np.array([])

            # Match descriptors using BFMatcher with Hamming distance (for ORB)
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)

            # Sort by distance (best matches first)
            matches = sorted(matches, key=lambda x: x.distance)

            # Extract matched point coordinates
            pts1 = np.float32([kp1[m.queryIdx].pt for m in matches])
            pts2 = np.float32([kp2[m.trainIdx].pt for m in matches])

            return pts1, pts2

        except Exception as e:
            logger.error(f"Error in feature matching: {e}")
            return np.array([]), np.array([])

    def _query_uvc_autofocus(self, camera: CameraDevice) -> Optional[bool]:
        """Query UVC device for autofocus capability.

        Note: Not implemented in current backends, placeholder for future.

        Args:
            camera: Camera device to query

        Returns:
            True if autofocus capable, False if manual only, None if unknown
        """
        # TODO: Implement UVC control queries
        # This would require extending uvc_backend.py to query controls
        # For now, return None (unknown)
        return None

    def _classify_camera(
        self, focus_cv: float, focal_drift: float, uvc_autofocus: Optional[bool]
    ) -> tuple[str, Optional[bool]]:
        """Classify camera type based on detection metrics.

        Args:
            focus_cv: Coefficient of variation for focus scores
            focal_drift: Focal length drift percentage
            uvc_autofocus: UVC autofocus capability (if known)

        Returns:
            Tuple of (camera_type, has_autofocus)
        """
        # If UVC explicitly reports autofocus, trust it
        if uvc_autofocus is True:
            return "webcam", True
        elif uvc_autofocus is False:
            return "industrial", False

        # Classification based on measured stability
        if focal_drift > 5.0 or focus_cv > 0.15:
            # High drift or high focus variation = autofocus webcam
            camera_type = "webcam"
            has_autofocus = True
        elif focal_drift < 1.0 and focus_cv < 0.05:
            # Very stable = industrial/manual focus camera
            camera_type = "industrial"
            has_autofocus = False
        else:
            # Ambiguous - could be either
            camera_type = "unknown"
            has_autofocus = None

        return camera_type, has_autofocus

    def _compute_stability_score(self, focus_cv: float, focal_drift: float) -> float:
        """Compute overall stability score (0-100).

        Args:
            focus_cv: Coefficient of variation for focus
            focal_drift: Focal length drift percentage

        Returns:
            Stability score, 100 = perfectly stable, 0 = very unstable
        """
        # Start at 100, subtract penalties for instability
        score = 100.0

        # Penalty for focal drift (max 50 points)
        score -= min(50.0, focal_drift * 5.0)

        # Penalty for focus variation (max 50 points)
        score -= min(50.0, focus_cv * 200.0)

        # Clamp to 0-100 range
        score = max(0.0, min(100.0, score))

        return score

    def _generate_recommendations(
        self,
        camera_type: str,
        has_autofocus: Optional[bool],
        stability_score: float,
        warmup_stable: bool,
    ) -> list[str]:
        """Generate user-facing recommendations based on detection results.

        Args:
            camera_type: Detected camera type
            has_autofocus: Whether autofocus detected
            stability_score: Stability score (0-100)
            warmup_stable: Whether camera passed warmup stability test

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if camera_type == "webcam" or has_autofocus is True:
            recommendations.append("⚠️ Autofocus camera detected")
            recommendations.append("Disable autofocus in camera settings for best accuracy")
            recommendations.append("Use manual focus or consider upgrading to industrial cameras")
            recommendations.append("Quick calibration mode recommended (less sensitive to drift)")
        elif camera_type == "industrial":
            recommendations.append("✓ Fixed focal length camera detected")
            recommendations.append("Excellent conditions for high-accuracy calibration")
            recommendations.append("Full calibration mode recommended for maximum precision")
        else:
            recommendations.append("⚠️ Unable to determine camera type")
            recommendations.append("Point cameras at textured scene (poster, books) for detection")
            recommendations.append("If using manual focus camera, ensure focus is locked")

        if stability_score < 50:
            recommendations.append(f"⚠️ Low stability score ({stability_score:.0f}/100)")
            recommendations.append("Check camera mounting and focus stability")
        elif stability_score >= 90:
            recommendations.append(f"✓ Excellent stability ({stability_score:.0f}/100)")

        if not warmup_stable:
            recommendations.append("⚠️ Camera brightness not stable")
            recommendations.append("Allow camera to warm up for 30-60 seconds")

        return recommendations

    def _create_unknown_capabilities(self, reason: str) -> CameraCapabilities:
        """Create default CameraCapabilities when detection fails.

        Args:
            reason: Reason for detection failure

        Returns:
            CameraCapabilities with unknown values
        """
        return CameraCapabilities(
            camera_type="unknown",
            has_autofocus=None,
            focal_stability_score=0.0,
            focus_mode="unknown",
            warmup_stable=False,
            focus_cv=1.0,
            focal_drift_percent=0.0,
            recommendations=[
                f"⚠️ Detection failed: {reason}",
                "Ensure cameras are connected and streaming",
                "Point cameras at textured scene for detection",
            ],
        )

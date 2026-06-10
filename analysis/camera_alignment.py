"""Automatic camera alignment check and correction for stereo calibration.

This module runs automatically during calibration setup to detect and correct
camera alignment issues (vertical offset, toe-in, rotation).
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Tuple

import numpy as np
import yaml

from analysis.camera_alignment_types import AlignmentResults
from analysis.camera_alignment_internals import (
    _assess_quality,
    _build_messages,
    _find_feature_matches,
    _insufficient_features_result,
    _analyze_vertical,
    _analyze_horizontal,
    _analyze_rotation,
    _analyze_scale,
)

# Re-exported for backward compatibility: callers import these from
# analysis.camera_alignment.
from analysis.camera_alignment_types import AlignmentResults  # noqa: F401,F811
from analysis.camera_alignment_reporting import (  # noqa: F401
    visualize_features,
    save_alignment_frames,
    generate_html_report,
)
from analysis.camera_alignment_presets import (  # noqa: F401
    save_alignment_preset,
    load_alignment_preset,
    list_alignment_presets,
    compare_with_preset,
)


def analyze_alignment(left_img: np.ndarray, right_img: np.ndarray, max_features: int = 1000) -> AlignmentResults:
    """Automatically analyze stereo camera alignment from frame pair.

    This function runs the complete alignment analysis and returns both
    measurements and automatic correction parameters.

    Args:
        left_img: Image from left camera (BGR or grayscale)
        right_img: Image from right camera (BGR or grayscale)
        max_features: Maximum number of features to detect

    Returns:
        AlignmentResults with measurements, quality assessment, and corrections
    """
    try:
        # Find feature matches
        pts1, pts2 = _find_feature_matches(left_img, right_img, max_features)
        num_matches = len(pts1)

        if num_matches < 50:
            return _insufficient_features_result(num_matches)

        # Analyze alignment dimensions
        vertical = _analyze_vertical(pts1, pts2)
        horizontal = _analyze_horizontal(pts1, pts2)
        rotation = _analyze_rotation(pts1, pts2)
        scale = _analyze_scale(pts1, pts2)  # NEW: Check focal length/scale mismatch

        # Extract key metrics
        vertical_mean = vertical["mean_vertical_disparity_px"]
        vertical_max = vertical["max_vertical_disparity_px"]
        convergence_std = horizontal["std_horizontal_disparity_px"]
        correlation = horizontal["position_disparity_correlation"]
        rotation_deg = rotation["rotation_deg"]
        scale_difference_percent = scale["scale_difference_percent"]  # NEW
        scale_ratio = scale.get("scale_ratio", 1.0)  # NEW: Extract scale ratio

        # Assess overall quality
        quality = _assess_quality(vertical_mean, convergence_std, rotation_deg, correlation, scale_difference_percent)

        # Determine automatic corrections
        rotation_correction_needed = abs(rotation_deg) > 1.0
        rotation_left = 0.0
        rotation_right = rotation_deg if rotation_correction_needed else 0.0
        vertical_offset_px = int(round(vertical_mean))

        # Build user messages
        status_message, warnings, corrections_applied = _build_messages(
            quality,
            vertical,
            horizontal,
            rotation,
            scale,  # Added scale
            rotation_correction_needed,
            rotation_deg,
            vertical_offset_px,
        )

        return AlignmentResults(
            vertical_mean_px=vertical_mean,
            vertical_max_px=vertical_max,
            convergence_std_px=convergence_std,
            correlation=correlation,
            rotation_deg=rotation_deg,
            num_matches=num_matches,
            scale_difference_percent=scale_difference_percent,  # NEW
            scale_ratio=scale_ratio,  # NEW
            quality=quality,
            vertical_status=vertical["status"],
            horizontal_status=horizontal["status"],
            rotation_status=rotation["status"],
            scale_status=scale["status"],  # NEW
            rotation_correction_needed=rotation_correction_needed,
            rotation_left=rotation_left,
            rotation_right=rotation_right,
            vertical_offset_px=vertical_offset_px,
            status_message=status_message,
            warnings=warnings,
            corrections_applied=corrections_applied,
        )

    except Exception as e:
        # If anything fails, return error result
        return AlignmentResults(
            vertical_mean_px=0,
            vertical_max_px=0,
            convergence_std_px=0,
            correlation=0,
            rotation_deg=0,
            num_matches=0,
            scale_difference_percent=0.0,  # NEW
            scale_ratio=1.0,  # NEW
            quality="CRITICAL",
            vertical_status="UNKNOWN",
            horizontal_status="UNKNOWN",
            rotation_status="UNKNOWN",
            scale_status="UNKNOWN",  # NEW
            rotation_correction_needed=False,
            rotation_left=0,
            rotation_right=0,
            vertical_offset_px=0,
            status_message=f"Alignment check failed: {str(e)}",
            warnings=[f"Could not analyze alignment: {str(e)}"],
            corrections_applied=[],
        )


def apply_corrections(config_path: Path, results: AlignmentResults) -> None:
    """Automatically apply software corrections to configuration.

    Saves rotation and vertical offset corrections to config file.
    These are automatically applied during camera capture and calibration.

    Args:
        config_path: Path to configuration file (configs/default.yaml)
        results: Alignment analysis results with correction parameters
    """
    try:
        config_data = yaml.safe_load(config_path.read_text())

        # Apply rotation corrections
        if "camera" not in config_data:
            config_data["camera"] = {}

        config_data["camera"]["rotation_left"] = float(results.rotation_left)
        config_data["camera"]["rotation_right"] = float(results.rotation_right)
        config_data["camera"]["vertical_offset_px"] = int(results.vertical_offset_px)

        # Save alignment quality metrics for reference
        if "alignment_quality" not in config_data["camera"]:
            config_data["camera"]["alignment_quality"] = {}

        config_data["camera"]["alignment_quality"] = {
            "vertical_px": float(results.vertical_mean_px),
            "convergence_std": float(results.convergence_std_px),
            "rotation_deg": float(results.rotation_deg),
            "correlation": float(results.correlation),
            "quality": results.quality,
            "last_checked": datetime.now().isoformat(),
            "num_matches": results.num_matches,
        }

        config_path.write_text(yaml.safe_dump(config_data))

    except Exception as e:
        raise RuntimeError(f"Failed to apply alignment corrections: {e}")


def analyze_alignment_averaged(
    left_camera, right_camera, num_frames: int = 10, interval_ms: int = 100
) -> AlignmentResults:
    """Analyze alignment averaged over multiple frames for stability.

    This provides more robust measurements by averaging over multiple frames,
    reducing noise from single bad frames.

    Args:
        left_camera: Left camera device
        right_camera: Right camera device
        num_frames: Number of frames to average (default: 10)
        interval_ms: Milliseconds between frames (default: 100)

    Returns:
        AlignmentResults with averaged measurements
    """
    results_list = []
    successful_frames = 0

    for i in range(num_frames):
        try:
            # Capture frames
            left_frame = left_camera.read_frame(timeout_ms=1000)
            right_frame = right_camera.read_frame(timeout_ms=1000)

            # Analyze alignment
            result = analyze_alignment(left_frame.image, right_frame.image)

            # Only include if successful (found enough features)
            if result.num_matches >= 50:
                results_list.append(result)
                successful_frames += 1

            # Wait between frames
            if i < num_frames - 1:
                time.sleep(interval_ms / 1000.0)

        except Exception:
            continue  # Skip failed frames

    # Need at least 5 successful frames
    if successful_frames < 5:
        # Return single-frame result if averaging failed
        try:
            left_frame = left_camera.read_frame(timeout_ms=1000)
            right_frame = right_camera.read_frame(timeout_ms=1000)
            return analyze_alignment(left_frame.image, right_frame.image)
        except:
            raise ValueError("Could not capture frames for alignment analysis")

    # Average the metrics
    avg_vertical_mean = np.mean([r.vertical_mean_px for r in results_list])
    avg_vertical_max = np.mean([r.vertical_max_px for r in results_list])
    avg_convergence_std = np.mean([r.convergence_std_px for r in results_list])
    avg_correlation = np.mean([r.correlation for r in results_list])
    avg_rotation = np.mean([r.rotation_deg for r in results_list])
    avg_scale_diff = np.mean([r.scale_difference_percent for r in results_list])
    avg_scale_ratio = np.mean([r.scale_ratio for r in results_list])
    total_matches = sum(r.num_matches for r in results_list) // len(results_list)

    # Re-assess quality with averaged metrics
    quality = _assess_quality(avg_vertical_mean, avg_convergence_std, avg_rotation, avg_correlation, avg_scale_diff)

    # Use first result's status assessments (will be similar)
    first = results_list[0]

    # Determine corrections based on averaged metrics
    rotation_correction_needed = abs(avg_rotation) > 1.0
    rotation_left = 0.0
    rotation_right = avg_rotation if rotation_correction_needed else 0.0
    vertical_offset_px = int(round(avg_vertical_mean))

    # Build messages with averaged data
    vertical_dict = {
        "status": first.vertical_status,
        "severity": "ok" if avg_vertical_mean < 10 else "warning",
        "message": f"Vertical offset {avg_vertical_mean:.1f}px",
    }
    horizontal_dict = {
        "status": first.horizontal_status,
        "severity": "ok" if avg_convergence_std < 10 else "warning",
        "message": f"Convergence {avg_convergence_std:.1f}px",
    }
    rotation_dict = {
        "status": first.rotation_status,
        "severity": "ok" if abs(avg_rotation) < 2 else "warning",
        "message": f"Rotation {avg_rotation:.1f}°",
    }
    scale_dict = {
        "status": first.scale_status,
        "severity": "ok" if avg_scale_diff < 5 else "warning",
        "message": f"Scale {avg_scale_diff:.1f}%",
    }

    status_message, warnings, corrections_applied = _build_messages(
        quality,
        vertical_dict,
        horizontal_dict,
        rotation_dict,
        scale_dict,
        rotation_correction_needed,
        avg_rotation,
        vertical_offset_px,
    )

    # Create result with averaged metrics
    return AlignmentResults(
        vertical_mean_px=avg_vertical_mean,
        vertical_max_px=avg_vertical_max,
        convergence_std_px=avg_convergence_std,
        correlation=avg_correlation,
        rotation_deg=avg_rotation,
        num_matches=total_matches,
        scale_difference_percent=avg_scale_diff,
        scale_ratio=avg_scale_ratio,
        quality=quality,
        vertical_status=first.vertical_status,
        horizontal_status=first.horizontal_status,
        rotation_status=first.rotation_status,
        scale_status=first.scale_status,
        rotation_correction_needed=rotation_correction_needed,
        rotation_left=rotation_left,
        rotation_right=rotation_right,
        vertical_offset_px=vertical_offset_px,
        status_message=f"{status_message} (averaged over {successful_frames} frames)",
        warnings=warnings,
        corrections_applied=corrections_applied,
    )


def check_camera_warmup(camera_device, num_frames: int = 20, variance_threshold: float = 0.02) -> Tuple[bool, float]:
    """Check if camera has warmed up and stabilized.

    Monitors frame variance over multiple frames to detect when camera
    auto-exposure, auto-focus, and auto-white-balance have settled.

    Args:
        camera_device: Camera device to check
        num_frames: Number of frames to analyze (default: 20)
        variance_threshold: Max variance for "stable" (default: 0.02)

    Returns:
        Tuple of (is_stable, variance_score)
    """
    try:
        frame_means = []

        for _ in range(num_frames):
            frame = camera_device.read_frame(timeout_ms=1000)
            # Calculate mean brightness
            mean_val = np.mean(frame.image)
            frame_means.append(mean_val)
            time.sleep(0.05)  # 50ms between frames

        # Calculate variance in mean brightness over time
        frame_means = np.array(frame_means)
        mean_brightness = np.mean(frame_means)

        # Normalize variance by mean (coefficient of variation)
        if mean_brightness > 0:
            variance_score = np.std(frame_means) / mean_brightness
        else:
            variance_score = 1.0  # High variance if mean is 0

        is_stable = variance_score < variance_threshold

        return is_stable, variance_score

    except Exception:
        # If check fails, assume stable (don't block workflow)
        return True, 0.0


def predict_calibration_quality(results: AlignmentResults) -> dict:
    """Predict expected calibration quality based on alignment.

    Args:
        results: Alignment analysis results

    Returns:
        Dict with predicted RMS error range, quality rating, and confidence message
    """
    # Estimate RMS error based on alignment metrics
    # These are empirical estimates based on typical calibration outcomes

    base_error = 0.3  # Baseline error even with perfect alignment

    # Vertical contributes to RMS
    vertical_contribution = abs(results.vertical_mean_px) * 0.05

    # Toe-in is the biggest contributor
    toin_contribution = results.convergence_std_px * 0.08

    # Rotation (if not corrected)
    rotation_contribution = 0 if results.rotation_correction_needed else abs(results.rotation_deg) * 0.1

    # Scale mismatch
    scale_contribution = results.scale_difference_percent * 0.15

    # Estimate RMS error
    estimated_rms_min = (
        base_error + vertical_contribution + (toin_contribution * 0.5) + rotation_contribution + scale_contribution
    )
    estimated_rms_max = (
        base_error
        + (vertical_contribution * 1.5)
        + (toin_contribution * 1.5)
        + (rotation_contribution * 1.5)
        + (scale_contribution * 1.5)
    )

    # Determine predicted quality
    if estimated_rms_max < 0.5:
        predicted_quality = "EXCELLENT"
        confidence_msg = "You should get excellent calibration results with this alignment!"
    elif estimated_rms_max < 1.0:
        predicted_quality = "GOOD"
        confidence_msg = "Expected to achieve good calibration quality."
    elif estimated_rms_max < 2.0:
        predicted_quality = "ACCEPTABLE"
        confidence_msg = "Calibration will work, but consider improving alignment for better accuracy."
    elif estimated_rms_max < 5.0:
        predicted_quality = "POOR"
        confidence_msg = "Calibration quality will be poor. Strongly recommend fixing alignment issues."
    else:
        predicted_quality = "CRITICAL"
        confidence_msg = "Calibration will likely fail or produce unusable results. Fix alignment first."

    return {
        "estimated_rms_min": round(estimated_rms_min, 2),
        "estimated_rms_max": round(estimated_rms_max, 2),
        "predicted_quality": predicted_quality,
        "confidence_message": confidence_msg,
    }

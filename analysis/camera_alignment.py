"""Automatic camera alignment check and correction for stereo calibration.

This module runs automatically during calibration setup to detect and correct
camera alignment issues (vertical offset, toe-in, rotation).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np
import yaml


@dataclass
class AlignmentResults:
    """Results from automatic camera alignment analysis."""

    # Raw measurements
    vertical_mean_px: float
    vertical_max_px: float
    convergence_std_px: float
    correlation: float
    rotation_deg: float
    num_matches: int
    scale_difference_percent: float  # NEW: Scale/focal length mismatch percentage
    scale_ratio: float = 1.0  # NEW: Actual scale ratio (1.0 = match, >1.0 = left zoomed, <1.0 = right zoomed)

    # Quality assessment
    quality: str  # "EXCELLENT", "GOOD", "ACCEPTABLE", "POOR", "CRITICAL"
    vertical_status: str
    horizontal_status: str
    rotation_status: str
    scale_status: str  # NEW: Focal length/scale status

    # Automatic correction parameters
    rotation_correction_needed: bool
    rotation_left: float  # Degrees to rotate left image
    rotation_right: float  # Degrees to rotate right image
    vertical_offset_px: int  # Vertical shift for rectification

    # User-facing messages
    status_message: str
    warnings: list[str]
    corrections_applied: list[str]

    def can_calibrate(self) -> bool:
        """Check if calibration should be allowed with this alignment."""
        return self.quality != "CRITICAL"

    def should_warn_user(self) -> bool:
        """Check if user should be warned about alignment quality."""
        return self.quality in ["POOR", "CRITICAL"]

    def get_quality_score(self) -> int:
        """Calculate overall alignment quality score (0-100).

        Returns:
            Score where 100 = perfect alignment, 0 = unusable
        """
        # Start with perfect score
        score = 100.0

        # Penalize focal length mismatch (0-30 points)
        focal_penalty = min(30, self.scale_difference_percent * 2)
        score -= focal_penalty

        # Penalize toe-in/convergence (0-30 points)
        toin_penalty = min(30, self.convergence_std_px * 1.5)
        score -= toin_penalty

        # Penalize vertical misalignment (0-20 points)
        vertical_penalty = min(20, abs(self.vertical_mean_px) * 2)
        score -= vertical_penalty

        # Penalize rotation (0-20 points, if not auto-corrected)
        if not self.rotation_correction_needed:
            rotation_penalty = min(20, abs(self.rotation_deg) * 10)
            score -= rotation_penalty

        # Ensure score is in valid range
        score = max(0, min(100, score))

        return int(round(score))

    def get_directional_guidance(self) -> List[str]:
        """Get specific adjustment instructions based on alignment issues.

        Returns list of actionable instructions for user.
        """
        guidance = []

        # Focal length guidance (most important - put first)
        if self.scale_difference_percent > 2.0:  # Lower threshold for earlier warning
            # Estimate turn amount based on scale difference
            # Typical lens: 1/8 turn ≈ 3-5% scale change
            turn_estimate = self.scale_difference_percent / 4.0  # Rough estimate
            if turn_estimate < 0.1:
                turn_desc = "very small adjustment"
            elif turn_estimate < 0.2:
                turn_desc = "1/8 turn"
            elif turn_estimate < 0.4:
                turn_desc = "1/4 turn"
            elif turn_estimate < 0.75:
                turn_desc = "1/2 turn"
            else:
                turn_desc = "3/4 turn"

            if self.scale_ratio > 1.02:  # Left camera more zoomed (zoomed in more = higher magnification)
                guidance.append(
                    f"🔧 FOCAL LENGTH: LEFT camera {self.scale_difference_percent:.1f}% more zoomed\n"
                    f"   → Turn LEFT focus ring COUNTER-CLOCKWISE ~{turn_desc}\n"
                    f"   → Goal: Match right camera's zoom level\n"
                    f"   → After adjustment, run Quick Check to verify"
                )
            elif self.scale_ratio < 0.98:  # Right camera more zoomed
                guidance.append(
                    f"🔧 FOCAL LENGTH: RIGHT camera {self.scale_difference_percent:.1f}% more zoomed\n"
                    f"   → Turn RIGHT focus ring COUNTER-CLOCKWISE ~{turn_desc}\n"
                    f"   → Goal: Match left camera's zoom level\n"
                    f"   → After adjustment, run Quick Check to verify"
                )

        # Toe-in guidance
        if self.convergence_std_px > 10.0:
            if self.correlation > 0.3:  # Toed in
                guidance.append(
                    f"🔧 Camera Angles: Rotate BOTH cameras OUTWARD (away from each other) "
                    f"by ~2-3 degrees to fix toe-in"
                )
            elif self.correlation < -0.3:  # Toed out
                guidance.append(
                    f"🔧 Camera Angles: Rotate BOTH cameras INWARD (toward each other) "
                    f"by ~2-3 degrees to fix toe-out"
                )

        # Vertical guidance
        if abs(self.vertical_mean_px) > 10.0:
            direction = "LOWER" if self.vertical_mean_px > 0 else "RAISE"
            amount_inches = abs(self.vertical_mean_px) * 0.02  # Rough px to inches
            guidance.append(
                f"🔧 Camera Height: {direction} right camera by ~{amount_inches:.1f} inches "
                f"(currently {abs(self.vertical_mean_px):.0f}px offset)"
            )

        # Rotation guidance (if not auto-corrected)
        if abs(self.rotation_deg) > 2.0 and not self.rotation_correction_needed:
            direction = "CLOCKWISE" if self.rotation_deg > 0 else "COUNTER-CLOCKWISE"
            guidance.append(
                f"🔧 Camera Rotation: Rotate right camera {direction} by ~{abs(self.rotation_deg):.1f}° "
                f"to level with left camera"
            )

        if not guidance:
            guidance.append("✓ Alignment is good - no adjustments needed!")

        return guidance


def analyze_alignment(left_img: np.ndarray, right_img: np.ndarray,
                      max_features: int = 1000) -> AlignmentResults:
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
            quality, vertical, horizontal, rotation, scale,  # Added scale
            rotation_correction_needed, rotation_deg, vertical_offset_px
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
            corrections_applied=corrections_applied
        )

    except Exception as e:
        # If anything fails, return error result
        return AlignmentResults(
            vertical_mean_px=0, vertical_max_px=0,
            convergence_std_px=0, correlation=0, rotation_deg=0, num_matches=0,
            scale_difference_percent=0.0,  # NEW
            scale_ratio=1.0,  # NEW
            quality="CRITICAL",
            vertical_status="UNKNOWN",
            horizontal_status="UNKNOWN",
            rotation_status="UNKNOWN",
            scale_status="UNKNOWN",  # NEW
            rotation_correction_needed=False,
            rotation_left=0, rotation_right=0, vertical_offset_px=0,
            status_message=f"Alignment check failed: {str(e)}",
            warnings=[f"Could not analyze alignment: {str(e)}"],
            corrections_applied=[]
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
            "num_matches": results.num_matches
        }

        config_path.write_text(yaml.safe_dump(config_data))

    except Exception as e:
        raise RuntimeError(f"Failed to apply alignment corrections: {e}")


def analyze_alignment_averaged(left_camera, right_camera, num_frames: int = 10,
                               interval_ms: int = 100) -> AlignmentResults:
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
    quality = _assess_quality(avg_vertical_mean, avg_convergence_std, avg_rotation,
                             avg_correlation, avg_scale_diff)

    # Use first result's status assessments (will be similar)
    first = results_list[0]

    # Determine corrections based on averaged metrics
    rotation_correction_needed = abs(avg_rotation) > 1.0
    rotation_left = 0.0
    rotation_right = avg_rotation if rotation_correction_needed else 0.0
    vertical_offset_px = int(round(avg_vertical_mean))

    # Build messages with averaged data
    vertical_dict = {"status": first.vertical_status, "severity": "ok" if avg_vertical_mean < 10 else "warning", "message": f"Vertical offset {avg_vertical_mean:.1f}px"}
    horizontal_dict = {"status": first.horizontal_status, "severity": "ok" if avg_convergence_std < 10 else "warning", "message": f"Convergence {avg_convergence_std:.1f}px"}
    rotation_dict = {"status": first.rotation_status, "severity": "ok" if abs(avg_rotation) < 2 else "warning", "message": f"Rotation {avg_rotation:.1f}°"}
    scale_dict = {"status": first.scale_status, "severity": "ok" if avg_scale_diff < 5 else "warning", "message": f"Scale {avg_scale_diff:.1f}%"}

    status_message, warnings, corrections_applied = _build_messages(
        quality, vertical_dict, horizontal_dict, rotation_dict, scale_dict,
        rotation_correction_needed, avg_rotation, vertical_offset_px
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
        corrections_applied=corrections_applied
    )


def visualize_features(left_img: np.ndarray, right_img: np.ndarray,
                      pts1: np.ndarray, pts2: np.ndarray,
                      save_path: Optional[Path] = None) -> np.ndarray:
    """Create visualization of matched features between cameras.

    Args:
        left_img: Left camera image
        right_img: Right camera image
        pts1: Feature points in left image (Nx2)
        pts2: Corresponding points in right image (Nx2)
        save_path: Optional path to save visualization

    Returns:
        Combined visualization image with feature overlays
    """
    # Convert to BGR if grayscale
    if left_img.ndim == 2:
        left_vis = cv2.cvtColor(left_img, cv2.COLOR_GRAY2BGR)
    else:
        left_vis = left_img.copy()

    if right_img.ndim == 2:
        right_vis = cv2.cvtColor(right_img, cv2.COLOR_GRAY2BGR)
    else:
        right_vis = right_img.copy()

    # Draw circles on feature points
    for pt in pts1:
        cv2.circle(left_vis, (int(pt[0]), int(pt[1])), 3, (0, 255, 0), -1)  # Green

    for pt in pts2:
        cv2.circle(right_vis, (int(pt[0]), int(pt[1])), 3, (0, 255, 0), -1)  # Green

    # Create side-by-side visualization
    h1, w1 = left_vis.shape[:2]
    h2, w2 = right_vis.shape[:2]
    h_max = max(h1, h2)

    # Resize if heights don't match
    if h1 != h_max:
        left_vis = cv2.resize(left_vis, (int(w1 * h_max / h1), h_max))
    if h2 != h_max:
        right_vis = cv2.resize(right_vis, (int(w2 * h_max / h2), h_max))

    # Combine side by side
    combined = np.hstack([left_vis, right_vis])

    # Add text overlay
    text = f"{len(pts1)} features matched"
    cv2.putText(combined, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                1.0, (0, 255, 0), 2, cv2.LINE_AA)

    # Save if requested
    if save_path:
        cv2.imwrite(str(save_path), combined)

    return combined


def save_alignment_frames(left_img: np.ndarray, right_img: np.ndarray,
                         results: AlignmentResults,
                         output_dir: Path = Path("alignment_checks")) -> None:
    """Save alignment check frames and visualization for debugging.

    Args:
        left_img: Left camera image
        right_img: Right camera image
        results: Alignment results
        output_dir: Directory to save frames (default: alignment_checks/)
    """
    try:
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save raw frames
        left_path = output_dir / f"left_{timestamp}.png"
        right_path = output_dir / f"right_{timestamp}.png"
        cv2.imwrite(str(left_path), left_img)
        cv2.imwrite(str(right_path), right_img)

        # Save visualization with features
        try:
            pts1, pts2 = _find_feature_matches(left_img, right_img, max_features=1000)
            vis_path = output_dir / f"features_{timestamp}.png"
            visualize_features(left_img, right_img, pts1, pts2, vis_path)
        except:
            pass  # Skip visualization if feature matching fails

        # Save JSON report
        import json
        report = {
            "timestamp": timestamp,
            "quality": results.quality,
            "vertical_mean_px": results.vertical_mean_px,
            "vertical_max_px": results.vertical_max_px,
            "convergence_std_px": results.convergence_std_px,
            "correlation": results.correlation,
            "rotation_deg": results.rotation_deg,
            "scale_difference_percent": results.scale_difference_percent,
            "num_matches": results.num_matches,
            "warnings": results.warnings,
            "corrections_applied": results.corrections_applied,
        }
        report_path = output_dir / f"report_{timestamp}.json"
        report_path.write_text(json.dumps(report, indent=2))

    except Exception as e:
        # Don't fail alignment check if saving fails
        print(f"Warning: Could not save alignment frames: {e}")


def generate_html_report(results: AlignmentResults, left_serial: str, right_serial: str) -> str:
    """Generate HTML alignment report.

    Args:
        results: Alignment analysis results
        left_serial: Left camera serial/ID
        right_serial: Right camera serial/ID

    Returns:
        HTML string with comprehensive alignment report
    """
    from datetime import datetime

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate quality score
    quality_score = results.get_quality_score()

    # Choose colors
    if results.quality == "EXCELLENT":
        quality_color = "#4CAF50"
    elif results.quality == "GOOD":
        quality_color = "#8BC34A"
    elif results.quality == "ACCEPTABLE":
        quality_color = "#FFC107"
    elif results.quality == "POOR":
        quality_color = "#FF9800"
    else:  # CRITICAL
        quality_color = "#F44336"

    # Build guidance section
    guidance_html = ""
    guidance = results.get_directional_guidance()
    if guidance:
        guidance_html = "<h3>Recommended Adjustments</h3><ul>"
        for instruction in guidance:
            guidance_html += f"<li>{instruction.replace('🔧', '').replace('→', '&rarr;')}</li>"
        guidance_html += "</ul>"

    # Build corrections section
    corrections_html = ""
    if results.corrections_applied:
        corrections_html = "<h3>Automatic Corrections Applied</h3><ul>"
        for correction in results.corrections_applied:
            corrections_html += f"<li>{correction}</li>"
        corrections_html += "</ul>"

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Camera Alignment Report - {timestamp}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 28pt;
        }}
        .header p {{
            margin: 5px 0;
            opacity: 0.9;
        }}
        .score-card {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        .score {{
            font-size: 64pt;
            font-weight: bold;
            color: {quality_color};
            margin: 10px 0;
        }}
        .quality-label {{
            font-size: 20pt;
            color: {quality_color};
            font-weight: bold;
            margin: 10px 0;
        }}
        .section {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h2 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        h3 {{
            color: #555;
            margin-top: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f5f5f5;
            font-weight: bold;
            color: #555;
        }}
        .status-excellent {{ color: #4CAF50; font-weight: bold; }}
        .status-good {{ color: #8BC34A; font-weight: bold; }}
        .status-acceptable {{ color: #FFC107; font-weight: bold; }}
        .status-poor {{ color: #FF9800; font-weight: bold; }}
        .status-critical {{ color: #F44336; font-weight: bold; }}
        ul {{
            line-height: 1.8;
        }}
        li {{
            margin: 10px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #888;
            font-size: 9pt;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📹 Camera Alignment Report</h1>
        <p><strong>Generated:</strong> {timestamp}</p>
        <p><strong>Left Camera:</strong> {left_serial}</p>
        <p><strong>Right Camera:</strong> {right_serial}</p>
    </div>

    <div class="score-card">
        <div class="score">{quality_score}%</div>
        <div class="quality-label">{results.quality}</div>
        <p style="color: #666; margin-top: 15px;">{results.status_message}</p>
    </div>

    <div class="section">
        <h2>Alignment Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Status</th>
            </tr>
            <tr>
                <td><strong>Focal Length Difference</strong></td>
                <td>{results.scale_difference_percent:.2f}%</td>
                <td class="status-{results.scale_status.lower()}">{results.scale_status}</td>
            </tr>
            <tr>
                <td><strong>Toe-in / Convergence</strong></td>
                <td>{results.convergence_std_px:.2f} px std dev</td>
                <td class="status-{results.horizontal_status.lower()}">{results.horizontal_status}</td>
            </tr>
            <tr>
                <td><strong>Vertical Offset</strong></td>
                <td>{results.vertical_mean_px:.2f} px mean ({results.vertical_max_px:.2f} px max)</td>
                <td class="status-{results.vertical_status.lower()}">{results.vertical_status}</td>
            </tr>
            <tr>
                <td><strong>Rotation Difference</strong></td>
                <td>{results.rotation_deg:.2f}°</td>
                <td class="status-{results.rotation_status.lower()}">{results.rotation_status}</td>
            </tr>
            <tr>
                <td><strong>Feature Matches</strong></td>
                <td>{results.num_matches}</td>
                <td>{'<span class="status-excellent">Good</span>' if results.num_matches >= 200 else '<span class="status-acceptable">Acceptable</span>'}</td>
            </tr>
        </table>
    </div>

    {f'<div class="section">{guidance_html}</div>' if guidance_html else ''}
    {f'<div class="section">{corrections_html}</div>' if corrections_html else ''}

    <div class="footer">
        <p>Generated by PitchTracker Camera Alignment System</p>
        <p>For best results, keep alignment score above 75%</p>
    </div>
</body>
</html>"""

    return html


def save_alignment_preset(results: AlignmentResults, preset_name: str,
                          left_serial: str, right_serial: str) -> None:
    """Save current alignment as a preset/profile.

    Args:
        results: Alignment results to save
        preset_name: Name for this preset (e.g., "baseline_2026-01-20")
        left_serial: Left camera serial
        right_serial: Right camera serial
    """
    import json
    from datetime import datetime

    presets_dir = Path("alignment_checks/presets")
    presets_dir.mkdir(parents=True, exist_ok=True)

    preset_data = {
        "preset_name": preset_name,
        "saved_at": datetime.now().isoformat(),
        "left_camera": left_serial,
        "right_camera": right_serial,
        "quality_score": results.get_quality_score(),
        "quality_rating": results.quality,
        "metrics": {
            "focal_diff_percent": results.scale_difference_percent,
            "scale_ratio": results.scale_ratio,
            "toin_std_px": results.convergence_std_px,
            "correlation": results.correlation,
            "vertical_mean_px": results.vertical_mean_px,
            "vertical_max_px": results.vertical_max_px,
            "rotation_deg": results.rotation_deg,
            "num_matches": results.num_matches
        },
        "status": {
            "focal": results.scale_status,
            "horizontal": results.horizontal_status,
            "vertical": results.vertical_status,
            "rotation": results.rotation_status
        }
    }

    # Save to file
    preset_file = presets_dir / f"{preset_name}.json"
    preset_file.write_text(json.dumps(preset_data, indent=2))


def load_alignment_preset(preset_name: str) -> Optional[dict]:
    """Load a saved alignment preset.

    Args:
        preset_name: Name of preset to load

    Returns:
        Preset data dict or None if not found
    """
    import json

    preset_file = Path("alignment_checks/presets") / f"{preset_name}.json"
    if not preset_file.exists():
        return None

    try:
        return json.loads(preset_file.read_text())
    except Exception:
        return None


def list_alignment_presets() -> List[dict]:
    """List all saved alignment presets.

    Returns:
        List of preset metadata dicts
    """
    import json

    presets_dir = Path("alignment_checks/presets")
    if not presets_dir.exists():
        return []

    presets = []
    for preset_file in presets_dir.glob("*.json"):
        try:
            data = json.loads(preset_file.read_text())
            presets.append({
                "name": preset_file.stem,
                "saved_at": data.get("saved_at", "Unknown"),
                "quality_score": data.get("quality_score", 0),
                "quality_rating": data.get("quality_rating", "UNKNOWN")
            })
        except Exception:
            continue

    # Sort by saved date (newest first)
    presets.sort(key=lambda x: x["saved_at"], reverse=True)
    return presets


def compare_with_preset(current: AlignmentResults, preset_data: dict) -> dict:
    """Compare current alignment with a saved preset.

    Args:
        current: Current alignment results
        preset_data: Loaded preset data

    Returns:
        Dict with comparison details
    """
    preset_metrics = preset_data["metrics"]

    # Calculate deltas
    focal_delta = current.scale_difference_percent - preset_metrics["focal_diff_percent"]
    toin_delta = current.convergence_std_px - preset_metrics["toin_std_px"]
    vertical_delta = current.vertical_mean_px - preset_metrics["vertical_mean_px"]
    rotation_delta = current.rotation_deg - preset_metrics["rotation_deg"]

    # Calculate score delta
    current_score = current.get_quality_score()
    preset_score = preset_data["quality_score"]
    score_delta = current_score - preset_score

    # Determine overall trend
    if score_delta > 5:
        trend = "BETTER"
        trend_emoji = "📈"
    elif score_delta < -5:
        trend = "WORSE"
        trend_emoji = "📉"
    else:
        trend = "SIMILAR"
        trend_emoji = "➡️"

    return {
        "preset_name": preset_data["preset_name"],
        "preset_date": preset_data["saved_at"][:10],
        "current_score": current_score,
        "preset_score": preset_score,
        "score_delta": score_delta,
        "trend": trend,
        "trend_emoji": trend_emoji,
        "deltas": {
            "focal": {
                "current": current.scale_difference_percent,
                "preset": preset_metrics["focal_diff_percent"],
                "delta": focal_delta,
                "better": abs(focal_delta) < 0 or (abs(current.scale_difference_percent) < abs(preset_metrics["focal_diff_percent"]))
            },
            "toin": {
                "current": current.convergence_std_px,
                "preset": preset_metrics["toin_std_px"],
                "delta": toin_delta,
                "better": toin_delta < 0
            },
            "vertical": {
                "current": current.vertical_mean_px,
                "preset": preset_metrics["vertical_mean_px"],
                "delta": vertical_delta,
                "better": abs(vertical_delta) < 0 or (abs(current.vertical_mean_px) < abs(preset_metrics["vertical_mean_px"]))
            },
            "rotation": {
                "current": current.rotation_deg,
                "preset": preset_metrics["rotation_deg"],
                "delta": rotation_delta,
                "better": abs(rotation_delta) < 0 or (abs(current.rotation_deg) < abs(preset_metrics["rotation_deg"]))
            }
        }
    }


def check_camera_warmup(camera_device, num_frames: int = 20,
                        variance_threshold: float = 0.02) -> Tuple[bool, float]:
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
    estimated_rms_min = base_error + vertical_contribution + (toin_contribution * 0.5) + rotation_contribution + scale_contribution
    estimated_rms_max = base_error + (vertical_contribution * 1.5) + (toin_contribution * 1.5) + (rotation_contribution * 1.5) + (scale_contribution * 1.5)

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


# ============================================================================
# Internal helper functions
# ============================================================================

def _find_feature_matches(img1: np.ndarray, img2: np.ndarray,
                         max_features: int) -> Tuple[np.ndarray, np.ndarray]:
    """Find corresponding feature points between two images."""
    # Convert to grayscale if needed
    if img1.ndim == 3:
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    else:
        gray1 = img1

    if img2.ndim == 3:
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    else:
        gray2 = img2

    # Use ORB (fast, patent-free)
    orb = cv2.ORB_create(nfeatures=max_features)

    # Detect keypoints and compute descriptors
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        raise ValueError("Not enough features detected - point cameras at textured scene")

    # Match features
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    if len(matches) < 20:
        raise ValueError(f"Not enough matches found ({len(matches)}) - need textured scene")

    # Sort and take best matches
    matches = sorted(matches, key=lambda x: x.distance)
    num_good = max(50, len(matches) // 2)
    good_matches = matches[:num_good]

    # Extract coordinates
    pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])

    return pts1, pts2


def _analyze_vertical(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze vertical alignment (height difference)."""
    y1 = pts1[:, 1]
    y2 = pts2[:, 1]
    vertical_disparity = y2 - y1

    mean_v_disp = np.mean(vertical_disparity)
    std_v_disp = np.std(vertical_disparity)
    max_v_disp = np.max(np.abs(vertical_disparity))

    # Thresholds
    if max_v_disp < 2.0:
        status = "EXCELLENT"
        severity = "ok"
        message = "Cameras well aligned vertically"
    elif max_v_disp < 5.0:
        status = "GOOD"
        severity = "ok"
        message = "Cameras well aligned vertically"
    elif max_v_disp < 10.0:
        status = "ACCEPTABLE"
        severity = "warning"
        message = "Slight vertical misalignment"
    else:
        status = "POOR"
        severity = "error"
        message = "Significant vertical misalignment"

    return {
        "status": status,
        "severity": severity,
        "message": message,
        "mean_vertical_disparity_px": float(mean_v_disp),
        "std_vertical_disparity_px": float(std_v_disp),
        "max_vertical_disparity_px": float(max_v_disp),
    }


def _analyze_horizontal(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze horizontal alignment (toe-in/convergence)."""
    x1 = pts1[:, 0]
    x2 = pts2[:, 0]
    horizontal_disparity = x1 - x2

    mean_h_disp = np.mean(horizontal_disparity)
    std_h_disp = np.std(horizontal_disparity)
    correlation = np.corrcoef(x1, horizontal_disparity)[0, 1]

    # Thresholds
    if std_h_disp < 5.0 and abs(correlation) < 0.1:
        status = "EXCELLENT"
        severity = "ok"
        message = "Cameras perfectly parallel"
    elif std_h_disp < 10.0 and abs(correlation) < 0.3:
        status = "GOOD"
        severity = "ok"
        message = "Cameras well aligned (minimal convergence)"
    elif std_h_disp < 20.0:
        status = "ACCEPTABLE"
        severity = "warning"
        message = "Slight convergence detected"
    else:
        status = "POOR"
        severity = "error"
        if correlation > 0.3:
            message = "Cameras toed-IN (converging)"
        elif correlation < -0.3:
            message = "Cameras toed-OUT (diverging)"
        else:
            message = "Cameras not parallel"

    return {
        "status": status,
        "severity": severity,
        "message": message,
        "mean_horizontal_disparity_px": float(mean_h_disp),
        "std_horizontal_disparity_px": float(std_h_disp),
        "position_disparity_correlation": float(correlation),
    }


def _analyze_rotation(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze rotation difference (roll/tilt)."""
    try:
        if len(pts1) < 3:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Not enough points for rotation estimate",
                "rotation_deg": 0.0,
            }

        # Estimate affine transform with RANSAC
        M, mask = cv2.estimateAffinePartial2D(pts1, pts2, method=cv2.RANSAC,
                                              ransacReprojThreshold=5.0)

        if M is None:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Could not estimate rotation",
                "rotation_deg": 0.0,
            }

        # Extract rotation angle
        rotation_rad = np.arctan2(M[1, 0], M[0, 0])
        rotation_deg = np.degrees(rotation_rad)

        # Thresholds
        abs_rotation = abs(rotation_deg)
        if abs_rotation < 0.5:
            status = "EXCELLENT"
            severity = "ok"
            message = "No rotation difference"
        elif abs_rotation < 1.0:
            status = "GOOD"
            severity = "ok"
            message = "Minimal rotation difference"
        elif abs_rotation < 2.0:
            status = "ACCEPTABLE"
            severity = "warning"
            message = f"Slight rotation ({rotation_deg:.1f}°)"
        else:
            status = "POOR"
            severity = "error"
            direction = "clockwise" if rotation_deg > 0 else "counter-clockwise"
            message = f"Significant rotation ({rotation_deg:.1f}° {direction})"

        return {
            "status": status,
            "severity": severity,
            "message": message,
            "rotation_deg": float(rotation_deg),
        }

    except Exception:
        return {
            "status": "UNKNOWN",
            "severity": "warning",
            "message": "Rotation analysis failed",
            "rotation_deg": 0.0,
        }


def _analyze_scale(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze scale difference (focal length mismatch).

    If cameras have different focal lengths (one zoomed in more),
    the same features will appear at different scales.
    """
    try:
        if len(pts1) < 10:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Not enough points for scale estimate",
                "scale_difference_percent": 0.0,
            }

        # Compute pairwise distances between features in each image
        # If scales match, distance ratios should be ~1.0

        # Sample random pairs to estimate scale
        np.random.seed(42)  # Reproducible
        n_samples = min(50, len(pts1))
        indices = np.random.choice(len(pts1), size=n_samples, replace=False)

        scale_ratios = []
        for i in range(len(indices) - 1):
            idx1 = indices[i]
            idx2 = indices[i + 1]

            # Distance in left image
            dist1 = np.linalg.norm(pts1[idx1] - pts1[idx2])
            # Distance in right image
            dist2 = np.linalg.norm(pts2[idx1] - pts2[idx2])

            if dist2 > 1.0:  # Avoid division by very small numbers
                scale_ratios.append(dist1 / dist2)

        if len(scale_ratios) < 5:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Insufficient data for scale estimate",
                "scale_difference_percent": 0.0,
            }

        # Median scale ratio (robust to outliers)
        median_scale = np.median(scale_ratios)

        # Scale difference as percentage
        # 1.0 = perfect match, 1.1 = 10% larger in left camera
        scale_difference_percent = abs(median_scale - 1.0) * 100

        # Thresholds
        if scale_difference_percent < 2.0:
            status = "EXCELLENT"
            severity = "ok"
            message = "Focal lengths match well"
        elif scale_difference_percent < 5.0:
            status = "GOOD"
            severity = "ok"
            message = "Focal lengths nearly match"
        elif scale_difference_percent < 10.0:
            status = "ACCEPTABLE"
            severity = "warning"
            message = f"Slight focal length mismatch ({scale_difference_percent:.1f}%)"
        else:
            status = "POOR"
            severity = "error"
            which_larger = "left" if median_scale > 1.0 else "right"
            message = f"Focal length mismatch ({scale_difference_percent:.1f}% - {which_larger} camera more zoomed)"

        return {
            "status": status,
            "severity": severity,
            "message": message,
            "scale_difference_percent": float(scale_difference_percent),
            "scale_ratio": float(median_scale),
        }

    except Exception:
        return {
            "status": "UNKNOWN",
            "severity": "warning",
            "message": "Scale analysis failed",
            "scale_difference_percent": 0.0,
        }


def _assess_quality(vertical_px: float, convergence_std: float,
                   rotation_deg: float, correlation: float, scale_difference_percent: float) -> str:
    """Assess overall alignment quality."""
    # Critical - block calibration
    if correlation < 0.3 or convergence_std > 40 or scale_difference_percent > 15:
        return "CRITICAL"

    # Poor - strong warning
    if vertical_px > 20 or convergence_std > 20 or abs(rotation_deg) > 5 or scale_difference_percent > 10:
        return "POOR"

    # Acceptable - minor warning
    if vertical_px > 10 or convergence_std > 10 or abs(rotation_deg) > 3 or scale_difference_percent > 5:
        return "ACCEPTABLE"

    # Good
    if vertical_px > 5 or convergence_std > 5 or abs(rotation_deg) > 1 or scale_difference_percent > 2:
        return "GOOD"

    # Excellent
    return "EXCELLENT"


def _build_messages(quality: str, vertical: dict, horizontal: dict, rotation: dict, scale: dict,
                   rotation_correction_needed: bool, rotation_deg: float,
                   vertical_offset_px: int) -> Tuple[str, list[str], list[str]]:
    """Build user-facing status messages."""
    warnings = []
    corrections_applied = []

    if quality == "CRITICAL":
        status_message = "Camera alignment is too poor for calibration"
        if horizontal["severity"] == "error":
            warnings.append("Severe toe-in detected - cameras must be adjusted to be parallel")
        if scale["severity"] == "error":
            warnings.append(f"Focal length mismatch detected - {scale['message']}")
            warnings.append("Adjust camera focus rings to match or check manual focus settings")
        warnings.append("Physical adjustment required before calibration")
    elif quality == "POOR":
        status_message = "Camera alignment is poor - calibration will have reduced accuracy"
        if horizontal["severity"] == "error":
            warnings.append(f"{horizontal['message']} - consider adjusting camera angles")
        if vertical["severity"] == "error":
            warnings.append(f"{vertical['message']} - consider adjusting camera heights")
        if rotation["severity"] == "error" and not rotation_correction_needed:
            warnings.append(f"{rotation['message']} - consider leveling cameras")
        if scale["severity"] == "error":
            warnings.append(f"{scale['message']} - adjust camera focus settings")
    elif quality == "ACCEPTABLE":
        status_message = "Camera alignment is acceptable with software corrections"
        if horizontal["severity"] == "warning":
            warnings.append(f"{horizontal['message']}")
        if scale["severity"] == "warning":
            warnings.append(f"{scale['message']} - check camera focus")
    elif quality == "GOOD":
        status_message = "Camera alignment is good"
    else:
        status_message = "Camera alignment is excellent"

    # Corrections applied
    if rotation_correction_needed:
        corrections_applied.append(f"Rotation correction applied ({rotation_deg:.1f}° → 0°)")

    if abs(vertical_offset_px) > 5:
        corrections_applied.append(f"Vertical offset correction saved ({vertical_offset_px} px)")

    return status_message, warnings, corrections_applied


def _insufficient_features_result(num_matches: int) -> AlignmentResults:
    """Return result when insufficient features are detected."""
    return AlignmentResults(
        vertical_mean_px=0, vertical_max_px=0,
        convergence_std_px=0, correlation=0, rotation_deg=0,
        num_matches=num_matches,
        scale_difference_percent=0.0,  # NEW
        scale_ratio=1.0,  # NEW
        quality="CRITICAL",
        vertical_status="UNKNOWN",
        horizontal_status="UNKNOWN",
        rotation_status="UNKNOWN",
        scale_status="UNKNOWN",  # NEW
        rotation_correction_needed=False,
        rotation_left=0, rotation_right=0, vertical_offset_px=0,
        status_message="Not enough features detected",
        warnings=[
            f"Only {num_matches} features matched (need 50+)",
            "Point cameras at textured scene (posters, books, NOT blank wall)",
            "Ensure good lighting and both cameras see common objects"
        ],
        corrections_applied=[]
    )

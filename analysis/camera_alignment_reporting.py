"""Alignment visualization and report generation.

Rendering and IO helpers: feature overlays, saved debug frames, and the
standalone HTML report. Kept separate so the core analysis stays IO-free.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from analysis.camera_alignment_types import AlignmentResults
from analysis.camera_alignment_internals import _find_feature_matches


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

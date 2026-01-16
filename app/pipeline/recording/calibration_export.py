"""Export calibration metadata for ML training."""

import json
from pathlib import Path
from typing import Any, Optional


def export_calibration_metadata(
    session_dir: Path,
    stereo: Any,  # SimpleStereoMatcher
    left_camera_id: str,
    right_camera_id: str,
    lane_gate: Optional[Any] = None,
    plate_gate: Optional[Any] = None,
):
    """Export calibration metadata to JSON.

    Args:
        session_dir: Session directory
        stereo: Stereo matcher with calibration
        left_camera_id: Left camera serial
        right_camera_id: Right camera serial
        lane_gate: Lane ROI gate
        plate_gate: Plate ROI gate
    """
    calib_dir = session_dir / "calibration"
    calib_dir.mkdir(exist_ok=True)

    # Stereo geometry
    if hasattr(stereo, "geometry"):
        geometry = {
            "baseline_ft": float(stereo.geometry.baseline_ft),
            "convergence_angle_deg": float(stereo.geometry.convergence_angle_deg),
            "camera_height_ft": float(stereo.geometry.camera_height_ft),
            "distance_to_plate_ft": float(stereo.geometry.distance_to_plate_ft),
        }
        (calib_dir / "stereo_geometry.json").write_text(json.dumps(geometry, indent=2))

    # Camera intrinsics (if available)
    if hasattr(stereo, "camera_matrix_left") and stereo.camera_matrix_left is not None:
        intrinsics_left = {
            "camera_id": left_camera_id,
            "fx": float(stereo.camera_matrix_left[0, 0]),
            "fy": float(stereo.camera_matrix_left[1, 1]),
            "cx": float(stereo.camera_matrix_left[0, 2]),
            "cy": float(stereo.camera_matrix_left[1, 2]),
            "distortion_k1": (
                float(stereo.dist_coeffs_left[0])
                if stereo.dist_coeffs_left is not None
                else 0.0
            ),
            "distortion_k2": (
                float(stereo.dist_coeffs_left[1])
                if stereo.dist_coeffs_left is not None
                else 0.0
            ),
        }
        (calib_dir / "intrinsics_left.json").write_text(
            json.dumps(intrinsics_left, indent=2)
        )

    if hasattr(stereo, "camera_matrix_right") and stereo.camera_matrix_right is not None:
        intrinsics_right = {
            "camera_id": right_camera_id,
            "fx": float(stereo.camera_matrix_right[0, 0]),
            "fy": float(stereo.camera_matrix_right[1, 1]),
            "cx": float(stereo.camera_matrix_right[0, 2]),
            "cy": float(stereo.camera_matrix_right[1, 2]),
            "distortion_k1": (
                float(stereo.dist_coeffs_right[0])
                if stereo.dist_coeffs_right is not None
                else 0.0
            ),
            "distortion_k2": (
                float(stereo.dist_coeffs_right[1])
                if stereo.dist_coeffs_right is not None
                else 0.0
            ),
        }
        (calib_dir / "intrinsics_right.json").write_text(
            json.dumps(intrinsics_right, indent=2)
        )

    # ROI annotations
    roi_annotations = {}

    if lane_gate and hasattr(lane_gate, "polygon") and lane_gate.polygon is not None:
        roi_annotations["lane_gate_polygon"] = [
            [float(x), float(y)] for x, y in lane_gate.polygon
        ]

    if plate_gate and hasattr(plate_gate, "polygon") and plate_gate.polygon is not None:
        roi_annotations["plate_gate_polygon"] = [
            [float(x), float(y)] for x, y in plate_gate.polygon
        ]

    if roi_annotations:
        (calib_dir / "roi_annotations.json").write_text(
            json.dumps(roi_annotations, indent=2)
        )

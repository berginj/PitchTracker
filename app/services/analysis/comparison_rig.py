"""Bind qualification to effective geometry, regions and camera identities."""

import hashlib
import json
from pathlib import Path

from contracts.model_bundle import file_hash


def rig_binding(calibration_path, regions, field_transform, camera_ids):
    if not calibration_path or set(camera_ids) != {"left", "right"}:
        raise ValueError("Qualification requires calibration and both camera identities")
    effective: dict[str, dict[str, list[list[float]]]] = {}
    for kind in ("lane", "plate"):
        per_camera = regions.get(f"{kind}_by_camera", {})
        effective[kind] = {}
        for side, camera in camera_ids.items():
            polygon = per_camera.get(camera, regions.get(kind, []))
            effective[kind][side] = [[float(x), float(y)] for x, y in polygon]
    matrix = field_transform.get("matrix_4x4")
    if not matrix or len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ValueError("Qualification requires the actual field transform")
    payload = {
        "calibration_sha256": file_hash(Path(calibration_path)),
        "regions": effective,
        "field_matrix_4x4": [[float(v) for v in row] for row in matrix],
        "camera_ids": camera_ids,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


def admit_live_rig(config, calibration_path, regions, field_transform, camera_ids):
    if config.detector.type != "ml" or config.detector.model_format != "yolo_v11":
        return
    from app.services.analysis.comparison_qualification import admit_live_profile

    admit_live_profile(config)
    receipt = json.loads(Path(config.detector.qualification_path).read_text(encoding="utf-8"))
    if receipt.get("rig_binding") != rig_binding(calibration_path, regions, field_transform, camera_ids):
        raise ValueError("Experimental detector qualification does not match this rig's geometry or camera identities")

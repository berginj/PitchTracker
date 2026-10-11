"""Explicit mapping of one derived fit into one shadow study case."""

import json
from pathlib import Path

from app.pipeline.analysis.pitch_summary import _fitted_observed_speed_mph
from trajectory.serialization import decode_result


def shadow_measurements(path: Path, phase: str):
    if phase != "shadow":
        raise ValueError("Confirmation datasets are read-only")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "fit_batch_result.v1":
        raise ValueError("Select a derived fit result artifact")
    result = decode_result(payload["result"])
    request = payload["request"]["payload"]
    speed = _fitted_observed_speed_mph(result)
    crossing = result.plate_crossing_xyz_ft
    available = speed is not None and crossing is not None
    return {
        "mode": request["mode"],
        "system_outcome": "ACCEPTED" if available else "UNAVAILABLE",
        "measured_speed_mph": speed if available else None,
        "measured_speed_source": "vision_fit" if available else None,
        "speed_estimator": result.diagnostics.estimator,
        "measured_speed_reference_z_ft": result.samples[0].Z if available else None,
        "measured_plate_xy_ft": list(crossing[:2]) if crossing is not None and available else None,
        "used_for_tuning": True,
    }

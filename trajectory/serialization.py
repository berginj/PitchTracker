"""JSON-only transport for the supervised trajectory worker."""

from dataclasses import asdict
import json
import math
from typing import Any, Optional

import numpy as np

from contracts import RayObservation, StereoObservation, TrackSample
from trajectory.camera_model import CameraModel
from trajectory.contracts import (
    FailureCode,
    ResidualReport,
    TrajectoryDiagnostics,
    TrajectoryFitRequest,
    TrajectoryFitResult,
)


def json_payload(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return json_payload(value.tolist())
    if isinstance(value, np.generic):
        return json_payload(value.item())
    if isinstance(value, dict):
        return {key: json_payload(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_payload(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def encode_request(request: TrajectoryFitRequest) -> str:
    return json.dumps(
        {
            "schema_version": "trajectory_worker.v1",
            "correlation_id": request.correlation_id,
            "payload": json_payload(asdict(request)),
        },
        allow_nan=False,
    )


def _camera(payload: Optional[dict]) -> Optional[CameraModel]:
    if payload is None:
        return None
    data = dict(payload)
    for key in ("R", "t", "fundamental_matrix"):
        if data.get(key) is not None:
            data[key] = np.asarray(data[key], dtype=float)
    if data.get("distortion") is not None:
        data["distortion"] = tuple(data["distortion"])
    return CameraModel(**data)


def decode_request(envelope: dict) -> TrajectoryFitRequest:
    if envelope.get("schema_version") != "trajectory_worker.v1":
        raise ValueError("unsupported trajectory worker schema")
    data = dict(envelope["payload"])
    if not data.get("correlation_id") or data["correlation_id"] != envelope.get("correlation_id"):
        raise ValueError("trajectory worker correlation mismatch")
    data["observations"] = [StereoObservation(**obs) for obs in data["observations"]]
    data["ray_observations"] = [RayObservation(**ray) for ray in data["ray_observations"]]
    data["camera_models"] = {key: _camera(value) for key, value in data["camera_models"].items()}
    for key in ("camera_left", "camera_right"):
        data[key] = _camera(data.get(key))
    return TrajectoryFitRequest(**data)


def decode_result(payload: dict) -> TrajectoryFitResult:
    data = dict(payload)
    diagnostics = dict(data["diagnostics"])
    diagnostics["failure_codes"] = [FailureCode(code) for code in diagnostics.get("failure_codes", [])]
    data["diagnostics"] = TrajectoryDiagnostics(**diagnostics)
    data["samples"] = [TrackSample(**sample) for sample in data["samples"]]
    data["residuals"] = [ResidualReport(**residual) for residual in data.get("residuals", [])]
    if data.get("plate_crossing_xyz_ft") is not None:
        data["plate_crossing_xyz_ft"] = tuple(data["plate_crossing_xyz_ft"])
    return TrajectoryFitResult(**data)

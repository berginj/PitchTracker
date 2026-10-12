"""Metric calibration, surveyed targets, and per-camera region validation."""

from __future__ import annotations

import json
from math import isfinite, sqrt
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import yaml

from app.services.rig_profile_persistence import atomic_write_text
from app.services.setup_workflow.storage import configuration_file
from calib.calibration_report import build_calibration_report
from calib.field_transform import estimate_field_transform
from contracts import Detection
from contracts.setup_workflow import FieldTarget
from stereo.calibrated_stereo import CalibratedStereoGeometry, CalibratedStereoMatcher

if TYPE_CHECKING:
    from app.services.setup_workflow.service import SetupWorkflowService


def calibration_geometry(service: SetupWorkflowService) -> CalibratedStereoGeometry:
    config = service.config
    path = service.artifact("calibration")
    with np.load(path, allow_pickle=False) as data:
        for key in ("mtx_left", "mtx_right", "dist_left", "dist_right", "R", "T", "img_size"):
            if key not in data or not np.isfinite(data[key]).all():
                raise ValueError(f"Calibration is missing finite {key}")
        if tuple(data["img_size"]) != (config.camera.width, config.camera.height):
            raise ValueError("Calibration image dimensions differ from the saved capture mode")
        if str(data.get("calibration_mode", "")) != "FULL" or not bool(data.get("production_ready", False)):
            raise ValueError("Full metric calibration is required; quick calibration remains diagnostic")
        if np.asarray(data["R"]).shape != (3, 3) or np.asarray(data["T"]).size != 3:
            raise ValueError("Calibration rotation/translation has invalid dimensions")
        if float(np.linalg.norm(data["T"])) <= 0:
            raise ValueError("Calibration has no metric baseline")
        if "rms_error_px" not in data or not isfinite(float(data["rms_error_px"])):
            raise ValueError("Calibration residual evidence is missing")
    return CalibratedStereoGeometry.from_npz(
        path, config.stereo.epipolar_epsilon_px, config.stereo.z_min_ft, config.stereo.z_max_ft,
        config.stereo.time_sync_offset_ns,
    )


def accept_calibration(service: SetupWorkflowService, source: Path, *, generated: bool) -> None:
    if source.suffix.lower() != ".npz":
        raise ValueError("Select a local stereo calibration NPZ")
    identity_path = source.with_suffix(".identity.json")
    identity = service.calibration_identity() if generated else (
        json.loads(identity_path.read_text(encoding="utf-8")) if identity_path.exists() else None
    )
    candidate = service.state
    candidate["artifacts"]["calibration"] = service._copy_file(source)
    candidate["calibration_identity"] = identity
    with np.load(source, allow_pickle=False) as data:
        if str(data.get("calibration_mode", "")) == "FULL":
            payload = yaml.safe_load(service.config_path.read_text(encoding="utf-8"))
            matrix = np.asarray(data["mtx_left"], dtype=float)
            payload["stereo"].update({
                "baseline_ft": float(np.linalg.norm(data["T"])) / 304.8,
                "focal_length_px": float(matrix[0, 0]), "cx": float(matrix[0, 2]), "cy": float(matrix[1, 2]),
            })
            candidate["config_file"] = configuration_file(service.root, payload).name
    service._edit(candidate, {"calibration", "field", "regions"})
    validate_calibration(service)


def validate_calibration(service: SetupWorkflowService) -> None:
    generation = service.generation
    try:
        calibration_geometry(service)
        if service.state.get("calibration_identity") != service.calibration_identity():
            raise ValueError("Calibration identity/transform provenance is missing or incompatible; capture a full calibration")
        # Baseline is taken from calibrated T; manual defaults cannot override metric geometry.
        report = build_calibration_report(service.artifact("calibration"))
        if report["status"] == "FAIL":
            raise ValueError("; ".join(report["errors"]))
        service.record_check("calibration", True, report, generation)
    except (OSError, ValueError, KeyError) as exc:
        service.record_check("calibration", False, {"error": str(exc)}, generation)
        raise


def _target_point(
    matcher: CalibratedStereoMatcher, target: FieldTarget, pair: dict[str, Any],
) -> tuple[tuple[float, float, float], float]:
    detections = []
    for side, pixel in (("left", target.left_pixel), ("right", target.right_pixel)):
        record = pair[side]
        if len(pixel) != 2 or not all(isfinite(value) for value in pixel):
            raise ValueError("Target pixels must contain two finite coordinates")
        if not 0 <= pixel[0] < record["width"] or not 0 <= pixel[1] < record["height"]:
            raise ValueError("Target pixel is outside its source image")
        detections.append(Detection(
            record["camera_id"], record["frame_index"], record["timestamp_ns"],
            pixel[0], pixel[1], 1.0, 1.0,
        ))
    match = matcher.match(*detections)
    if match is None:
        raise ValueError(f"Target {target.target_id} fails calibrated epipolar matching")
    observation = matcher.triangulate(match)
    point = (observation.X, observation.Y, observation.Z)
    if not all(isfinite(value) for value in point) or observation.quality <= 0:
        raise ValueError(f"Target {target.target_id} cannot be triangulated within the configured depth range")
    return point, match.epipolar_error_px


def fit_field(service: SetupWorkflowService) -> None:
    if not service.state["checks"].get("calibration", {}).get("passed"):
        raise ValueError("Validate metric calibration before fitting field targets")
    state = service.state
    rows = state["targets"]
    targets = [FieldTarget.from_payload(row) for row in rows]
    ids = [target.target_id for target in targets]
    if len(ids) != len(set(ids)) or any(not value.strip() for value in ids):
        raise ValueError("Each target needs a unique, nonblank identity")
    fitting = [target for target in targets if not target.holdout]
    holdouts = [target for target in targets if target.holdout]
    if len(fitting) < 3 or not holdouts:
        raise ValueError("Use at least three fitting targets and one separate holdout target")
    pixel_pairs = [(target.left_pixel, target.right_pixel) for target in targets]
    if len(pixel_pairs) != len(set(pixel_pairs)):
        raise ValueError("Fitting and holdout targets must be distinct observed points")
    matcher = CalibratedStereoMatcher(calibration_geometry(service))
    camera_points = {}
    epipolar_errors = []
    for target, row in zip(targets, rows):
        if len(target.field_xyz_ft) != 3 or not all(isfinite(value) for value in target.field_xyz_ft):
            raise ValueError("Surveyed field coordinates must contain three finite values in feet")
        pair = row.get("source_pair")
        if not pair or pair["config_sha256"] != state.get("latest_pair", {}).get("config_sha256"):
            raise ValueError("Target image/configuration evidence is missing or stale; recapture targets")
        if pair["correlation_id"] != state["latest_pair"]["correlation_id"]:
            raise ValueError("Confirm each target in the current captured image pair")
        if set(row.get("confirmed_sides", ["left", "right"])) != {"left", "right"}:
            raise ValueError("Click the target in both current camera views")
        if any(pair[side]["camera_id"] != state["camera_ids"][side] for side in ("left", "right")):
            raise ValueError("Target belongs to another camera pair")
        if row.get("calibration_sha256") != service.artifact("calibration").stem:
            raise ValueError("Target calibration evidence is missing or stale; recapture targets")
        point, error = _target_point(matcher, target, pair)
        camera_points[target.target_id] = point
        epipolar_errors.append(error)
    transform = estimate_field_transform(
        [camera_points[target.target_id] for target in fitting], [target.field_xyz_ft for target in fitting],
        fixture_id=state["setup_id"], max_rms_residual_ft=0.1,
    )
    holdout_errors = {
        target.target_id: sqrt(sum((a - b) ** 2 for a, b in zip(
            transform.apply(camera_points[target.target_id]), target.field_xyz_ft,
        ))) for target in holdouts
    }
    passed = transform.passes_residual_gate and max(holdout_errors.values()) <= transform.max_rms_residual_ft
    payload = {
        **transform.to_payload(), "targets": rows, "camera_points_ft": camera_points,
        "holdout_errors_ft": holdout_errors, "holdout_passed": passed,
        "calibrated_epipolar_error_px": max(epipolar_errors),
    }
    candidate = service.state
    candidate["field_transform"] = payload
    service._commit(candidate)
    service.record_check("field", passed, payload, service.generation)
    if not passed:
        raise ValueError("Field fitting or independent holdout exceeds the 0.1 ft setup gate")


def _validate_polygon(service: SetupWorkflowService, polygon: list[list[int]]) -> None:
    config = service.config
    if len(polygon) < 3:
        raise ValueError("A region needs at least three vertices")
    for x, y in polygon:
        if not (isfinite(x) and isfinite(y) and 0 <= x < config.camera.width and 0 <= y < config.camera.height):
            raise ValueError("Region vertices must be inside the saved image dimensions")
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, polygon[1:] + polygon[:1])))
    if area <= 0:
        raise ValueError("Region must have positive area")


def save_region(service: SetupWorkflowService, side: str, kind: str, polygon: list[list[int]]) -> None:
    if side not in ("left", "right") or kind not in ("lane", "plate"):
        raise ValueError("Choose a camera and lane/plate region")
    _validate_polygon(service, polygon)
    candidate = service.state
    camera_id = candidate["camera_ids"].get(side)
    if not camera_id:
        raise ValueError("Assign cameras before drawing regions")
    candidate["regions"].setdefault(f"{kind}_by_camera", {})[camera_id] = polygon
    service._edit(candidate, {"regions"})


def validate_regions(service: SetupWorkflowService) -> None:
    state = service.state
    for camera_id in state["camera_ids"].values():
        for kind in ("lane", "plate"):
            polygon = state["regions"].get(f"{kind}_by_camera", {}).get(camera_id)
            if polygon is None:
                raise ValueError(f"Draw {kind} region for {camera_id}")
            _validate_polygon(service, polygon)
    if len(state["camera_ids"]) != 2:
        raise ValueError("Two camera assignments are required")
    text = json.dumps(state["regions"], sort_keys=True)
    import hashlib
    name = hashlib.sha256(text.encode()).hexdigest() + ".json"
    atomic_write_text(service.root / name, text)
    candidate = service.state
    candidate["artifacts"]["regions"] = name
    service._commit(candidate)
    service.record_check("regions", True, {"camera_ids": state["camera_ids"]}, service.generation)

"""Reduce supervised capture evidence without camera I/O in the UI."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from app.monitoring.error_budget import ErrorBudget, MetricLimit
from calib.capture_qualification import qualify_capture
from calib.stereo_setup.focus_lock import (
    ExposureLockInput, ExposureValues, evaluate_exposure_lock, evaluate_focus_lock,
)
from calib.stereo_setup.overlap import validate_overlap
from calib.stereo_setup.rectify import coarse_rectify
from calib.sync_check import check_frame_sync, pair_timestamps
from contracts.setup_capture import SetupCapturePurpose, SetupCaptureResult
from contracts.capability_observation import CapabilityObservation
from contracts.types import Frame

if TYPE_CHECKING:
    from app.services.setup_workflow.service import SetupWorkflowService


def _image_file(service: SetupWorkflowService, image: np.ndarray) -> str:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Unable to preserve the setup image")
    data = encoded.tobytes()
    name = hashlib.sha256(data).hexdigest() + ".png"
    path = service.root / name
    if not path.exists():
        with path.open("xb") as handle:
            handle.write(data)
    return name


def apply_capture_result(service: SetupWorkflowService, result: SetupCaptureResult) -> dict[str, Any]:
    if result.assignment_generation != service.generation:
        raise ValueError("Capture belongs to an earlier setup generation")
    if result.config_sha256 != hashlib.sha256(service.config_path.read_bytes()).hexdigest():
        raise ValueError("Capture configuration no longer matches saved settings")
    ids = service.state["camera_ids"]
    streams = {"left": result.left_frames, "right": result.right_frames}
    if any(not records or any(record.camera_id != ids[side] for record in records) for side, records in streams.items()):
        raise ValueError("Capture did not return the assigned camera pair")
    for side, payload in result.capability_observations.items():
        observation = CapabilityObservation.from_payload(dict(payload))
        if observation.camera_id and observation.camera_id != ids[side]:
            raise ValueError(f"{side} capability observation belongs to another camera")
    frames = {}
    pair: dict[str, Any] = {"generation": service.generation, "config_sha256": result.config_sha256,
                            "correlation_id": result.correlation_id}
    for side, records in streams.items():
        record = records[-1]
        if record.image_path is None:
            raise ValueError("Capture image artifact is missing")
        image = np.load(record.image_path, allow_pickle=False)
        if image.shape[:2] != (record.height, record.width):
            raise ValueError("Captured image dimensions disagree with its frame contract")
        frames[side] = [
            Frame(camera_id=item.camera_id, frame_index=item.frame_index,
                  t_capture_monotonic_ns=item.t_capture_monotonic_ns,
                  width=item.width, height=item.height, pixfmt=item.pixfmt,
                  image=image if item is record else None, timing=item.timing, capture_epoch=item.capture_epoch)
            for item in records
        ]
        pair[side] = {
            "file": _image_file(service, image), "camera_id": record.camera_id,
            "frame_index": record.frame_index, "timestamp_ns": record.t_capture_monotonic_ns,
            "capture_epoch": record.capture_epoch, "width": record.width, "height": record.height,
        }
    candidate = service.state
    candidate["latest_pair"] = pair
    candidate["capture_context"] = {
        "modes": result.modes, "controls": result.controls, "capability_observations": result.capability_observations,
        "correlation_id": result.correlation_id, "errors_by_side": result.errors_by_side,
    }
    if result.purpose == SetupCapturePurpose.CALIBRATION_PAIR:
        identity = (pair["left"]["file"], pair["right"]["file"])
        if any((item["left"]["file"], item["right"]["file"]) == identity for item in candidate["captures"]):
            raise ValueError("This board pair is already saved; move the board and capture another pose")
        candidate["captures"].append(pair)
    service._commit(candidate)
    service.images = {side: frames[side][-1].image for side in streams}
    service.image_metadata = pair
    if result.purpose == SetupCapturePurpose.CHECKS:
        diagnostics = evaluate_images(service, result, frames)
        passed = all(item["passed"] for item in diagnostics["checks"].values())
        service.record_check("images", passed, diagnostics, service.generation)
        return diagnostics
    return pair


def evaluate_images(
    service: SetupWorkflowService, result: SetupCaptureResult, frames: dict[str, list[Frame]],
) -> dict[str, Any]:
    config = service.config
    left, right = frames["left"], frames["right"]
    tolerance = float(config.stereo.pairing_tolerance_ms)
    sync = check_frame_sync(left, right, tolerance, max_speed_mph=float(config.metrics.velo_bounds_mph[1]))
    budget = ErrorBudget("setup-capture-v1", "1", {
        "pair_skew_p95_ms": MetricLimit(tolerance * 0.5, tolerance, "ms"),
        "pair_skew_p99_ms": MetricLimit(tolerance * 0.75, tolerance * 1.5, "ms"),
        "frame_drop_rate": MetricLimit(0.01, 0.05, "ratio"),
        "unmatched_frame_rate": MetricLimit(0.01, 0.05, "ratio"),
        "mode_mismatch": MetricLimit(0.0, 0.0, "flag"),
        "controls_unverified": MetricLimit(0.0, 0.0, "flag"),
        "fps_shortfall_ratio_left": MetricLimit(0.05, 0.15, "ratio"),
        "fps_shortfall_ratio_right": MetricLimit(0.05, 0.15, "ratio"),
        "jitter_p95_ms_left": MetricLimit(1.0, 3.0, "ms"),
        "jitter_p95_ms_right": MetricLimit(1.0, 3.0, "ms"),
    })
    requested = {"width": config.camera.width, "height": config.camera.height, "fps": config.camera.fps,
                 "pixfmt": "YUYV" if config.camera.color_mode and config.camera.pixfmt == "GRAY8" else config.camera.pixfmt}
    modes = {side: dict(mode) for side, mode in result.modes.items()}
    for mode in modes.values():
        if mode.get("pixfmt") == "YUY2":
            mode["pixfmt"] = "YUYV"
    modes_agree = modes.get("left") == modes.get("right")
    verified = modes_agree and all(result.controls.get(side, {}).get("readback_verified") for side in frames)
    left_timestamps = [frame.t_capture_monotonic_ns for frame in left]
    right_timestamps = [frame.t_capture_monotonic_ns for frame in right]
    pair_skews, _ = pair_timestamps(left_timestamps, right_timestamps, int(tolerance * 1e6))
    qualification = qualify_capture(
        left_timestamps, right_timestamps, pair_skews,
        requested_mode=requested, negotiated_mode=modes.get("left", {}) if modes_agree else modes,
        expected_frames=result.requested_frames_per_camera, controls_verified=verified, budget=budget,
        qualification_id=result.correlation_id,
    )
    checks = {
        "pairing": {"passed": sync.passed, "details": sync.to_payload()},
        "capture": {"passed": qualification.assessment.permits_measurement
                    and qualification.assessment.status != "DEGRADED", "details": asdict(qualification)},
    }
    applied = ExposureValues(config.camera.exposure_us, config.camera.gain, float(config.camera.wb or 0))
    for side in frames:
        controls = result.controls.get(side, {})
        image = frames[side][-1].image
        focus = evaluate_focus_lock(side, image, bool(controls.get("autofocus_disabled")))
        exposure = evaluate_exposure_lock(side, ExposureLockInput(
            applied, applied if controls.get("readback_verified") else None,
            bool(controls.get("auto_exposure_disabled")), bool(controls.get("auto_white_balance_disabled")),
        ))
        checks[f"{side}_focus"] = {"passed": focus.passed, "details": focus.to_payload()}
        checks[f"{side}_controls"] = {"passed": exposure.passed, "details": exposure.to_payload()}
    overlap = validate_overlap(left[-1].image, right[-1].image)
    rectification = coarse_rectify(left[-1].image, right[-1].image)
    checks["overlap"] = {"passed": overlap.passed, "details": overlap.to_payload()}
    checks["coarse_alignment"] = {"passed": rectification.passed, "details": rectification.to_payload()}
    return {"checks": checks, "qualification": asdict(qualification),
            "note": "Pairing health does not verify optical exposure synchronization or physical accuracy."}

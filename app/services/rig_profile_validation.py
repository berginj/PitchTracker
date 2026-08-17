"""Runtime artifact validation for rig profiles."""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional, cast

import numpy as np

from calib.calibration_report import FAIL, build_calibration_report
from calib.field_transform import FieldTransform
from calib.runtime_status import REQUIRED_MATRIX_KEYS
from app.services.rig_profile_approval import (
    production_geometry_required,
    validate_config_modes,
)
from app.services.rig_profile_models import (
    CRITICAL,
    PASS,
    WARN,
    RigProfile,
    RigProfileValidation,
)
from app.services.rig_profile_persistence import sha256_file
from configs.settings import AppConfig
from contracts.physical_validation import (
    TrajectoryModeApprovalV2,
    payload_sha256,
)
from contracts.setup_snapshot import assess_setup_snapshot_payload, canonical_payload_sha256
from log_config.logger import get_logger

logger = get_logger(__name__)


def validate_for_runtime(
    profile: Optional[RigProfile],
    *,
    config: Optional[AppConfig],
    backend: Optional[str],
    left_serial: Optional[str],
    right_serial: Optional[str],
    calibration_path_fn: Any,
    roi_path_fn: Any,
    setup_snapshot_path_fn: Any,
    profile_dir_fn: Any,
    config_path: Any,
    approval_trust_keys: dict[str, bytes],
) -> RigProfileValidation:
    """Core runtime validation logic for a rig profile."""
    if profile is None:
        return RigProfileValidation(
            state=CRITICAL,
            issues=["No active rig profile and no legacy config fallback could be loaded."],
            diagnostics={"profile_id": None},
        )

    issues: list[str] = []
    warnings: list[str] = []
    diagnostics: dict[str, Any] = {
        "profile_id": profile.profile_id,
        "backend": profile.backend,
        "calibration_file": str(calibration_path_fn(profile)),
        "roi_file": str(roi_path_fn(profile)),
    }

    snapshot_assessment = (
        assess_setup_snapshot_payload(profile.setup_snapshot)
        if profile.setup_snapshot
        else None
    )
    diagnostics["setup_snapshot_present"] = snapshot_assessment is not None
    diagnostics["setup_snapshot_configuration_evidence_complete"] = bool(
        snapshot_assessment and snapshot_assessment.configuration_evidence_complete
    )
    diagnostics["setup_snapshot_blockers"] = (
        list(snapshot_assessment.blockers)
        if snapshot_assessment
        else ["SETUP_SNAPSHOT_MISSING"]
    )
    diagnostics["setup_snapshot_unavailable_fields"] = list(
        snapshot_assessment.unavailable_fields if snapshot_assessment else ()
    )
    physical_runtime = production_geometry_required(backend or profile.backend)
    if (
        profile.profile_id != "legacy"
        and physical_runtime
        and snapshot_assessment is None
    ):
        warnings.append(
            "Canonical setup-system snapshot is missing; physical accuracy claims are blocked."
        )
    elif (
        physical_runtime
        and snapshot_assessment is not None
        and not snapshot_assessment.configuration_evidence_complete
    ):
        warnings.append(
            "Canonical setup-system snapshot is incomplete; physical accuracy claims are blocked."
        )

    if (
        backend
        and profile.backend
        and backend != profile.backend
        and profile.profile_id != "legacy"
    ):
        message = f"Active rig backend is {profile.backend}, runtime requested {backend}."
        if production_geometry_required(backend):
            issues.append(message)
        else:
            warnings.append(message)

    _validate_serials(profile, left_serial, right_serial, issues)
    _validate_camera_mode(profile, config, issues)
    _validate_calibration_file(
        profile, backend, issues, warnings, diagnostics,
        calibration_path_fn, config_path,
    )
    _validate_roi_file(profile, issues, warnings, diagnostics, roi_path_fn)
    _validate_field_transform(profile, backend, issues, warnings, diagnostics)
    _validate_artifact_hashes(
        profile, issues, diagnostics,
        calibration_path_fn, roi_path_fn, setup_snapshot_path_fn,
    )
    validate_config_modes(
        profile, config, backend or profile.backend, issues, diagnostics,
        calibration_path_fn, profile_dir_fn, approval_trust_keys,
    )

    status = (profile.runtime_validation_status or "").upper()
    if status == CRITICAL:
        issues.append("Last runtime dry-run for this rig profile was CRITICAL.")
    elif status == WARN:
        warnings.append("Last runtime dry-run for this rig profile had warnings.")
    elif status == PASS:
        diagnostics["last_runtime_dry_run"] = PASS

    state = CRITICAL if issues else WARN if warnings else PASS
    accuracy_eligible = bool(diagnostics.get("trajectory_accuracy_claim_eligible"))
    snapshot_complete = bool(
        diagnostics.get("setup_snapshot_configuration_evidence_complete")
    )
    diagnostics["validated_configuration_ready"] = bool(
        state == PASS and snapshot_complete and accuracy_eligible
    )
    diagnostics["state"] = state
    return RigProfileValidation(
        state=state, issues=issues, warnings=warnings, diagnostics=diagnostics
    )


def _validate_serials(
    profile: RigProfile,
    left_serial: Optional[str],
    right_serial: Optional[str],
    issues: list[str],
) -> None:
    expected_left = profile.camera_serials.get("left")
    expected_right = profile.camera_serials.get("right")
    if left_serial and expected_left and left_serial != expected_left:
        issues.append(
            f"Left camera serial mismatch: expected {expected_left}, got {left_serial}."
        )
    if right_serial and expected_right and right_serial != expected_right:
        issues.append(
            f"Right camera serial mismatch: expected {expected_right}, got {right_serial}."
        )


def _validate_camera_mode(
    profile: RigProfile, config: Optional[AppConfig], issues: list[str]
) -> None:
    if config is None or profile.profile_id == "legacy" or not profile.camera_mode:
        return
    actual = config.camera
    for key in ("width", "height", "fps", "pixfmt", "color_mode"):
        expected = profile.camera_mode.get(key)
        requested = (
            "YUYV"
            if key == "pixfmt" and actual.color_mode and actual.pixfmt == "GRAY8"
            else getattr(actual, key)
        )
        if expected is not None and requested != expected:
            issues.append(
                f"Runtime camera {key} mismatch: rig profile requires {expected!r}, "
                f"config requested {requested!r}."
            )


def _validate_calibration_file(
    profile: RigProfile,
    backend: Optional[str],
    issues: list[str],
    warnings: list[str],
    diagnostics: dict[str, Any],
    calibration_path_fn: Any,
    config_path: Any,
) -> None:
    path = calibration_path_fn(profile)
    physical = production_geometry_required(backend)
    diagnostics["production_geometry_required"] = physical
    if not path.exists():
        if profile.profile_id == "legacy" and not physical:
            warnings.append(
                f"Calibration file not found at {path}; runtime will use scalar stereo fallback."
            )
        else:
            issues.append(f"Calibration file not found at {path}.")
        diagnostics["calibration_mode"] = "missing"
        return

    try:
        data = np.load(path, allow_pickle=True)
        missing = [key for key in REQUIRED_MATRIX_KEYS if key not in data]
        if missing:
            issues.append(
                f"Calibration file missing required matrix arrays: {', '.join(missing)}."
            )
            diagnostics["calibration_mode"] = "invalid_matrix_file"
            return

        mode = _calibration_mode(data)
        diagnostics["calibration_mode"] = mode
        diagnostics["calibration_quality"] = _npz_str(data, "quality_rating", "UNKNOWN")
        diagnostics["rms_error_px"] = _npz_float(data, "rms_error_px")

        report = build_calibration_report(path, config_path)
        diagnostics["calibration_report_status"] = report["status"]
        diagnostics["calibration_report_errors"] = list(report["errors"])
        diagnostics["calibration_report_warnings"] = list(report["warnings"])

        if physical and report["status"] == FAIL:
            issues.extend(
                _prefix_findings("Production calibration gate failed", report["errors"])
            )
        elif report["status"] == FAIL:
            warnings.extend(_prefix_findings("Calibration report", report["errors"]))
        if physical:
            warnings.extend(
                _prefix_findings("Calibration report", report["warnings"])
            )

        if mode == "QUICK":
            quick_message = (
                "Quick calibration is diagnostic/fallback-only and does not mark "
                "the rig production-ready."
            )
            if physical:
                issues.append(quick_message)
            else:
                warnings.append(quick_message)
        elif mode not in {"FULL", "UNKNOWN"}:
            warnings.append(
                f"Calibration mode is {mode}; full matrix calibration is the production default."
            )

        quality = str(diagnostics["calibration_quality"]).upper()
        if quality == "POOR":
            poor_message = (
                "Calibration quality is POOR; rerun full calibration before "
                "production if possible."
            )
            if physical:
                issues.append(poor_message)
            else:
                warnings.append(poor_message)
    except Exception as exc:
        issues.append(f"Calibration file could not be loaded: {exc}.")
        diagnostics["calibration_mode"] = "invalid_matrix_file"


def _validate_roi_file(
    profile: RigProfile,
    issues: list[str],
    warnings: list[str],
    diagnostics: dict[str, Any],
    roi_path_fn: Any,
) -> None:
    path = roi_path_fn(profile)
    if not path.exists():
        warnings.append(
            f"ROI file not found at {path}; lane/plate gating will be disabled."
        )
        diagnostics["roi_status"] = "missing"
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"ROI file could not be parsed: {exc}.")
        diagnostics["roi_status"] = "invalid_json"
        return

    bad_fields = _invalid_roi_fields(data)
    if bad_fields:
        issues.append(
            f"ROI file contains invalid polygons: {', '.join(bad_fields)}."
        )
        diagnostics["roi_status"] = "invalid_polygon"
        return

    has_lane = bool(data.get("lane") or data.get("lane_by_camera"))
    has_plate = bool(data.get("plate") or data.get("plate_by_camera"))
    diagnostics["roi_status"] = "ok"
    diagnostics["has_lane_roi"] = has_lane
    diagnostics["has_plate_roi"] = has_plate
    if not has_lane:
        warnings.append("Lane ROI is not configured.")
    if not has_plate:
        warnings.append("Plate ROI is not configured.")


def _validate_field_transform(
    profile: RigProfile,
    backend: Optional[str],
    issues: list[str],
    warnings: list[str],
    diagnostics: dict[str, Any],
) -> None:
    matrix = (profile.field_transform or {}).get("matrix_4x4")
    if not matrix:
        message = (
            "Field coordinate transform is missing; location and strike metrics "
            "are unavailable."
        )
        if production_geometry_required(backend):
            issues.append(message)
        diagnostics["field_transform_status"] = "missing"
        return
    try:
        transform = FieldTransform(
            cast(
                tuple[tuple[float, float, float, float], ...],
                tuple(tuple(float(value) for value in row) for row in matrix),
            ),
            float(profile.field_transform.get("rms_residual_ft", float("inf"))),
            str(profile.field_transform.get("fixture_id") or "unknown"),
            float(profile.field_transform.get("max_rms_residual_ft", 0.1)),
        )
        if not transform.passes_residual_gate:
            raise ValueError(
                f"RMS residual {transform.rms_residual_ft:.3f} ft exceeds "
                f"{transform.max_rms_residual_ft:.3f} ft gate"
            )
        diagnostics["field_transform_status"] = "ok"
        diagnostics["field_transform_rms_ft"] = transform.rms_residual_ft
        diagnostics["field_transform_max_rms_ft"] = transform.max_rms_residual_ft
    except (TypeError, ValueError) as exc:
        issues.append(f"Field coordinate transform is invalid: {exc}.")
        diagnostics["field_transform_status"] = "invalid"


def _validate_artifact_hashes(
    profile: RigProfile,
    issues: list[str],
    diagnostics: dict[str, Any],
    calibration_path_fn: Any,
    roi_path_fn: Any,
    setup_snapshot_path_fn: Any,
) -> None:
    checked: dict[str, bool] = {}
    for label, path in {
        "calibration": calibration_path_fn(profile),
        "roi": roi_path_fn(profile),
    }.items():
        expected = profile.artifact_hashes.get(label)
        if not expected or not path.exists():
            continue
        matches = sha256_file(path) == expected
        checked[label] = matches
        if not matches:
            issues.append(
                f"{label.capitalize()} artifact changed after rig profile persistence."
            )
    for label, payload in {
        "field_transform": profile.field_transform,
        "hardware_fingerprint": profile.hardware_fingerprint,
    }.items():
        expected = profile.artifact_hashes.get(label)
        if not expected or not payload:
            continue
        matches = payload_sha256(payload) == expected
        checked[label] = matches
        if not matches:
            issues.append(
                f"{label.replace('_', ' ').capitalize()} changed after rig profile persistence."
            )
    if profile.setup_snapshot:
        snapshot_path = setup_snapshot_path_fn(profile)
        expected = profile.artifact_hashes.get("setup_snapshot")
        matches = bool(
            expected and snapshot_path.exists() and sha256_file(snapshot_path) == expected
        )
        checked["setup_snapshot"] = matches
        if not matches:
            issues.append(
                "Setup snapshot artifact changed after rig profile persistence."
            )
        embedded_matches = canonical_payload_sha256(
            {
                key: value
                for key, value in profile.setup_snapshot.items()
                if key != "fingerprint_sha256"
            }
        ) == str(profile.setup_snapshot.get("fingerprint_sha256") or "")
        checked["setup_snapshot_fingerprint"] = embedded_matches
        if not embedded_matches:
            issues.append("Setup snapshot fingerprint is invalid.")
    for approval in profile.trajectory_mode_approvals:
        if not isinstance(approval, TrajectoryModeApprovalV2):
            continue
        label = f"approval:{approval.approval_id}"
        expected = profile.artifact_hashes.get(label)
        if not expected:
            continue
        matches = payload_sha256(approval.to_payload()) == expected
        checked[label] = matches
        if not matches:
            issues.append(
                f"Accuracy approval {approval.approval_id} changed after rig profile persistence."
            )
    diagnostics["artifact_hashes_verified"] = checked


# --- Utility helpers ---


def _calibration_mode(data: Any) -> str:
    if "calibration_mode" in data:
        return _npz_str(data, "calibration_mode", "UNKNOWN").upper()
    return "UNKNOWN"


def _npz_str(data: Any, key: str, default: str) -> str:
    if key not in data:
        return default
    value = data[key]
    try:
        if hasattr(value, "item"):
            value = value.item()
    except Exception:
        pass
    return str(value)


def _npz_float(data: Any, key: str) -> Optional[float]:
    if key not in data:
        return None
    try:
        return float(data[key])
    except Exception:
        return None


def _invalid_roi_fields(data: Mapping[str, Any]) -> list[str]:
    bad: list[str] = []
    for key in ("lane", "plate"):
        points = data.get(key)
        if points is not None and not _valid_polygon(points):
            bad.append(key)
    for key in ("lane_by_camera", "plate_by_camera"):
        by_camera = data.get(key)
        if by_camera is None:
            continue
        if not isinstance(by_camera, Mapping):
            bad.append(key)
            continue
        for camera_id, points in by_camera.items():
            if points is not None and not _valid_polygon(points):
                bad.append(f"{key}.{camera_id}")
    return bad


def _valid_polygon(points: Any) -> bool:
    if not isinstance(points, list) or len(points) < 3:
        return False
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return False
        x, y = point
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return False
    return True


def _prefix_findings(prefix: str, findings: list[str]) -> list[str]:
    return [f"{prefix}: {item}" for item in findings]

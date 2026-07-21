"""Durable rig profile contract and runtime validation helpers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np

from calib.calibration_report import FAIL, build_calibration_report
from calib.runtime_status import REQUIRED_MATRIX_KEYS
from calib.field_transform import FieldTransform
from app.services.rig_profile_models import (
    CRITICAL,
    PASS,
    SCHEMA_VERSION,
    WARN,
    RigProfile,
    RigProfileValidation,
    TrajectoryModeApproval,
    utc_now_iso,
)
from configs.settings import AppConfig
from contracts.versioning import APP_VERSION
from contracts.physical_validation import (
    DATASET_SCHEMA,
    PROTOCOL_SCHEMA,
    REPORT_SCHEMA,
    TrajectoryModeApprovalV2,
    payload_sha256,
    verify_approval_signatures,
)
from log_config.logger import get_logger

logger = get_logger(__name__)


class RigProfileService:
    """Load, save, activate, and validate Setup Doctor rig profiles."""

    def __init__(
        self,
        base_dir: Path = Path("calibration/rigs"),
        *,
        active_marker: Optional[Path] = None,
        config_path: Path = Path("configs/default.yaml"),
        approval_trust_keys: Optional[Mapping[str, bytes]] = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.active_marker = Path(active_marker) if active_marker is not None else self.base_dir / "active_profile.txt"
        self.config_path = Path(config_path)
        # Secrets belong in an OS/service trust store and are injected by the
        # caller. An empty store intentionally makes all v2 claims ineligible.
        self.approval_trust_keys = dict(approval_trust_keys or {})

    def profile_dir(self, profile_id: str) -> Path:
        return self.base_dir / profile_id

    def profile_path(self, profile_id: str) -> Path:
        return self.profile_dir(profile_id) / "rig_profile.json"

    def load(self, profile_id: str) -> RigProfile:
        path = self.profile_path(profile_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return RigProfile.from_dict(data)

    def load_active(self) -> Optional[RigProfile]:
        if not self.active_marker.exists():
            return None
        try:
            profile_id = self.active_marker.read_text(encoding="utf-8").strip()
            if not profile_id:
                return None
            return self.load(profile_id)
        except Exception as exc:
            logger.warning(f"Active rig profile could not be loaded: {exc}")
            return None

    def save(self, profile: RigProfile, *, activate: bool = False) -> RigProfile:
        self.profile_dir(profile.profile_id).mkdir(parents=True, exist_ok=True)
        hashes = dict(profile.artifact_hashes)
        for label, path in {
            "calibration": self.calibration_path(profile),
            "roi": self.roi_path(profile),
        }.items():
            if path.exists() and path.is_file():
                hashes[label] = _sha256(path)
        if profile.field_transform:
            hashes["field_transform"] = payload_sha256(profile.field_transform)
        if profile.hardware_fingerprint:
            hashes["hardware_fingerprint"] = payload_sha256(profile.hardware_fingerprint)
        for approval in profile.trajectory_mode_approvals:
            if isinstance(approval, TrajectoryModeApprovalV2):
                hashes[f"approval:{approval.approval_id}"] = payload_sha256(approval.to_payload())
        saved = replace(profile, updated_utc=utc_now_iso(), artifact_hashes=hashes)
        _atomic_write_text(self.profile_path(saved.profile_id), json.dumps(saved.to_dict(), indent=2))
        if activate:
            self.activate(saved.profile_id)
        return saved

    def activate(self, profile_id: str) -> None:
        if not self.profile_path(profile_id).exists():
            raise FileNotFoundError(f"Rig profile not found: {profile_id}")
        _atomic_write_text(self.active_marker, profile_id)

    def legacy_fallback(
        self,
        config: Optional[AppConfig] = None,
        *,
        backend: str = "uvc",
        left_serial: str = "",
        right_serial: str = "",
    ) -> RigProfile:
        """Build an unsaved profile that describes the legacy runtime paths."""
        if config is None:
            from configs.settings import load_config

            config = load_config(self.config_path)

        calibration_file = Path("calibration/stereo_calibration.npz")
        roi_file = _first_existing(
            (
                Path("rois/shared_rois.json"),
                Path("configs/roi.json"),
            ),
            default=Path("rois/shared_rois.json"),
        )
        quality_metrics = _load_legacy_quality_metrics()
        return RigProfile.from_config(
            "legacy",
            config,
            backend=backend,
            left_serial=left_serial,
            right_serial=right_serial,
            calibration_file=str(calibration_file),
            roi_file=str(roi_file),
            quality_metrics=quality_metrics,
            diagnostics={"source": "legacy_fallback", "config_path": str(self.config_path)},
        )

    def load_active_or_legacy(
        self,
        config: AppConfig,
        *,
        backend: str = "uvc",
        left_serial: str = "",
        right_serial: str = "",
    ) -> RigProfile:
        return self.load_active() or self.legacy_fallback(
            config,
            backend=backend,
            left_serial=left_serial,
            right_serial=right_serial,
        )

    def calibration_path(self, profile: RigProfile) -> Path:
        return self._resolve_profile_file(profile, profile.calibration_file)

    def roi_path(self, profile: RigProfile) -> Path:
        return self._resolve_profile_file(profile, profile.roi_file)

    def validate_for_runtime(
        self,
        profile: Optional[RigProfile] = None,
        *,
        config: Optional[AppConfig] = None,
        backend: Optional[str] = None,
        left_serial: Optional[str] = None,
        right_serial: Optional[str] = None,
    ) -> RigProfileValidation:
        if profile is None:
            if config is None:
                profile = self.load_active()
            else:
                profile = self.load_active_or_legacy(
                    config,
                    backend=backend or "uvc",
                    left_serial=left_serial or "",
                    right_serial=right_serial or "",
                )
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
            "calibration_file": str(self.calibration_path(profile)),
            "roi_file": str(self.roi_path(profile)),
        }

        if backend and profile.backend and backend != profile.backend and profile.profile_id != "legacy":
            message = f"Active rig backend is {profile.backend}, runtime requested {backend}."
            if _production_geometry_required(backend):
                issues.append(message)
            else:
                warnings.append(message)

        _validate_serials(profile, left_serial, right_serial, issues)
        _validate_camera_mode(profile, config, issues)
        self._validate_calibration_file(profile, backend, issues, warnings, diagnostics)
        self._validate_roi_file(profile, issues, warnings, diagnostics)
        _validate_field_transform(profile, backend, issues, warnings, diagnostics)
        _validate_artifact_hashes(self, profile, issues, diagnostics)
        _validate_config_modes(self, profile, config, backend or profile.backend, issues, diagnostics)

        status = (profile.runtime_validation_status or "").upper()
        if status == CRITICAL:
            issues.append("Last runtime dry-run for this rig profile was CRITICAL.")
        elif status == WARN:
            warnings.append("Last runtime dry-run for this rig profile had warnings.")
        elif status == PASS:
            diagnostics["last_runtime_dry_run"] = PASS

        state = CRITICAL if issues else WARN if warnings else PASS
        diagnostics["state"] = state
        return RigProfileValidation(state=state, issues=issues, warnings=warnings, diagnostics=diagnostics)

    def apply_profile_to_config(
        self,
        config: AppConfig,
        profile: RigProfile,
        *,
        preserve_camera_mode: bool = True,
    ) -> AppConfig:
        """Apply rig image transforms to an AppConfig without dropping other sections."""
        transforms = profile.image_transforms or {}
        camera_mode = profile.camera_mode or {}
        controls = profile.control_settings or {}
        camera = config.camera

        updates: dict[str, Any] = {
            "flip_left": bool(transforms.get("flip_left", camera.flip_left)),
            "flip_right": bool(transforms.get("flip_right", camera.flip_right)),
            "rotation_left": float(transforms.get("rotation_left", camera.rotation_left)),
            "rotation_right": float(transforms.get("rotation_right", camera.rotation_right)),
            "vertical_offset_px": int(transforms.get("vertical_offset_px", camera.vertical_offset_px)),
            "exposure_us": int(controls.get("exposure_us", camera.exposure_us)),
            "gain": float(controls.get("gain", camera.gain)),
            "wb_mode": controls.get("wb_mode", camera.wb_mode),
            "wb": controls.get("wb", camera.wb),
        }

        if not preserve_camera_mode:
            for key in ("width", "height", "fps", "pixfmt", "color_mode"):
                if key in camera_mode:
                    updates[key] = camera_mode[key]

        return replace(config, camera=replace(camera, **updates))

    def _resolve_profile_file(self, profile: RigProfile, raw_path: str) -> Path:
        path = Path(raw_path)
        candidates = [path]
        if profile.profile_id != "legacy" and not path.is_absolute():
            candidates.insert(0, self.profile_dir(profile.profile_id) / path)

        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve() if profile.profile_id != "legacy" else candidate

        if profile.profile_id != "legacy" and not path.is_absolute():
            return self.profile_dir(profile.profile_id) / path
        return path

    def _validate_calibration_file(
        self,
        profile: RigProfile,
        backend: Optional[str],
        issues: list[str],
        warnings: list[str],
        diagnostics: dict[str, Any],
    ) -> None:
        path = self.calibration_path(profile)
        production_geometry_required = _production_geometry_required(backend)
        diagnostics["production_geometry_required"] = production_geometry_required
        if not path.exists():
            if profile.profile_id == "legacy" and not production_geometry_required:
                warnings.append(f"Calibration file not found at {path}; runtime will use scalar stereo fallback.")
            else:
                issues.append(f"Calibration file not found at {path}.")
            diagnostics["calibration_mode"] = "missing"
            return

        try:
            data = np.load(path, allow_pickle=True)
            missing = [key for key in REQUIRED_MATRIX_KEYS if key not in data]
            if missing:
                issues.append(f"Calibration file missing required matrix arrays: {', '.join(missing)}.")
                diagnostics["calibration_mode"] = "invalid_matrix_file"
                return

            mode = _calibration_mode(profile, path, data)
            diagnostics["calibration_mode"] = mode
            diagnostics["calibration_quality"] = _npz_str(data, "quality_rating", "UNKNOWN")
            diagnostics["rms_error_px"] = _npz_float(data, "rms_error_px")

            report = build_calibration_report(path, self.config_path)
            diagnostics["calibration_report_status"] = report["status"]
            diagnostics["calibration_report_errors"] = list(report["errors"])
            diagnostics["calibration_report_warnings"] = list(report["warnings"])

            if production_geometry_required and report["status"] == FAIL:
                issues.extend(_prefix_findings("Production calibration gate failed", report["errors"]))
            elif report["status"] == FAIL:
                warnings.extend(_prefix_findings("Calibration report", report["errors"]))
            if production_geometry_required:
                warnings.extend(_prefix_findings("Calibration report", report["warnings"]))

            if mode == "QUICK":
                quick_message = "Quick calibration is diagnostic/fallback-only and does not mark the rig production-ready."
                if production_geometry_required:
                    issues.append(quick_message)
                else:
                    warnings.append(quick_message)
            elif mode not in {"FULL", "UNKNOWN"}:
                warnings.append(f"Calibration mode is {mode}; full matrix calibration is the production default.")

            quality = str(diagnostics["calibration_quality"]).upper()
            if quality == "POOR":
                poor_message = "Calibration quality is POOR; rerun full calibration before production if possible."
                if production_geometry_required:
                    issues.append(poor_message)
                else:
                    warnings.append(poor_message)
        except Exception as exc:
            issues.append(f"Calibration file could not be loaded: {exc}.")
            diagnostics["calibration_mode"] = "invalid_matrix_file"

    def _validate_roi_file(
        self,
        profile: RigProfile,
        issues: list[str],
        warnings: list[str],
        diagnostics: dict[str, Any],
    ) -> None:
        path = self.roi_path(profile)
        if not path.exists():
            warnings.append(f"ROI file not found at {path}; lane/plate gating will be disabled.")
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
            issues.append(f"ROI file contains invalid polygons: {', '.join(bad_fields)}.")
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


def _first_existing(paths: tuple[Path, ...], *, default: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return default


def _load_legacy_quality_metrics() -> dict[str, Any]:
    report_path = Path("calibration/report.json")
    if not report_path.exists():
        return {}
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _validate_serials(
    profile: RigProfile,
    left_serial: Optional[str],
    right_serial: Optional[str],
    issues: list[str],
) -> None:
    expected_left = profile.camera_serials.get("left")
    expected_right = profile.camera_serials.get("right")
    if left_serial and expected_left and left_serial != expected_left:
        issues.append(f"Left camera serial mismatch: expected {expected_left}, got {left_serial}.")
    if right_serial and expected_right and right_serial != expected_right:
        issues.append(f"Right camera serial mismatch: expected {expected_right}, got {right_serial}.")


def _validate_config_modes(
    service: RigProfileService,
    profile: RigProfile,
    config: Optional[AppConfig],
    backend: Optional[str],
    issues: list[str],
    diagnostics: dict[str, Any],
) -> None:
    if config is None:
        return
    allowed = {"stereo_3d", "ray_reprojection", "ray_graph"}
    trajectory = getattr(config, "trajectory", None)
    if trajectory is None:
        return
    primary_mode = getattr(trajectory, "primary_mode", None)
    compare_modes = getattr(trajectory, "compare_modes", ())
    if not isinstance(primary_mode, str):
        return
    if not isinstance(compare_modes, (list, tuple, set)):
        compare_modes = ()
    modes = [primary_mode, *compare_modes]
    invalid = sorted({mode for mode in modes if mode not in allowed})
    if invalid:
        issues.append(f"Invalid trajectory mode(s): {', '.join(invalid)}.")
        return

    diagnostics["trajectory_primary_mode"] = primary_mode
    diagnostics["trajectory_comparison_modes"] = list(compare_modes)
    physical = _production_geometry_required(backend)
    operational_approval_required = physical and primary_mode.startswith("ray_")
    diagnostics["trajectory_primary_approval_required"] = operational_approval_required

    candidates = [approval for approval in profile.trajectory_mode_approvals if approval.mode == primary_mode]
    operational_matches = [
        approval
        for approval in candidates
        if approval.rig_profile_id == profile.profile_id
        and approval.rig_profile_revision == profile.profile_revision
        and approval.software_version == APP_VERSION
        and approval.claim_ready is True
        and (
            not isinstance(approval, TrajectoryModeApprovalV2)
            or approval.lifecycle_state in {"REVIEWED", "ACTIVE"}
        )
    ]
    operationally_eligible = not operational_approval_required or bool(operational_matches)
    diagnostics["trajectory_operationally_eligible"] = operationally_eligible
    # Compatibility field: this means operational approval only. Accuracy claim
    # eligibility is intentionally separate below.
    diagnostics["trajectory_primary_approved"] = operationally_eligible
    diagnostics["trajectory_approval_software_version"] = APP_VERSION
    diagnostics["trajectory_approval_candidate_count"] = len(candidates)
    if operational_matches:
        diagnostics["trajectory_primary_approval"] = operational_matches[0].to_payload()

    if not operationally_eligible:
        mismatch_reasons = _operational_approval_blockers(candidates, profile)
        diagnostics["trajectory_primary_approval_rejections"] = mismatch_reasons
        issues.append(
            f"Primary trajectory mode {primary_mode} is not approved for physical runtime "
            f"(operational eligibility) on "
            f"rig {profile.profile_id} revision {profile.profile_revision} with software {APP_VERSION}: "
            f"{', '.join(mismatch_reasons)}. Keep stereo_3d primary or add an explicit approval."
        )

    eligibility = _accuracy_claim_eligibility(service, profile, config, primary_mode, physical)
    diagnostics["trajectory_accuracy_claim_eligible"] = eligibility["eligible"]
    diagnostics["trajectory_accuracy_claim_blockers"] = eligibility["blockers"]
    diagnostics["trajectory_accuracy_claim_approval"] = eligibility.get("approval")
    diagnostics["trajectory_pipeline_fingerprint"] = eligibility["pipeline_fingerprint"]


def _operational_approval_blockers(candidates: list[Any], profile: RigProfile) -> list[str]:
    if not candidates:
        return ["MISSING_MODE_APPROVAL"]
    reasons: list[str] = []
    if not any(item.rig_profile_id == profile.profile_id for item in candidates):
        reasons.append("RIG_PROFILE_ID_MISMATCH")
    if not any(item.rig_profile_revision == profile.profile_revision for item in candidates):
        reasons.append("RIG_PROFILE_REVISION_MISMATCH")
    if not any(item.software_version == APP_VERSION for item in candidates):
        reasons.append("SOFTWARE_VERSION_MISMATCH")
    if not any(item.claim_ready is True for item in candidates):
        reasons.append("GROUND_TRUTH_NOT_CLAIM_READY")
    return reasons or ["NO_SINGLE_APPROVAL_MATCHES_ACTIVE_RIG"]


def _accuracy_claim_eligibility(
    service: RigProfileService,
    profile: RigProfile,
    config: AppConfig,
    mode: str,
    physical: bool,
) -> dict[str, Any]:
    bindings = _measurement_bindings(service, profile, config)
    if not physical:
        return {
            "eligible": False,
            "blockers": ["NON_PHYSICAL_BACKEND_NOT_ACCURACY_CLAIM_ELIGIBLE"],
            "pipeline_fingerprint": bindings["pipeline_fingerprint"],
        }

    v2_candidates = [
        approval
        for approval in profile.trajectory_mode_approvals
        if isinstance(approval, TrajectoryModeApprovalV2) and approval.mode == mode
    ]
    if not v2_candidates:
        legacy_present = any(approval.mode == mode for approval in profile.trajectory_mode_approvals)
        return {
            "eligible": False,
            "blockers": ["LEGACY_V1_APPROVAL_NOT_ACCURACY_CLAIM_ELIGIBLE"]
            if legacy_present
            else ["MISSING_V2_ACCURACY_APPROVAL"],
            "pipeline_fingerprint": bindings["pipeline_fingerprint"],
        }

    all_blockers: list[str] = []
    for approval in v2_candidates:
        blockers = _verify_v2_approval(service, profile, approval, bindings)
        if not blockers:
            return {
                "eligible": True,
                "blockers": [],
                "approval": approval.to_payload(),
                "pipeline_fingerprint": bindings["pipeline_fingerprint"],
            }
        all_blockers.extend(f"{approval.approval_id}:{reason}" for reason in blockers)
    return {
        "eligible": False,
        "blockers": list(dict.fromkeys(all_blockers)),
        "pipeline_fingerprint": bindings["pipeline_fingerprint"],
    }


def _measurement_bindings(
    service: RigProfileService,
    profile: RigProfile,
    config: AppConfig,
) -> dict[str, str]:
    config_payload = {
        name: asdict(getattr(config, name))
        for name in (
            "camera", "stereo", "tracking", "metrics", "trajectory", "detector",
            "strike_zone", "ball",
        )
        if hasattr(config, name)
    }
    config_sha = payload_sha256(config_payload)
    hardware_sha = payload_sha256(profile.hardware_fingerprint or {"missing": True})
    field_sha = payload_sha256(profile.field_transform or {"missing": True})
    calibration_path = service.calibration_path(profile)
    calibration_sha = _sha256(calibration_path) if calibration_path.exists() else "0" * 64
    correction_payload = {
        "online_refinement_enabled": bool(getattr(config.metrics, "online_refinement_enabled", False)),
        "drag_k0_default": getattr(config.metrics, "drag_k0_default", None),
        "plate_plane_z_ft": getattr(config.metrics, "plate_plane_z_ft", None),
        "time_sync_offset_ns": getattr(config.stereo, "time_sync_offset_ns", None),
        "trajectory": asdict(config.trajectory),
    }
    correction_sha = payload_sha256(correction_payload)
    pipeline_sha = payload_sha256(
        {
            "software_version": APP_VERSION,
            "config_sha256": config_sha,
            "hardware_fingerprint_sha256": hardware_sha,
            "calibration_sha256": calibration_sha,
            "field_transform_sha256": field_sha,
            "correction_policy_sha256": correction_sha,
        }
    )
    return {
        "config_sha256": config_sha,
        "hardware_fingerprint_sha256": hardware_sha,
        "calibration_sha256": calibration_sha,
        "field_transform_sha256": field_sha,
        "correction_policy_sha256": correction_sha,
        "pipeline_fingerprint": pipeline_sha,
    }


def _verify_v2_approval(
    service: RigProfileService,
    profile: RigProfile,
    approval: TrajectoryModeApprovalV2,
    bindings: Mapping[str, str],
) -> list[str]:
    blockers: list[str] = []
    if approval.lifecycle_state != "ACTIVE":
        blockers.append(f"APPROVAL_NOT_ACTIVE:{approval.lifecycle_state}")
    if not approval.claim_ready:
        blockers.append("APPROVAL_NOT_CLAIM_READY")
    if approval.rig_profile_id != profile.profile_id:
        blockers.append("RIG_PROFILE_ID_MISMATCH")
    if approval.rig_profile_revision != profile.profile_revision:
        blockers.append("RIG_PROFILE_REVISION_MISMATCH")
    if approval.software_version != APP_VERSION:
        blockers.append("SOFTWARE_VERSION_MISMATCH")
    if datetime.now(timezone.utc) >= datetime.fromisoformat(approval.expires_utc.replace("Z", "+00:00")):
        blockers.append("APPROVAL_EXPIRED")
    for field_name in (
        "pipeline_fingerprint", "hardware_fingerprint_sha256", "config_sha256",
        "calibration_sha256", "field_transform_sha256", "correction_policy_sha256",
    ):
        if getattr(approval, field_name) != bindings[field_name]:
            blockers.append(f"{field_name.upper()}_MISMATCH")

    signed, signature_blockers = verify_approval_signatures(approval, service.approval_trust_keys)
    if not signed:
        blockers.extend(signature_blockers)

    artifacts: dict[str, tuple[str, str]] = {
        "protocol": (approval.protocol_file, approval.protocol_sha256),
        "dataset": (approval.dataset_manifest_file, approval.dataset_manifest_sha256),
        "report": (approval.ground_truth_report_file, approval.ground_truth_report_sha256),
    }
    loaded: dict[str, dict[str, Any]] = {}
    for label, (raw_path, expected_digest) in artifacts.items():
        try:
            path = _approval_artifact_path(service, profile, raw_path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON root is not an object")
            loaded[label] = payload
            digest = _sha256(path) if label == "report" else payload_sha256(payload)
            if digest != expected_digest:
                blockers.append(f"{label.upper()}_HASH_MISMATCH")
        except Exception as exc:
            blockers.append(f"{label.upper()}_ARTIFACT_INVALID:{type(exc).__name__}")

    protocol = loaded.get("protocol") or {}
    dataset = loaded.get("dataset") or {}
    report = loaded.get("report") or {}
    if protocol.get("schema_version") != PROTOCOL_SCHEMA:
        blockers.append("PROTOCOL_SCHEMA_NOT_V2")
    if dataset.get("schema_version") != DATASET_SCHEMA:
        blockers.append("DATASET_SCHEMA_NOT_V2")
    if report.get("schema_version") != REPORT_SCHEMA:
        blockers.append("REPORT_SCHEMA_NOT_V2")
    if report.get("claim_ready") is not True or report.get("accuracy_claim_eligible") is not True:
        blockers.append("REPORT_NOT_CLAIM_READY")
    for label, actual, expected in (
        ("REPORT_DATASET_ID", report.get("dataset_id"), approval.dataset_id),
        ("REPORT_TRAJECTORY_MODE", report.get("trajectory_mode"), approval.mode),
        ("REPORT_PROTOCOL_HASH", report.get("protocol_sha256"), approval.protocol_sha256),
        ("REPORT_PIPELINE_FINGERPRINT", report.get("pipeline_fingerprint"), approval.pipeline_fingerprint),
        ("REPORT_RIG_PROFILE_ID", report.get("rig_profile_id"), profile.profile_id),
        ("REPORT_RIG_PROFILE_REVISION", report.get("rig_profile_revision"), profile.profile_revision),
        ("DATASET_ID", dataset.get("dataset_id"), approval.dataset_id),
        ("DATASET_PROTOCOL_HASH", dataset.get("protocol_sha256"), approval.protocol_sha256),
        ("DATASET_PIPELINE_FINGERPRINT", dataset.get("pipeline_fingerprint"), approval.pipeline_fingerprint),
    ):
        if actual != expected:
            blockers.append(f"{label}_MISMATCH")
    return list(dict.fromkeys(blockers))


def _approval_artifact_path(service: RigProfileService, profile: RigProfile, raw_path: str) -> Path:
    root = service.profile_dir(profile.profile_id).resolve()
    path = Path(raw_path)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("approval artifact escapes rig profile directory") from exc
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _validate_camera_mode(profile: RigProfile, config: Optional[AppConfig], issues: list[str]) -> None:
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


def _validate_field_transform(
    profile: RigProfile,
    backend: Optional[str],
    issues: list[str],
    warnings: list[str],
    diagnostics: dict[str, Any],
) -> None:
    matrix = (profile.field_transform or {}).get("matrix_4x4")
    if not matrix:
        message = "Field coordinate transform is missing; location and strike metrics are unavailable."
        if _production_geometry_required(backend):
            issues.append(message)
        diagnostics["field_transform_status"] = "missing"
        return
    try:
        transform = FieldTransform(
            tuple(tuple(float(value) for value in row) for row in matrix),
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
    service: RigProfileService,
    profile: RigProfile,
    issues: list[str],
    diagnostics: dict[str, Any],
) -> None:
    checked: dict[str, bool] = {}
    for label, path in {
        "calibration": service.calibration_path(profile),
        "roi": service.roi_path(profile),
    }.items():
        expected = profile.artifact_hashes.get(label)
        if not expected or not path.exists():
            continue
        matches = _sha256(path) == expected
        checked[label] = matches
        if not matches:
            issues.append(f"{label.capitalize()} artifact changed after rig profile persistence.")
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
            issues.append(f"{label.replace('_', ' ').capitalize()} changed after rig profile persistence.")
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
            issues.append(f"Accuracy approval {approval.approval_id} changed after rig profile persistence.")
    diagnostics["artifact_hashes_verified"] = checked


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    """Replace a small durable text artifact without exposing partial contents."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _production_geometry_required(backend: Optional[str]) -> bool:
    """Return True when runtime should refuse diagnostic-only geometry."""
    backend_name = str(backend or "").lower()
    return backend_name not in {"", "sim", "simulated", "test"}


def _prefix_findings(prefix: str, findings: list[str]) -> list[str]:
    return [f"{prefix}: {item}" for item in findings]


def _calibration_mode(_profile: RigProfile, _path: Path, data: Any) -> str:
    # The durable calibration artifact is authoritative. Profile metadata may be
    # stale or copied from a legacy setup and must not upgrade an unlabelled NPZ.
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


__all__ = [
    "CRITICAL",
    "PASS",
    "WARN",
    "RigProfile",
    "RigProfileService",
    "RigProfileValidation",
    "SCHEMA_VERSION",
    "utc_now_iso",
]

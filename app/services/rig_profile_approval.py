"""Approval eligibility rules, operational blockers, and v2 verification."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.services.rig_profile_models import RigProfile
from app.services.rig_profile_persistence import sha256_file
from contracts.physical_validation import (
    DATASET_SCHEMA,
    PROTOCOL_SCHEMA,
    REPORT_SCHEMA,
    TrajectoryModeApprovalV2,
    payload_sha256,
    verify_approval_signatures,
)
from contracts.setup_snapshot import assess_setup_snapshot_payload
from contracts.versioning import APP_VERSION
from log_config.logger import get_logger

logger = get_logger(__name__)


def production_geometry_required(backend: str | None) -> bool:
    """Return True when runtime should refuse diagnostic-only geometry."""
    backend_name = str(backend or "").lower()
    return backend_name not in {"", "sim", "simulated", "test"}


def operational_approval_blockers(
    candidates: list[Any], profile: RigProfile
) -> list[str]:
    """Return reasons why no candidate satisfies operational eligibility."""
    if not candidates:
        return ["MISSING_MODE_APPROVAL"]
    reasons: list[str] = []
    if not any(item.rig_profile_id == profile.profile_id for item in candidates):
        reasons.append("RIG_PROFILE_ID_MISMATCH")
    if not any(
        item.rig_profile_revision == profile.profile_revision for item in candidates
    ):
        reasons.append("RIG_PROFILE_REVISION_MISMATCH")
    if not any(item.software_version == APP_VERSION for item in candidates):
        reasons.append("SOFTWARE_VERSION_MISMATCH")
    if not any(item.claim_ready is True for item in candidates):
        reasons.append("GROUND_TRUTH_NOT_CLAIM_READY")
    return reasons or ["NO_SINGLE_APPROVAL_MATCHES_ACTIVE_RIG"]


def measurement_bindings(
    calibration_path: Path,
    profile: RigProfile,
    config: Any,
) -> dict[str, str]:
    """Compute binding fingerprints for accuracy claim verification."""
    config_payload = {
        name: asdict(getattr(config, name))
        for name in (
            "camera",
            "stereo",
            "tracking",
            "metrics",
            "trajectory",
            "detector",
            "strike_zone",
            "ball",
        )
        if hasattr(config, name)
    }
    config_sha = payload_sha256(config_payload)
    hardware_sha = payload_sha256(profile.hardware_fingerprint or {"missing": True})
    field_sha = payload_sha256(profile.field_transform or {"missing": True})
    calibration_sha = (
        sha256_file(calibration_path) if calibration_path.exists() else "0" * 64
    )
    correction_payload = {
        "online_refinement_enabled": bool(
            getattr(config.metrics, "online_refinement_enabled", False)
        ),
        "drag_k0_default": getattr(config.metrics, "drag_k0_default", None),
        "plate_plane_z_ft": getattr(config.metrics, "plate_plane_z_ft", None),
        "time_sync_offset_ns": getattr(config.stereo, "time_sync_offset_ns", None),
        "trajectory": asdict(config.trajectory),
    }
    correction_sha = payload_sha256(correction_payload)
    setup_snapshot_sha = str(
        profile.setup_snapshot.get("fingerprint_sha256") or "0" * 64
    )
    pipeline_sha = payload_sha256(
        {
            "software_version": APP_VERSION,
            "config_sha256": config_sha,
            "hardware_fingerprint_sha256": hardware_sha,
            "calibration_sha256": calibration_sha,
            "field_transform_sha256": field_sha,
            "correction_policy_sha256": correction_sha,
            "setup_snapshot_sha256": setup_snapshot_sha,
        }
    )
    return {
        "config_sha256": config_sha,
        "hardware_fingerprint_sha256": hardware_sha,
        "calibration_sha256": calibration_sha,
        "field_transform_sha256": field_sha,
        "correction_policy_sha256": correction_sha,
        "setup_snapshot_sha256": setup_snapshot_sha,
        "pipeline_fingerprint": pipeline_sha,
    }


def accuracy_claim_eligibility(
    calibration_path: Path,
    profile_dir: Path,
    profile: RigProfile,
    config: Any,
    mode: str,
    physical: bool,
    trust_keys: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    """Evaluate whether accuracy claims are eligible for the given mode."""
    bindings = measurement_bindings(calibration_path, profile, config)
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
        legacy_present = any(
            approval.mode == mode for approval in profile.trajectory_mode_approvals
        )
        return {
            "eligible": False,
            "blockers": ["LEGACY_V1_APPROVAL_NOT_ACCURACY_CLAIM_ELIGIBLE"]
            if legacy_present
            else ["MISSING_V2_ACCURACY_APPROVAL"],
            "pipeline_fingerprint": bindings["pipeline_fingerprint"],
        }
    if not profile.setup_snapshot:
        return {
            "eligible": False,
            "blockers": ["SETUP_SNAPSHOT_MISSING"],
            "pipeline_fingerprint": bindings["pipeline_fingerprint"],
        }
    setup_assessment = assess_setup_snapshot_payload(profile.setup_snapshot)
    if not setup_assessment.configuration_evidence_complete:
        return {
            "eligible": False,
            "blockers": list(setup_assessment.blockers) or ["SETUP_SNAPSHOT_INCOMPLETE"],
            "pipeline_fingerprint": bindings["pipeline_fingerprint"],
        }

    all_blockers: list[str] = []
    for approval in v2_candidates:
        blockers = verify_v2_approval(
            profile_dir, profile, approval, bindings, trust_keys
        )
        if not blockers:
            return {
                "eligible": True,
                "blockers": [],
                "approval": approval.to_payload(),
                "pipeline_fingerprint": bindings["pipeline_fingerprint"],
            }
        all_blockers.extend(
            f"{approval.approval_id}:{reason}" for reason in blockers
        )
    return {
        "eligible": False,
        "blockers": list(dict.fromkeys(all_blockers)),
        "pipeline_fingerprint": bindings["pipeline_fingerprint"],
    }


def verify_v2_approval(
    profile_dir: Path,
    profile: RigProfile,
    approval: TrajectoryModeApprovalV2,
    bindings: Mapping[str, str],
    trust_keys: Mapping[str, bytes] | None = None,
) -> list[str]:
    """Verify a single v2 approval against current bindings and artifacts."""
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
    if datetime.now(timezone.utc) >= datetime.fromisoformat(
        approval.expires_utc.replace("Z", "+00:00")
    ):
        blockers.append("APPROVAL_EXPIRED")
    for field_name in (
        "pipeline_fingerprint",
        "hardware_fingerprint_sha256",
        "config_sha256",
        "calibration_sha256",
        "field_transform_sha256",
        "correction_policy_sha256",
    ):
        if getattr(approval, field_name) != bindings[field_name]:
            blockers.append(f"{field_name.upper()}_MISMATCH")

    signed, signature_blockers = verify_approval_signatures(
        approval, dict(trust_keys or {})
    )
    if not signed:
        blockers.extend(signature_blockers)

    artifacts: dict[str, tuple[str, str]] = {
        "protocol": (approval.protocol_file, approval.protocol_sha256),
        "dataset": (approval.dataset_manifest_file, approval.dataset_manifest_sha256),
        "report": (
            approval.ground_truth_report_file,
            approval.ground_truth_report_sha256,
        ),
    }
    loaded: dict[str, dict[str, Any]] = {}
    root = profile_dir.resolve()
    for label, (raw_path, expected_digest) in artifacts.items():
        try:
            path = _resolve_approval_artifact(root, raw_path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON root is not an object")
            loaded[label] = payload
            digest = (
                sha256_file(path)
                if label == "report"
                else payload_sha256(payload)
            )
            if digest != expected_digest:
                blockers.append(f"{label.upper()}_HASH_MISMATCH")
        except Exception as exc:
            blockers.append(
                f"{label.upper()}_ARTIFACT_INVALID:{type(exc).__name__}"
            )

    protocol = loaded.get("protocol") or {}
    dataset = loaded.get("dataset") or {}
    report = loaded.get("report") or {}
    if protocol.get("schema_version") != PROTOCOL_SCHEMA:
        blockers.append("PROTOCOL_SCHEMA_NOT_V2")
    if dataset.get("schema_version") != DATASET_SCHEMA:
        blockers.append("DATASET_SCHEMA_NOT_V2")
    if report.get("schema_version") != REPORT_SCHEMA:
        blockers.append("REPORT_SCHEMA_NOT_V2")
    if (
        report.get("claim_ready") is not True
        or report.get("accuracy_claim_eligible") is not True
    ):
        blockers.append("REPORT_NOT_CLAIM_READY")
    for label_name, actual, expected in (
        ("REPORT_DATASET_ID", report.get("dataset_id"), approval.dataset_id),
        ("REPORT_TRAJECTORY_MODE", report.get("trajectory_mode"), approval.mode),
        (
            "REPORT_PROTOCOL_HASH",
            report.get("protocol_sha256"),
            approval.protocol_sha256,
        ),
        (
            "REPORT_PIPELINE_FINGERPRINT",
            report.get("pipeline_fingerprint"),
            approval.pipeline_fingerprint,
        ),
        ("REPORT_RIG_PROFILE_ID", report.get("rig_profile_id"), profile.profile_id),
        (
            "REPORT_RIG_PROFILE_REVISION",
            report.get("rig_profile_revision"),
            profile.profile_revision,
        ),
        ("DATASET_ID", dataset.get("dataset_id"), approval.dataset_id),
        (
            "DATASET_PROTOCOL_HASH",
            dataset.get("protocol_sha256"),
            approval.protocol_sha256,
        ),
        (
            "DATASET_PIPELINE_FINGERPRINT",
            dataset.get("pipeline_fingerprint"),
            approval.pipeline_fingerprint,
        ),
    ):
        if actual != expected:
            blockers.append(f"{label_name}_MISMATCH")
    return list(dict.fromkeys(blockers))


def _resolve_approval_artifact(root: Path, raw_path: str) -> Path:
    """Resolve an approval artifact path within the profile directory."""
    path = Path(raw_path)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("approval artifact escapes rig profile directory") from exc
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def validate_config_modes(
    profile: RigProfile,
    config: Any,
    backend: str | None,
    issues: list[str],
    diagnostics: dict[str, Any],
    calibration_path_fn: Any,
    profile_dir_fn: Any,
    approval_trust_keys: dict[str, bytes],
) -> None:
    """Validate trajectory mode configuration and approval eligibility."""
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
    physical = production_geometry_required(backend)
    approval_required = physical and primary_mode.startswith("ray_")
    diagnostics["trajectory_primary_approval_required"] = approval_required

    candidates = [
        a for a in profile.trajectory_mode_approvals if a.mode == primary_mode
    ]
    operational_matches = [
        a
        for a in candidates
        if a.rig_profile_id == profile.profile_id
        and a.rig_profile_revision == profile.profile_revision
        and a.software_version == APP_VERSION
        and a.claim_ready is True
        and (
            not isinstance(a, TrajectoryModeApprovalV2)
            or a.lifecycle_state in {"REVIEWED", "ACTIVE"}
        )
    ]
    operationally_eligible = not approval_required or bool(operational_matches)
    diagnostics["trajectory_operationally_eligible"] = operationally_eligible
    diagnostics["trajectory_primary_approved"] = operationally_eligible
    diagnostics["trajectory_approval_software_version"] = APP_VERSION
    diagnostics["trajectory_approval_candidate_count"] = len(candidates)
    if operational_matches:
        diagnostics["trajectory_primary_approval"] = operational_matches[0].to_payload()

    if not operationally_eligible:
        mismatch_reasons = operational_approval_blockers(candidates, profile)
        diagnostics["trajectory_primary_approval_rejections"] = mismatch_reasons
        issues.append(
            f"Primary trajectory mode {primary_mode} is not approved for physical runtime "
            f"(operational eligibility) on "
            f"rig {profile.profile_id} revision {profile.profile_revision} "
            f"with software {APP_VERSION}: "
            f"{', '.join(mismatch_reasons)}. Keep stereo_3d primary or add an explicit approval."
        )

    eligibility = accuracy_claim_eligibility(
        calibration_path_fn(profile),
        profile_dir_fn(profile.profile_id),
        profile,
        config,
        primary_mode,
        physical,
        approval_trust_keys,
    )
    diagnostics["trajectory_accuracy_claim_eligible"] = eligibility["eligible"]
    diagnostics["trajectory_accuracy_claim_blockers"] = eligibility["blockers"]
    diagnostics["trajectory_accuracy_claim_approval"] = eligibility.get("approval")
    diagnostics["trajectory_pipeline_fingerprint"] = eligibility["pipeline_fingerprint"]

"""Assemble the canonical setup-system inventory persisted with a rig profile."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

from contracts.setup_snapshot import SetupSystemSnapshot, canonical_payload_sha256
from contracts.versioning import APP_VERSION


def assemble_setup_snapshot(
    *,
    profile: Any,
    config: Any,
    config_path: Path,
    cameras: Iterable[Any],
    capture_qualification: Any,
    capture_diagnostics: Mapping[str, Any],
    calibration_path: Path,
    roi_path: Path,
) -> SetupSystemSnapshot:
    """Build an immutable snapshot; unavailable probe data is explicit, never invented."""
    by_id = {str(getattr(camera, "hardware_id", "")): camera for camera in cameras}
    left_id = str(profile.camera_serials.get("left") or "")
    right_id = str(profile.camera_serials.get("right") or "")
    config_path = Path(config_path)
    calibration_path = Path(calibration_path)
    roi_path = Path(roi_path)
    field_payload = dict(profile.field_transform or {})
    source_revision, dirty = _source_revision()
    unavailable: list[str] = []

    camera_sections = {}
    for side, hardware_id in (("left", left_id), ("right", right_id)):
        camera = by_id.get(hardware_id)
        raw = _camera_inventory(camera, unavailable, side)
        raw.update(
            {
                "hardware_id": hardware_id,
                "requested_mode": dict(getattr(capture_qualification, "requested_mode", {}) or profile.camera_mode),
                "negotiated_mode": dict(
                    (capture_diagnostics.get("modes") or {}).get(side)
                    or getattr(capture_qualification, "negotiated_mode", {})
                    or profile.camera_mode
                ),
                "controls_readback": dict((profile.control_settings.get("readback") or {}).get(side) or {}),
            }
        )
        camera_sections[side] = raw

    qualification_payload = _jsonable(capture_qualification) if capture_qualification is not None else {}
    detector_payload = _jsonable(getattr(config, "detector", {}))
    trajectory_payload = _jsonable(getattr(config, "trajectory", {}))
    stereo_payload = _jsonable(getattr(config, "stereo", {}))
    artifact_inventory = {
        "calibration": _file_sha256(calibration_path),
        "roi": _file_sha256(roi_path),
        "field_transform": canonical_payload_sha256(field_payload),
        "config": _file_sha256(config_path),
    }
    model_path = Path(str(detector_payload.get("model_path") or "")) if detector_payload.get("model_path") else None
    if model_path is not None:
        artifact_inventory["detector_model"] = _file_sha256(model_path)
    else:
        unavailable.append("detection_tracking.detector_model_sha256:not_configured")

    sections = {
        "rig": {
            "profile_id": profile.profile_id,
            "profile_revision": profile.profile_revision,
            "backend": profile.backend,
            "camera_serials": dict(profile.camera_serials),
            "created_utc": profile.created_utc,
        },
        "software": {
            "app_version": APP_VERSION,
            "source_revision": source_revision,
            "working_tree_dirty": dirty,
            "packages": _package_versions(),
        },
        "host": {
            "os": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
        },
        "cameras": camera_sections,
        "capture_qualification": qualification_payload,
        "capture_diagnostics": dict(capture_diagnostics),
        "geometry": {
            "calibration": {
                "file": profile.calibration_file,
                "sha256": artifact_inventory["calibration"],
                "production_ready": bool(profile.production_ready),
                "profile": _jsonable(profile.stereo_profile) if profile.stereo_profile else None,
            },
            "roi": {"file": profile.roi_file, "sha256": artifact_inventory["roi"]},
            "field_transform": {
                **field_payload,
                "sha256": artifact_inventory["field_transform"],
                "passed": bool(field_payload.get("matrix_4x4"))
                and float(field_payload.get("rms_residual_ft", float("inf")))
                <= float(field_payload.get("max_rms_residual_ft", 0.0)),
            },
        },
        "detection_tracking": {
            "config_sha256": artifact_inventory["config"],
            "detector": detector_payload,
            "detector_config_sha256": canonical_payload_sha256(detector_payload),
            "detector_model_sha256": artifact_inventory.get("detector_model"),
            "pairing": stereo_payload,
            "association": {
                "algorithm": str(stereo_payload.get("association_mode") or "greedy_v1"),
                "version": "2" if "v2" in str(stereo_payload.get("association_mode") or "") else "1",
            },
        },
        "trajectory_corrections": {
            "primary_mode": str(trajectory_payload.get("primary_mode") or "stereo_3d"),
            "trajectory": trajectory_payload,
            "correction_policy_sha256": canonical_payload_sha256(
                {
                    "time_sync_offset_ns": stereo_payload.get("time_sync_offset_ns", 0),
                    "error_budget": profile.error_budget,
                    "online_refinement_enabled": bool(
                        getattr(getattr(config, "metrics", None), "online_refinement_enabled", False)
                    ),
                }
            ),
        },
        "validation": {
            "operational_status": profile.runtime_validation_status,
            "approval_ids": [
                getattr(approval, "approval_id", None) for approval in profile.trajectory_mode_approvals
            ],
            "validated_configuration_ready": False,
            "note": "Physical VALIDATED status additionally requires an exact active v2 approval and session preflight.",
        },
        "inventory_unavailable": sorted(set(unavailable)),
    }
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return SetupSystemSnapshot.create(
        snapshot_id=f"setup-{now.replace(':', '').replace('-', '')}-{uuid4().hex[:12]}",
        created_utc=now,
        rig_profile_id=profile.profile_id,
        rig_profile_revision=profile.profile_revision,
        sections=sections,
        artifact_inventory=artifact_inventory,
    )


def _camera_inventory(camera: Any, unavailable: list[str], side: str) -> dict[str, Any]:
    values = {
        "friendly_name": str(getattr(camera, "friendly_name", "") or ""),
        "model": str(getattr(camera, "model", "") or ""),
        "recognized": bool(getattr(camera, "recognized", False)),
        "global_shutter": bool(getattr(camera, "global_shutter", False)),
        "sync_capable": getattr(camera, "sync_capable", None),
        "supported_modes": list(getattr(camera, "supported_modes", ()) or ()),
        "controls": list(getattr(camera, "controls", ()) or ()),
        "instance_id": getattr(camera, "instance_id", None),
        "device_path": getattr(camera, "device_path", None),
        "usb_controller": getattr(camera, "usb_controller", None),
        "driver_version": getattr(camera, "driver_version", None),
        "firmware_version": getattr(camera, "firmware_version", None),
        "capability_score": int(getattr(camera, "capability_score", 0) or 0),
        "recommendation_reason": str(getattr(camera, "recommendation_reason", "") or ""),
    }
    for field in ("instance_id", "device_path", "usb_controller", "driver_version", "firmware_version"):
        if values[field] in {None, ""}:
            unavailable.append(f"cameras.{side}.{field}")
    return values


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return _jsonable(value.to_payload())
    return value


def _file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_revision() -> tuple[str, bool | None]:
    override = os.environ.get("PITCHTRACKER_SOURCE_REVISION")
    if override:
        return override, None
    root = Path(__file__).resolve().parents[2]
    try:
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            ).stdout.strip()
        )
        return revision, dirty
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE", None


def _package_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in ("numpy", "opencv-python", "scipy", "PySide6"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


__all__ = ["assemble_setup_snapshot"]

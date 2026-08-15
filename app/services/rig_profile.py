"""Durable rig profile contract and runtime validation helpers.

This module is a thin facade that delegates to:
- rig_profile_persistence (load, save, activate, path resolution)
- rig_profile_validation (runtime validation)
- rig_profile_approval (accuracy claims, mode approval)
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from app.services.rig_profile_models import (
    CRITICAL,
    PASS,
    SCHEMA_VERSION,
    WARN,
    RigProfile,
    RigProfileValidation,
    TrajectoryModeApproval as _TrajectoryModeApproval,
    utc_now_iso,
)
from app.services.rig_profile_persistence import (
    activate_profile,
    first_existing,
    load_active_profile,
    load_legacy_quality_metrics,
    load_profile,
    resolve_profile_file,
    save_profile,
)
from app.services.rig_profile_validation import (
    validate_for_runtime as _validate_for_runtime_core,
)
from app.services.rig_profile_approval import (
    measurement_bindings,
)
from configs.settings import AppConfig
from contracts.physical_validation import TrajectoryModeApprovalV2
from log_config.logger import get_logger

logger = get_logger(__name__)

# Preserve the historical import surface used by callers and tests.
TrajectoryModeApproval = _TrajectoryModeApproval


def _measurement_bindings(
    service: "RigProfileService",
    profile: RigProfile,
    config: AppConfig,
) -> dict[str, str]:
    """Compatibility wrapper preserving the private name used by tests."""
    return measurement_bindings(
        service.calibration_path(profile), profile, config
    )


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
        self.active_marker = (
            Path(active_marker)
            if active_marker is not None
            else self.base_dir / "active_profile.txt"
        )
        self.config_path = Path(config_path)
        self.approval_trust_keys = dict(approval_trust_keys or {})

    def profile_dir(self, profile_id: str) -> Path:
        return self.base_dir / profile_id

    def profile_path(self, profile_id: str) -> Path:
        return self.profile_dir(profile_id) / "rig_profile.json"

    def load(self, profile_id: str) -> RigProfile:
        return load_profile(self.profile_path(profile_id))

    def load_active(self) -> Optional[RigProfile]:
        return load_active_profile(self.active_marker, self.base_dir)

    def save(self, profile: RigProfile, *, activate: bool = False) -> RigProfile:
        saved = save_profile(
            self.base_dir,
            profile,
            calibration_path=self.calibration_path(profile),
            roi_path=self.roi_path(profile),
            setup_snapshot_path=self.setup_snapshot_path(profile),
            profile_path=self.profile_path(profile.profile_id),
        )
        if activate:
            self.activate(saved.profile_id)
        return saved

    def activate(self, profile_id: str) -> None:
        activate_profile(
            self.active_marker, self.profile_path(profile_id), profile_id
        )

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
        roi_file = first_existing(
            (Path("rois/shared_rois.json"), Path("configs/roi.json")),
            default=Path("rois/shared_rois.json"),
        )
        quality_metrics = load_legacy_quality_metrics()
        return RigProfile.from_config(
            "legacy",
            config,
            backend=backend,
            left_serial=left_serial,
            right_serial=right_serial,
            calibration_file=str(calibration_file),
            roi_file=str(roi_file),
            quality_metrics=quality_metrics,
            diagnostics={
                "source": "legacy_fallback",
                "config_path": str(self.config_path),
            },
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
        return resolve_profile_file(
            self.base_dir, profile, profile.calibration_file
        )

    def roi_path(self, profile: RigProfile) -> Path:
        return resolve_profile_file(self.base_dir, profile, profile.roi_file)

    def setup_snapshot_path(self, profile: RigProfile) -> Path:
        return resolve_profile_file(
            self.base_dir, profile, profile.setup_snapshot_file
        )

    def previously_validated_camera_pairs(self) -> list[dict[str, Any]]:
        """Return non-expired ACTIVE v2-approved pairs for recommendation only."""
        pairs: list[dict[str, Any]] = []
        if not self.base_dir.exists():
            return pairs
        now = datetime.now(timezone.utc)
        for path in sorted(self.base_dir.glob("*/rig_profile.json")):
            try:
                profile = RigProfile.from_dict(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except Exception:
                continue
            qualifying = [
                a
                for a in profile.trajectory_mode_approvals
                if isinstance(a, TrajectoryModeApprovalV2)
                and a.lifecycle_state == "ACTIVE"
                and a.claim_ready
                and _not_expired(a, now)
            ]
            if not qualifying:
                continue
            left = str(profile.camera_serials.get("left") or "")
            right = str(profile.camera_serials.get("right") or "")
            if not left or not right or left == right:
                continue
            pairs.append(
                {
                    "left_id": left,
                    "right_id": right,
                    "profile_id": profile.profile_id,
                    "profile_revision": profile.profile_revision,
                    "approval_ids": [a.approval_id for a in qualifying],
                    "updated_utc": profile.updated_utc,
                }
            )
        return sorted(
            pairs,
            key=lambda p: (
                str(p.get("updated_utc") or ""),
                int(p.get("profile_revision") or 0),
            ),
            reverse=True,
        )

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
        return _validate_for_runtime_core(
            profile,
            config=config,
            backend=backend,
            left_serial=left_serial,
            right_serial=right_serial,
            calibration_path_fn=self.calibration_path,
            roi_path_fn=self.roi_path,
            setup_snapshot_path_fn=self.setup_snapshot_path,
            profile_dir_fn=self.profile_dir,
            config_path=self.config_path,
            approval_trust_keys=self.approval_trust_keys,
        )

    def apply_profile_to_config(
        self,
        config: AppConfig,
        profile: RigProfile,
        *,
        preserve_camera_mode: bool = True,
    ) -> AppConfig:
        """Apply rig image transforms to an AppConfig."""
        transforms = profile.image_transforms or {}
        camera_mode = profile.camera_mode or {}
        controls = profile.control_settings or {}
        camera = config.camera

        updates: dict[str, Any] = {
            "flip_left": bool(transforms.get("flip_left", camera.flip_left)),
            "flip_right": bool(transforms.get("flip_right", camera.flip_right)),
            "rotation_left": float(
                transforms.get("rotation_left", camera.rotation_left)
            ),
            "rotation_right": float(
                transforms.get("rotation_right", camera.rotation_right)
            ),
            "vertical_offset_px": int(
                transforms.get("vertical_offset_px", camera.vertical_offset_px)
            ),
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


def _not_expired(approval: TrajectoryModeApprovalV2, now: datetime) -> bool:
    """Check if approval has not expired."""
    try:
        expires = datetime.fromisoformat(approval.expires_utc.replace("Z", "+00:00"))
    except ValueError:
        return False
    return expires > now


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

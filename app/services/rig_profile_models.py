"""Rig profile data contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from configs.settings import AppConfig
from contracts.setup import StereoCalibrationProfile

SCHEMA_VERSION = "1.0"
PASS = "PASS"
WARN = "WARN"
CRITICAL = "CRITICAL"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RigProfile:
    """Durable camera rig profile produced by Setup Doctor."""

    schema_version: str
    profile_id: str
    created_utc: str
    updated_utc: str
    backend: str
    camera_serials: dict[str, str] = field(default_factory=dict)
    camera_mode: dict[str, Any] = field(default_factory=dict)
    image_transforms: dict[str, Any] = field(default_factory=dict)
    calibration_file: str = "stereo_calibration.npz"
    roi_file: str = "roi.json"
    board_metadata: dict[str, Any] = field(default_factory=dict)
    quality_metrics: dict[str, Any] = field(default_factory=dict)
    runtime_validation_status: Optional[str] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    stereo_profile: Optional[StereoCalibrationProfile] = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RigProfile":
        now = utc_now_iso()
        stereo_raw = data.get("stereo_profile")
        stereo_profile = (
            StereoCalibrationProfile.from_payload(dict(stereo_raw)) if isinstance(stereo_raw, Mapping) else None
        )
        return cls(
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            profile_id=str(data["profile_id"]),
            created_utc=str(data.get("created_utc") or now),
            updated_utc=str(data.get("updated_utc") or now),
            backend=str(data.get("backend") or "uvc"),
            camera_serials=dict(data.get("camera_serials") or {}),
            camera_mode=dict(data.get("camera_mode") or {}),
            image_transforms=dict(data.get("image_transforms") or {}),
            calibration_file=str(data.get("calibration_file") or "stereo_calibration.npz"),
            roi_file=str(data.get("roi_file") or "roi.json"),
            board_metadata=dict(data.get("board_metadata") or {}),
            quality_metrics=dict(data.get("quality_metrics") or {}),
            runtime_validation_status=data.get("runtime_validation_status"),
            diagnostics=dict(data.get("diagnostics") or {}),
            stereo_profile=stereo_profile,
        )

    @classmethod
    def from_config(
        cls,
        profile_id: str,
        config: AppConfig,
        *,
        backend: str,
        left_serial: str = "",
        right_serial: str = "",
        calibration_file: str = "stereo_calibration.npz",
        roi_file: str = "roi.json",
        quality_metrics: Optional[dict[str, Any]] = None,
        diagnostics: Optional[dict[str, Any]] = None,
    ) -> "RigProfile":
        now = utc_now_iso()
        camera = config.camera
        return cls(
            schema_version=SCHEMA_VERSION,
            profile_id=profile_id,
            created_utc=now,
            updated_utc=now,
            backend=backend,
            camera_serials={"left": left_serial, "right": right_serial},
            camera_mode={
                "width": camera.width,
                "height": camera.height,
                "fps": camera.fps,
                "pixfmt": camera.pixfmt,
                "color_mode": camera.color_mode,
            },
            image_transforms={
                "flip_left": camera.flip_left,
                "flip_right": camera.flip_right,
                "rotation_left": camera.rotation_left,
                "rotation_right": camera.rotation_right,
                "vertical_offset_px": camera.vertical_offset_px,
            },
            calibration_file=calibration_file,
            roi_file=roi_file,
            quality_metrics=quality_metrics or {},
            diagnostics=diagnostics or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def production_ready(self) -> bool:
        """True only when a nested, production-validated stereo profile exists."""
        return bool(self.stereo_profile and self.stereo_profile.production_ready)


@dataclass(frozen=True)
class RigProfileValidation:
    """Setup Doctor validation result for runtime startup."""

    state: str
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        return self.state == CRITICAL

    @property
    def has_warnings(self) -> bool:
        return self.state == WARN


__all__ = [
    "CRITICAL",
    "PASS",
    "WARN",
    "RigProfile",
    "RigProfileValidation",
    "SCHEMA_VERSION",
    "utc_now_iso",
]

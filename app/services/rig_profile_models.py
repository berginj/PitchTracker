"""Rig profile data contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from configs.settings import AppConfig
from contracts.physical_validation import APPROVAL_SCHEMA, TrajectoryModeApprovalV2
from contracts.setup import StereoCalibrationProfile

SCHEMA_VERSION = "2.0"
PASS = "PASS"
WARN = "WARN"
CRITICAL = "CRITICAL"
TRAJECTORY_MODES = frozenset({"stereo_3d", "ray_reprojection", "ray_graph"})


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TrajectoryModeApproval:
    """Evidence binding a claim-ready trajectory mode to one exact rig build."""

    mode: str
    rig_profile_id: str
    rig_profile_revision: int
    software_version: str
    dataset_id: str
    ground_truth_report_sha256: str
    claim_ready: bool
    schema_version: str = "trajectory_mode_approval.v1"

    def __post_init__(self) -> None:
        if self.mode not in TRAJECTORY_MODES:
            raise ValueError(f"unsupported trajectory approval mode: {self.mode!r}")
        for label, value in {
            "rig_profile_id": self.rig_profile_id,
            "software_version": self.software_version,
            "dataset_id": self.dataset_id,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"trajectory approval {label} is required")
        if (
            not isinstance(self.rig_profile_revision, int)
            or isinstance(self.rig_profile_revision, bool)
            or self.rig_profile_revision < 1
        ):
            raise ValueError("trajectory approval rig_profile_revision must be positive")
        digest = self.ground_truth_report_sha256
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise ValueError("trajectory approval ground_truth_report_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(self.claim_ready, bool):
            raise ValueError("trajectory approval claim_ready must be boolean")
        if self.schema_version != "trajectory_mode_approval.v1":
            raise ValueError(f"unsupported trajectory approval schema: {self.schema_version!r}")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "TrajectoryModeApproval":
        return cls(
            mode=str(payload.get("mode") or ""),
            rig_profile_id=str(payload.get("rig_profile_id") or ""),
            rig_profile_revision=payload.get("rig_profile_revision", 0),
            software_version=str(payload.get("software_version") or ""),
            dataset_id=str(payload.get("dataset_id") or ""),
            ground_truth_report_sha256=str(payload.get("ground_truth_report_sha256") or ""),
            claim_ready=bool(payload.get("claim_ready", False)),
            schema_version=str(payload.get("schema_version") or "trajectory_mode_approval.v1"),
        )

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


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
    profile_revision: int = 1
    hardware_fingerprint: dict[str, Any] = field(default_factory=dict)
    control_settings: dict[str, Any] = field(default_factory=dict)
    field_transform: dict[str, Any] = field(default_factory=dict)
    approved_modes: list[dict[str, Any]] = field(default_factory=list)
    trajectory_mode_approvals: tuple[TrajectoryModeApproval | TrajectoryModeApprovalV2, ...] = ()
    error_budget: dict[str, Any] = field(default_factory=dict)
    artifact_hashes: dict[str, str] = field(default_factory=dict)
    setup_snapshot_file: str = "setup_snapshot.json"
    setup_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def left_serial(self) -> str:
        """Compatibility accessor for the canonical left camera assignment."""
        return self.camera_serials.get("left", "")

    @property
    def right_serial(self) -> str:
        """Compatibility accessor for the canonical right camera assignment."""
        return self.camera_serials.get("right", "")

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
            profile_revision=int(data.get("profile_revision", 1)),
            hardware_fingerprint=dict(data.get("hardware_fingerprint") or {}),
            control_settings=dict(data.get("control_settings") or {}),
            field_transform=dict(data.get("field_transform") or {}),
            approved_modes=[dict(item) for item in (data.get("approved_modes") or [])],
            trajectory_mode_approvals=_parse_trajectory_mode_approvals(data.get("trajectory_mode_approvals")),
            error_budget=dict(data.get("error_budget") or {}),
            artifact_hashes=dict(data.get("artifact_hashes") or {}),
            setup_snapshot_file=str(data.get("setup_snapshot_file") or "setup_snapshot.json"),
            setup_snapshot=dict(data.get("setup_snapshot") or {}),
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
        effective_pixfmt = "YUYV" if camera.color_mode and camera.pixfmt == "GRAY8" else camera.pixfmt
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
                "pixfmt": effective_pixfmt,
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
            hardware_fingerprint={
                "backend": backend,
                "left_serial": left_serial,
                "right_serial": right_serial,
            },
            control_settings={
                "exposure_us": camera.exposure_us,
                "gain": camera.gain,
                "wb_mode": camera.wb_mode,
                "wb": camera.wb,
            },
            approved_modes=[
                {
                    "width": camera.width,
                    "height": camera.height,
                    "fps": camera.fps,
                    "pixfmt": effective_pixfmt,
                    "color_mode": camera.color_mode,
                }
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def production_ready(self) -> bool:
        """True only when a nested, production-validated stereo profile exists."""
        return bool(self.stereo_profile and self.stereo_profile.production_ready)


def _parse_trajectory_mode_approvals(
    raw: Any,
) -> tuple[TrajectoryModeApproval | TrajectoryModeApprovalV2, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise ValueError("trajectory_mode_approvals must be a list")
    approvals: list[TrajectoryModeApproval | TrajectoryModeApprovalV2] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("each trajectory mode approval must be an object")
        schema = str(item.get("schema_version") or "trajectory_mode_approval.v1")
        approvals.append(
            TrajectoryModeApprovalV2.from_payload(item)
            if schema == APPROVAL_SCHEMA
            else TrajectoryModeApproval.from_payload(item)
        )
    return tuple(approvals)


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
    "TRAJECTORY_MODES",
    "TrajectoryModeApproval",
    "TrajectoryModeApprovalV2",
    "utc_now_iso",
]

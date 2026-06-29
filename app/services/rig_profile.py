"""Durable rig profile contract and runtime validation helpers."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np

from calib.calibration_report import FAIL, build_calibration_report
from calib.runtime_status import REQUIRED_MATRIX_KEYS
from app.services.rig_profile_models import (
    CRITICAL,
    PASS,
    SCHEMA_VERSION,
    WARN,
    RigProfile,
    RigProfileValidation,
    utc_now_iso,
)
from configs.settings import AppConfig
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
    ) -> None:
        self.base_dir = Path(base_dir)
        self.active_marker = Path(active_marker) if active_marker is not None else self.base_dir / "active_profile.txt"
        self.config_path = Path(config_path)

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
        saved = replace(profile, updated_utc=utc_now_iso())
        self.profile_path(saved.profile_id).write_text(
            json.dumps(saved.to_dict(), indent=2),
            encoding="utf-8",
        )
        if activate:
            self.activate(saved.profile_id)
        return saved

    def activate(self, profile_id: str) -> None:
        if not self.profile_path(profile_id).exists():
            raise FileNotFoundError(f"Rig profile not found: {profile_id}")
        self.active_marker.parent.mkdir(parents=True, exist_ok=True)
        self.active_marker.write_text(profile_id, encoding="utf-8")

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
            warnings.append(f"Active rig backend is {profile.backend}, runtime requested {backend}.")

        _validate_serials(profile, left_serial, right_serial, issues)
        self._validate_calibration_file(profile, backend, issues, warnings, diagnostics)
        self._validate_roi_file(profile, issues, warnings, diagnostics)
        _validate_config_modes(config, issues)

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
        camera = config.camera

        updates: dict[str, Any] = {
            "flip_left": bool(transforms.get("flip_left", camera.flip_left)),
            "flip_right": bool(transforms.get("flip_right", camera.flip_right)),
            "rotation_left": float(transforms.get("rotation_left", camera.rotation_left)),
            "rotation_right": float(transforms.get("rotation_right", camera.rotation_right)),
            "vertical_offset_px": int(transforms.get("vertical_offset_px", camera.vertical_offset_px)),
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


def _validate_config_modes(config: Optional[AppConfig], issues: list[str]) -> None:
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


def _production_geometry_required(backend: Optional[str]) -> bool:
    """Return True when runtime should refuse diagnostic-only geometry."""
    backend_name = str(backend or "").lower()
    return backend_name not in {"", "sim", "simulated", "test"}


def _prefix_findings(prefix: str, findings: list[str]) -> list[str]:
    return [f"{prefix}: {item}" for item in findings]


def _calibration_mode(profile: RigProfile, path: Path, data: Any) -> str:
    profile_mode = str(profile.quality_metrics.get("calibration_mode") or "").upper()
    if profile_mode:
        return profile_mode
    if "calibration_mode" in data:
        return _npz_str(data, "calibration_mode", "UNKNOWN").upper()
    report_path = path.with_name("report.json")
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report_mode = str(report.get("calibration_mode") or "").upper()
            if report_mode:
                return report_mode
        except Exception:
            pass
    return "FULL"


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

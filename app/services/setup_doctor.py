"""Setup Doctor staged rig-readiness workflow."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from app.services.rig_profile import CRITICAL, PASS, WARN, RigProfile, RigProfileService, RigProfileValidation
from app.services.rig_profile_models import utc_now_iso
from configs.settings import AppConfig


STAGE_NAMES = (
    "Camera identity",
    "Camera stability",
    "Orientation and software correction",
    "Overlap and toe-in",
    "ChArUco metadata",
    "Calibration capture quality",
    "Full stereo calibration",
    "ROI setup",
    "Runtime dry-run",
)


@dataclass(frozen=True)
class SetupDoctorStageResult:
    stage: str
    state: str
    notes: str
    details: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SetupDoctorReport:
    schema_version: str
    created_utc: str
    profile_id: str
    overall_state: str
    stage_results: list[SetupDoctorStageResult]
    validation_state: str
    validation_issues: list[str]
    validation_warnings: list[str]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stage_results"] = [result.to_dict() for result in self.stage_results]
        return data


class SetupDoctorWorkflow:
    """Evaluate Setup Doctor stages against the active rig profile."""

    def __init__(
        self,
        profile_service: RigProfileService,
        *,
        config: Optional[AppConfig],
        backend: str,
        left_serial: Optional[str],
        right_serial: Optional[str],
    ) -> None:
        self.profile_service = profile_service
        self.config = config
        self.backend = backend
        self.left_serial = left_serial
        self.right_serial = right_serial

    def load_profile(self) -> Optional[RigProfile]:
        profile = self.profile_service.load_active()
        if profile is None and self.config is not None:
            profile = self.profile_service.legacy_fallback(
                self.config,
                backend=self.backend,
                left_serial=self.left_serial or "",
                right_serial=self.right_serial or "",
            )
        return profile

    def validate(self, profile: Optional[RigProfile] = None) -> RigProfileValidation:
        return self.profile_service.validate_for_runtime(
            profile,
            config=self.config,
            backend=self.backend,
            left_serial=self.left_serial,
            right_serial=self.right_serial,
        )

    def run_stage(self, stage: str, profile: Optional[RigProfile] = None) -> SetupDoctorStageResult:
        profile = profile or self.load_profile()
        validation = self.validate(profile)
        if profile is None:
            return SetupDoctorStageResult(stage, CRITICAL, "No rig profile loaded.", validation.issues)
        if stage == "Camera identity":
            return self._camera_identity(profile, validation)
        if stage == "Camera stability":
            return self._camera_stability(profile)
        if stage == "Orientation and software correction":
            return self._orientation(profile)
        if stage == "Overlap and toe-in":
            return self._overlap(profile)
        if stage == "ChArUco metadata":
            return self._board_metadata(profile)
        if stage == "Calibration capture quality":
            return self._capture_quality(profile)
        if stage == "Full stereo calibration":
            return self._full_calibration(validation)
        if stage == "ROI setup":
            return self._roi_setup(validation)
        if stage == "Runtime dry-run":
            return self._runtime_dry_run(validation)
        return SetupDoctorStageResult(stage, WARN, "Unknown Setup Doctor stage.", [])

    def run_all(self) -> SetupDoctorReport:
        profile = self.load_profile()
        validation = self.validate(profile)
        results = [self.run_stage(stage, profile) for stage in STAGE_NAMES]
        overall = _aggregate_state([result.state for result in results])
        return SetupDoctorReport(
            schema_version="1.0",
            created_utc=utc_now_iso(),
            profile_id=profile.profile_id if profile is not None else "<none>",
            overall_state=overall,
            stage_results=results,
            validation_state=validation.state,
            validation_issues=validation.issues,
            validation_warnings=validation.warnings,
            diagnostics=validation.diagnostics,
        )

    def save_report(self, report: SetupDoctorReport, profile: Optional[RigProfile] = None) -> Path:
        profile = profile or self.load_profile()
        if profile is not None and profile.profile_id != "legacy":
            report_path = self.profile_service.profile_dir(profile.profile_id) / "setup_report.json"
        else:
            report_path = self.profile_service.base_dir / "legacy_setup_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        return report_path

    def _camera_identity(self, profile: RigProfile, validation: RigProfileValidation) -> SetupDoctorStageResult:
        details: list[str] = []
        expected_left = profile.camera_serials.get("left")
        expected_right = profile.camera_serials.get("right")
        if self.backend != profile.backend and profile.profile_id != "legacy":
            details.append(f"Backend mismatch: expected {profile.backend}, runtime requested {self.backend}.")
        for label, expected, actual in (
            ("Left", expected_left, self.left_serial),
            ("Right", expected_right, self.right_serial),
        ):
            if expected and actual and expected != actual:
                details.append(f"{label} serial mismatch: expected {expected}, got {actual}.")
            elif expected and not actual:
                details.append(f"{label} runtime serial was not available for confirmation.")
            elif not expected:
                details.append(f"{label} profile serial is not recorded.")
        serial_issues = [item for item in validation.issues if "serial mismatch" in item.lower()]
        if serial_issues:
            return SetupDoctorStageResult("Camera identity", CRITICAL, "Camera identity does not match.", serial_issues)
        if details:
            return SetupDoctorStageResult("Camera identity", WARN, "Camera identity needs operator confirmation.", details)
        return SetupDoctorStageResult("Camera identity", PASS, "Camera serials and backend match.", [])

    def _camera_stability(self, profile: RigProfile) -> SetupDoctorStageResult:
        status = _profile_value(profile, "camera_stability_status", "stability_status")
        samples = _profile_number(profile, "stability_samples", "camera_stability_samples")
        dropped = _profile_number(profile, "dropped_frame_ratio", "frame_drop_ratio")
        details = []
        if samples is not None:
            details.append(f"Stability samples: {int(samples)}.")
        if dropped is not None:
            details.append(f"Dropped frame ratio: {dropped:.3f}.")
        if str(status).upper() == CRITICAL or (dropped is not None and dropped > 0.05):
            return SetupDoctorStageResult("Camera stability", CRITICAL, "Camera capture is unstable.", details)
        if str(status).upper() == PASS and samples:
            return SetupDoctorStageResult("Camera stability", PASS, "Camera stability sample passed.", details)
        return SetupDoctorStageResult("Camera stability", WARN, "No recent camera stability sample is recorded.", details)

    def _orientation(self, profile: RigProfile) -> SetupDoctorStageResult:
        transforms = profile.image_transforms or {}
        try:
            left_rot = float(transforms.get("rotation_left", 0.0))
            right_rot = float(transforms.get("rotation_right", 0.0))
            vertical = int(transforms.get("vertical_offset_px", 0))
        except (TypeError, ValueError) as exc:
            return SetupDoctorStageResult(
                "Orientation and software correction",
                CRITICAL,
                "Image transform metadata is invalid.",
                [str(exc)],
            )
        details = [f"Left rotation {left_rot:.2f} deg.", f"Right rotation {right_rot:.2f} deg.", f"Vertical offset {vertical}px."]
        if max(abs(left_rot), abs(right_rot)) > 10 or abs(vertical) > 40:
            return SetupDoctorStageResult(
                "Orientation and software correction",
                WARN,
                "Large software correction recorded; physical adjustment is preferred.",
                details,
            )
        return SetupDoctorStageResult("Orientation and software correction", PASS, "Software correction metadata is usable.", details)

    def _overlap(self, profile: RigProfile) -> SetupDoctorStageResult:
        quality = str(_profile_value(profile, "alignment_quality", "overlap_quality", default="")).upper()
        convergence = _profile_number(profile, "convergence_std_px", "toin_std_px")
        scale = _profile_number(profile, "scale_mismatch_pct")
        overlap = _profile_number(profile, "overlap_score")
        details = []
        if quality:
            details.append(f"Alignment quality: {quality}.")
        if convergence is not None:
            details.append(f"Toe-in variation: {convergence:.1f}px.")
        if scale is not None:
            details.append(f"Scale mismatch: {scale:.1f}%.")
        if overlap is not None:
            details.append(f"Overlap score: {overlap:.2f}.")
        if quality == CRITICAL or (convergence is not None and convergence > 40) or (scale is not None and scale > 15):
            return SetupDoctorStageResult("Overlap and toe-in", CRITICAL, "Physical camera alignment is not production-ready.", details)
        if overlap is not None and overlap < 0.25:
            return SetupDoctorStageResult("Overlap and toe-in", CRITICAL, "Insufficient shared field of view.", details)
        if quality in {"EXCELLENT", "GOOD", PASS}:
            return SetupDoctorStageResult("Overlap and toe-in", PASS, "Overlap and toe-in diagnostics passed.", details)
        return SetupDoctorStageResult("Overlap and toe-in", WARN, "No complete overlap/toe-in diagnostic is recorded.", details)

    def _board_metadata(self, profile: RigProfile) -> SetupDoctorStageResult:
        metadata = profile.board_metadata or {}
        required = ("pattern", "square_size_mm", "marker_dictionary")
        missing = [key for key in required if not metadata.get(key)]
        if missing:
            return SetupDoctorStageResult("ChArUco metadata", WARN, "Board metadata is incomplete.", [f"Missing: {', '.join(missing)}."])
        return SetupDoctorStageResult("ChArUco metadata", PASS, "Board metadata is complete.", [f"{key}: {metadata[key]}" for key in required])

    def _capture_quality(self, profile: RigProfile) -> SetupDoctorStageResult:
        pose_count = _profile_number(profile, "valid_pose_pairs", "pose_pairs", "capture_pose_count", "valid_pairs")
        rejected = _profile_number(profile, "rejected_pose_pairs", "rejected_pairs")
        details = []
        if pose_count is not None:
            details.append(f"Valid stereo poses: {int(pose_count)}.")
        if rejected is not None:
            details.append(f"Rejected pose pairs: {int(rejected)}.")
        if pose_count is None:
            return SetupDoctorStageResult("Calibration capture quality", WARN, "No calibration capture-quality metrics are recorded.", details)
        if pose_count < 10:
            return SetupDoctorStageResult("Calibration capture quality", WARN, "Capture set is below the 10-pose production minimum.", details)
        return SetupDoctorStageResult("Calibration capture quality", PASS, "Calibration capture set is large enough for production.", details)

    def _full_calibration(self, validation: RigProfileValidation) -> SetupDoctorStageResult:
        mode = str(validation.diagnostics.get("calibration_mode", "missing"))
        if mode == "invalid_matrix_file":
            return SetupDoctorStageResult("Full stereo calibration", CRITICAL, "Matrix calibration file is invalid.", validation.issues)
        if mode == "missing":
            state = WARN if validation.state != CRITICAL else CRITICAL
            return SetupDoctorStageResult("Full stereo calibration", state, "Matrix calibration file is missing.", validation.issues)
        if mode == "QUICK":
            return SetupDoctorStageResult("Full stereo calibration", WARN, "Quick calibration is diagnostic/fallback-only.", validation.warnings)
        return SetupDoctorStageResult("Full stereo calibration", PASS, "Full matrix calibration is available.", [])

    def _roi_setup(self, validation: RigProfileValidation) -> SetupDoctorStageResult:
        status = str(validation.diagnostics.get("roi_status", "missing"))
        if status.startswith("invalid"):
            return SetupDoctorStageResult("ROI setup", CRITICAL, "ROI file is invalid.", validation.issues)
        if status == "missing":
            return SetupDoctorStageResult("ROI setup", WARN, "ROI file is missing.", validation.warnings)
        if not validation.diagnostics.get("has_lane_roi") or not validation.diagnostics.get("has_plate_roi"):
            return SetupDoctorStageResult("ROI setup", WARN, "Lane or plate ROI is missing.", validation.warnings)
        return SetupDoctorStageResult("ROI setup", PASS, "Lane and plate ROIs are available.", [])

    def _runtime_dry_run(self, validation: RigProfileValidation) -> SetupDoctorStageResult:
        if validation.state == CRITICAL:
            return SetupDoctorStageResult("Runtime dry-run", CRITICAL, "Runtime validation has critical issues.", validation.issues)
        if validation.state == WARN:
            return SetupDoctorStageResult("Runtime dry-run", WARN, "Runtime validation has warnings.", validation.warnings)
        return SetupDoctorStageResult("Runtime dry-run", PASS, "Runtime validation passed.", [])


def _aggregate_state(states: list[str]) -> str:
    if CRITICAL in states:
        return CRITICAL
    if WARN in states:
        return WARN
    return PASS


def _profile_value(profile: RigProfile, *keys: str, default: Any = None) -> Any:
    for source in (profile.quality_metrics, profile.diagnostics):
        for key in keys:
            if key in source:
                return source[key]
    return default


def _profile_number(profile: RigProfile, *keys: str) -> Optional[float]:
    value = _profile_value(profile, *keys)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "STAGE_NAMES",
    "SetupDoctorReport",
    "SetupDoctorStageResult",
    "SetupDoctorWorkflow",
]

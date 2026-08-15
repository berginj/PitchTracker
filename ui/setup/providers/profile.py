"""Quality report assembly and rig profile persistence for setup workflow."""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from contracts.quality import QUALITY_DEGRADED

if TYPE_CHECKING:
    from ui.setup.providers.context import LiveSetupContext


def build_quality_report_for_context(ctx: "LiveSetupContext"):
    """Assemble a quality report from current setup evidence."""
    from calib.stereo_setup.quality_report import build_quality_report
    from ui.setup.persist_profile_view import build_stereo_profile_from_report

    stereo = build_stereo_profile_from_report(Path("calibration"))
    if stereo is None:
        from ui.setup.quality_report_view import load_calibration_quality_report
        return load_calibration_quality_report(Path("calibration"))
    focus_locks = []
    exposure_locks = []
    if ctx.last_focus is not None:
        focus_locks = [ctx.last_focus.focus_left, ctx.last_focus.focus_right]
        exposure_locks = [ctx.last_focus.exposure_left, ctx.last_focus.exposure_right]
    report = build_quality_report(
        rms_reprojection_px=stereo.rms_reprojection_px,
        epipolar_error_px=(ctx.last_rectification.epipolar_error_after_px if ctx.last_rectification else stereo.epipolar_error_px),
        baseline_in=stereo.baseline_in,
        sync=ctx.last_sync,
        overlap=ctx.last_overlap,
        rectification=ctx.last_rectification,
        focus_locks=focus_locks,
        exposure_locks=exposure_locks,
        require_steps=True,
    )
    if ctx.last_qualification is not None:
        assessment = ctx.last_qualification.assessment
    else:
        assessment = None
    if assessment is not None and (
        assessment.status == QUALITY_DEGRADED or not assessment.permits_measurement
    ):
        from contracts.setup import QUALITY_GRADE_FAIL
        qualification_label = "degraded" if assessment.status == QUALITY_DEGRADED else "failed"
        reasons = ", ".join(assessment.reason_codes) or assessment.status
        report = replace(
            report,
            grade=QUALITY_GRADE_FAIL,
            passed=False,
            warnings=[
                *report.warnings,
                f"Capture qualification {qualification_label}: {reasons}",
            ],
        )
    return report


def persist_profile_for_context(ctx: "LiveSetupContext", stereo_profile) -> str:
    """Persist a validated rig profile and activate it."""
    from app.services.rig_profile import RigProfileService
    from app.services.rig_profile_models import PASS, WARN, RigProfile
    from app.services.setup_snapshot import assemble_setup_snapshot
    from configs.settings import load_config
    from ui.setup.field_alignment_view import load_or_estimate_field_alignment

    from ui.setup.providers.context import _new_profile_id, _setup_payload

    field_alignment = load_or_estimate_field_alignment(Path("calibration"))
    if not field_alignment.passed or field_alignment.transform is None:
        raise RuntimeError(field_alignment.recommendation)
    report = ctx.quality_report()
    if not report.passed:
        raise RuntimeError("Live setup checks have not all passed; profile was not activated.")
    config = load_config(ctx.config_path)
    authoritative_wb = config.camera.wb
    authoritative_wb_source = "configured" if authoritative_wb is not None else "not_applicable"
    resolved_wb_by_camera: dict[str, float] = {}
    if config.camera.color_mode and authoritative_wb is None:
        for side in ("left", "right"):
            controls = ctx.last_controls.get(side, {})
            value = controls.get("resolved_wb")
            source = controls.get("wb_source")
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                numeric_value = 0.0
            if (
                not controls.get("readback_verified")
                or source != "auto_sampled_then_locked"
                or not math.isfinite(numeric_value)
                or numeric_value <= 0
            ):
                raise RuntimeError(
                    f"{side.capitalize()} camera did not provide a verified auto-sampled white balance."
                )
            resolved_wb_by_camera[side] = numeric_value
        left_wb = resolved_wb_by_camera["left"]
        right_wb = resolved_wb_by_camera["right"]
        if abs(left_wb - right_wb) / max(abs(left_wb), 1.0) > 0.1:
            raise RuntimeError(
                "Camera white-balance samples differ by more than 10%; set and verify an explicit shared value."
            )
        authoritative_wb = int(round(left_wb))
        authoritative_wb_source = "auto_sampled_then_locked"
    if ctx.last_rectification is not None:
        stereo_profile = replace(
            stereo_profile,
            epipolar_error_px=float(ctx.last_rectification.epipolar_error_after_px),
        )
    left_id, right_id = ctx.assigned_ids()
    selection = {camera.hardware_id: camera for camera in ctx.selection().cameras}
    missing_ids = [camera_id for camera_id in (left_id, right_id) if camera_id not in selection]
    if missing_ids:
        raise RuntimeError("Assigned camera is no longer connected: " + ", ".join(missing_ids))
    profile_id = _new_profile_id()
    service = RigProfileService(base_dir=ctx.rig_profile_dir, config_path=ctx.config_path)
    profile_dir = service.profile_dir(profile_id)
    profile_dir.mkdir(parents=True, exist_ok=True)
    calibration_source = Path("calibration") / stereo_profile.calibration_file
    if not calibration_source.exists():
        raise RuntimeError(f"Calibration artifact missing: {calibration_source}")
    shutil.copy2(calibration_source, profile_dir / "stereo_calibration.npz")
    roi_source = next((path for path in (Path("rois/shared_rois.json"), Path("configs/roi.json")) if path.exists()), None)
    if roi_source is None:
        raise RuntimeError("ROI artifact missing; configure lane and plate ROIs before persistence.")
    shutil.copy2(roi_source, profile_dir / "roi.json")
    profile = RigProfile.from_config(
        profile_id,
        config,
        backend="uvc",
        left_serial=left_id,
        right_serial=right_id,
        quality_metrics={
            **report.to_payload(),
            "capture_qualification": None
            if ctx.last_qualification is None
            else {
                **ctx.last_qualification.__dict__,
                "assessment": ctx.last_qualification.assessment.to_payload(),
            },
        },
        diagnostics={"setup_source": "canonical_live_wizard"},
    )
    profile = replace(
        profile,
        stereo_profile=stereo_profile,
        field_transform={
            **field_alignment.transform.to_payload(),
            "fixture_source_sha256": field_alignment.fixture_source_sha256,
            "fixture_point_count": field_alignment.fixture_point_count,
        },
        hardware_fingerprint={
            "backend": "uvc",
            "left_serial": left_id,
            "right_serial": right_id,
            "left_friendly_name": selection[left_id].friendly_name,
            "right_friendly_name": selection[right_id].friendly_name,
        },
        camera_mode={
            **profile.camera_mode,
            **ctx.last_modes.get("left", {}),
        },
        approved_modes=[
            {
                **profile.camera_mode,
                **ctx.last_modes.get("left", {}),
            }
        ],
        control_settings={
            **profile.control_settings,
            "wb": authoritative_wb,
            "wb_source": authoritative_wb_source,
            "resolved_wb_by_camera": resolved_wb_by_camera,
            "readback": dict(ctx.last_controls),
        },
        runtime_validation_status=(
            WARN
            if ctx.last_qualification is not None
            and ctx.last_qualification.assessment.status == QUALITY_DEGRADED
            else PASS
        ),
        error_budget={
            "budget_id": "field-pilot-v1",
            "version": "1",
            "limits": {
                "pair_skew_p95_ms": {"warn": 0.5, "reject": 1.0, "units": "ms"},
                "recording_drop_rate": {"warn": 0.01, "reject": 0.05, "units": "ratio"},
                "analysis_drop_rate": {"warn": 0.0, "reject": 0.01, "units": "ratio"},
                "tracklet_start_rate": {"warn": 0.5, "reject": 0.8, "units": "ratio"},
                "pair_skew_rejection_rate": {"warn": 0.01, "reject": 0.05, "units": "ratio"},
                "association_rejection_rate": {"warn": 0.2, "reject": 0.5, "units": "ratio"},
            },
        },
    )
    setup_snapshot = assemble_setup_snapshot(
        profile=profile,
        config=config,
        config_path=ctx.config_path,
        cameras=selection.values(),
        capture_qualification=ctx.last_qualification,
        capture_diagnostics={
            **ctx.last_capture_diagnostics,
            "modes": dict(ctx.last_modes),
            "sync": _setup_payload(ctx.last_sync),
            "focus": _setup_payload(ctx.last_focus),
            "overlap": _setup_payload(ctx.last_overlap),
            "rectification": _setup_payload(ctx.last_rectification),
        },
        calibration_path=profile_dir / "stereo_calibration.npz",
        roi_path=profile_dir / "roi.json",
        capability_observations=ctx.last_capability_observations,
    )
    profile = replace(
        profile,
        setup_snapshot=setup_snapshot.to_payload(),
        diagnostics={
            **profile.diagnostics,
            "setup_snapshot_fingerprint": setup_snapshot.fingerprint_sha256,
            "setup_snapshot_configuration_evidence_complete": (
                setup_snapshot.assessment.configuration_evidence_complete
            ),
            "setup_snapshot_blockers": list(setup_snapshot.assessment.blockers),
        },
    )
    saved = service.save(profile, activate=True)
    return saved.profile_id

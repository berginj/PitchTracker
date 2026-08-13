"""Service lifecycle startup helpers for the pipeline orchestrator.

Encapsulates rig profile loading, validation, and service creation/update
logic that runs during ``start_capture``. Extracted from PipelineOrchestrator
to keep that file under 500 lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.events.event_bus import EventBus
from app.services.analysis import AnalysisServiceImpl
from app.services.capture import CaptureServiceImpl
from app.services.detection import DetectionServiceImpl
from app.services.orchestrator.roi_config import apply_runtime_rois
from app.services.recording import RecordingServiceImpl
from app.services.rig_profile import CRITICAL, RigProfile, RigProfileService
from calib.calibration_report import build_calibration_report
from configs.settings import AppConfig
from log_config.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RigStartupResult:
    """Result of rig profile loading and validation."""

    profile: RigProfile
    config: AppConfig
    calibration_path: Optional[Path]
    roi_path: Optional[Path]
    calibration_report: Optional[dict]


def load_and_validate_rig(
    rig_service: RigProfileService,
    config: AppConfig,
    backend: str,
    left_serial: str,
    right_serial: str,
) -> RigStartupResult:
    """Load, validate, and apply the rig profile to config.

    Raises:
        RuntimeError: If rig profile validation is CRITICAL.
    """
    profile = rig_service.load_active_or_legacy(
        config, backend=backend,
        left_serial=left_serial, right_serial=right_serial,
    )
    validation = rig_service.validate_for_runtime(
        profile, config=config, backend=backend,
        left_serial=left_serial, right_serial=right_serial,
    )
    if validation.state == CRITICAL:
        logger.error(
            "Rig profile runtime validation is CRITICAL: %s",
            validation.issues,
        )
        raise RuntimeError(
            "Rig profile runtime validation is CRITICAL: "
            + "; ".join(validation.issues or ["unknown validation failure"])
        )
    elif validation.warnings:
        logger.warning(
            "Rig profile runtime validation warnings: %s",
            validation.warnings,
        )

    applied_config = rig_service.apply_profile_to_config(
        config, profile,
        preserve_camera_mode=profile.profile_id == "legacy",
    )
    calibration_path = rig_service.calibration_path(profile)
    roi_path = rig_service.roi_path(profile)
    config_file = rig_service.config_path
    calibration_report = build_calibration_report(
        calibration_path, config_file,
    )

    return RigStartupResult(
        profile=profile,
        config=applied_config,
        calibration_path=calibration_path,
        roi_path=roi_path,
        calibration_report=calibration_report,
    )


def ensure_services(
    event_bus: EventBus,
    config: AppConfig,
    backend: str,
    rig_result: RigStartupResult,
    left_serial: str,
    right_serial: str,
    capture: Optional[CaptureServiceImpl],
    detection: Optional[DetectionServiceImpl],
    recording: Optional[RecordingServiceImpl],
    analysis: Optional[AnalysisServiceImpl],
    record_dir: Optional[Path],
    manual_speed_mph: Optional[float],
) -> tuple:
    """Create or update services. Returns (capture, detection, recording, analysis)."""
    if capture is None:
        capture = CaptureServiceImpl(event_bus, backend=backend)

    if detection is None:
        detection = DetectionServiceImpl(event_bus, config)
    else:
        detection.update_config(config)
    detection.set_runtime_calibration_path(rig_result.calibration_path)
    apply_runtime_rois(detection, rig_result.roi_path, left_serial, right_serial)

    if recording is None:
        recording = RecordingServiceImpl(event_bus)
        if record_dir is not None:
            recording.set_record_directory(record_dir)
        recording.set_manual_speed_mph(manual_speed_mph)
    recording.set_calibration_context(
        rig_result.profile.profile_id if rig_result.profile else None,
        rig_result.calibration_report,
    )

    if analysis is None:
        analysis = AnalysisServiceImpl(event_bus, config)
        analysis.set_manual_speed_mph(manual_speed_mph)
    else:
        analysis.update_config(config)
        analysis.set_manual_speed_mph(manual_speed_mph)

    return capture, detection, recording, analysis

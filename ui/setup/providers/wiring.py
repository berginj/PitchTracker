"""Wizard step wiring for the canonical stereo setup workflow."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Optional

from capture.device_discovery import list_uvc_devices
from contracts.setup_capture import SetupCapturePurpose, SetupCaptureRequest
from ui.setup.paired_preview_view import PairedPreviewSnapshot

from ui.setup.providers.context import LiveSetupContext
from ui.setup.providers.discovery import DeviceLister

if TYPE_CHECKING:
    from app.services.capture.setup_capture import SupervisedSetupCaptureService
    from ui.setup.providers.support import CameraCatalog
    from ui.setup.state_machine import SetupStep
    from ui.setup.steps.base_step import BaseStep

PreviewProvider = Callable[[], PairedPreviewSnapshot]


def build_live_stereo_step_widgets(
    *,
    catalog: Optional["CameraCatalog"] = None,
    list_devices: DeviceLister = list_uvc_devices,
    preview_provider: Optional[PreviewProvider] = None,
    setup_capture_service: Optional["SupervisedSetupCaptureService"] = None,
    setup_capture_backend: str = "uvc",
) -> "Dict[SetupStep, BaseStep]":
    """Build the canonical registry with a shared live hardware context.

    Step 1 uses live UVC discovery. Subsequent capture-quality steps reuse the
    assignments through :class:`LiveSetupContext`; ``preview_provider`` may be
    supplied for deterministic tests.

    Args:
        catalog: Optional camera-catalog service for recognition / carry-over.
        list_devices: Device lister for step-1 discovery (injectable for tests).
        preview_provider: Optional callable yielding a paired-preview snapshot
            from live cameras. ``None`` leaves the step's empty default.

    Returns:
        A mapping with an entry for every canonical :class:`SetupStep`.
    """
    from ui.setup.stereo_steps import build_stereo_step_widgets
    from ui.setup.state_machine import SetupStep
    from ui.setup.steps import CameraSelectStep, PairedPreviewStep
    from ui.setup.steps import FocusLockStep, OverlapStep, PersistProfileStep, QualityReportStep, RectifyStep, SyncCheckStep
    from ui.setup.persist_profile_view import build_stereo_profile_from_report
    from app.services.capture.setup_capture import SupervisedSetupCaptureService
    from ui.setup.setup_capture_controller import SetupCaptureOperation

    widgets = build_stereo_step_widgets()
    context = LiveSetupContext(
        catalog=catalog,
        list_devices=list_devices,
        setup_capture_backend=setup_capture_backend,
    )
    capture_service = setup_capture_service or SupervisedSetupCaptureService()

    def _operation(purpose: SetupCapturePurpose) -> SetupCaptureOperation:
        def _request() -> SetupCaptureRequest:
            return context.build_capture_request(purpose)

        return SetupCaptureOperation(
            capture_service,
            _request,
            context.apply_capture_result,
        )

    widgets[SetupStep.SELECT_CAMERAS] = CameraSelectStep(
        snapshot_provider=context.selection,
        assignment_callback=context.assign if catalog is not None else None,
    )
    widgets[SetupStep.PAIRED_PREVIEW] = PairedPreviewStep(
        snapshot_provider=preview_provider or context.preview,
        operation=None if preview_provider is not None else _operation(SetupCapturePurpose.PREVIEW),
    )
    widgets[SetupStep.SYNC_CHECK] = SyncCheckStep(
        result_provider=context.sync,
        operation=_operation(SetupCapturePurpose.SYNC),
    )
    widgets[SetupStep.FOCUS_EXPOSURE_LOCK] = FocusLockStep(
        snapshot_provider=context.focus,
        operation=_operation(SetupCapturePurpose.FOCUS),
    )
    widgets[SetupStep.OVERLAP_VALIDATION] = OverlapStep(
        result_provider=context.overlap,
        operation=_operation(SetupCapturePurpose.OVERLAP),
    )
    widgets[SetupStep.COARSE_RECTIFY] = RectifyStep(
        result_provider=context.rectify,
        operation=_operation(SetupCapturePurpose.RECTIFY),
    )
    widgets[SetupStep.PERSIST_PROFILE] = PersistProfileStep(
        profile_provider=lambda: build_stereo_profile_from_report(Path("calibration")),
        persist_callback=context.persist_profile,
    )
    widgets[SetupStep.QUALITY_REPORT] = QualityReportStep(report_provider=context.quality_report)
    for widget in widgets.values():
        setattr(widget, "_live_setup_context", context)
    return widgets

"""Registry wiring the canonical 9-step stereo spec to wizard widgets.

:data:`~ui.setup.state_machine.DEFAULT_SETUP_SPEC` defines the canonical stereo
setup flow (the architecture-note target). This module maps each
:class:`~ui.setup.state_machine.SetupStep` to the widget that drives it so the
genuine stereo wizard can run on the tested
:class:`~ui.setup.state_machine.SetupStateMachine` engine.

The four foundation gate steps (sync check, focus/exposure lock, overlap, coarse
rectification) and the final quality report are real, synthetic-testable
widgets. The remaining four steps (camera selection, paired preview, ChArUco
fine-tuning, profile persistence) are hardware/integration-bound and are
represented by an honest :class:`PlaceholderStep` until their widgets land, so
the flow is navigable end-to-end without pretending those steps are done.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6 import QtCore, QtWidgets

from ui.setup.state_machine import DEFAULT_SETUP_SPEC, SetupStep
from ui.setup.steps import (
    BaseStep,
    FocusLockStep,
    OverlapStep,
    QualityReportStep,
    RectifyStep,
    SyncCheckStep,
)
from ui.themes import apply_standard_layout, build_notice, style_status_label

# Titles come from the canonical spec so the registry never drifts from it.
_SPEC_TITLES = {spec.step: spec.title for spec in DEFAULT_SETUP_SPEC}

# Steps that do not yet have a genuine widget (hardware/integration-bound).
_PLACEHOLDER_NOTES = {
    SetupStep.SELECT_CAMERAS: "Camera discovery and stable left/right assignment is handled by the live "
    "camera workflow; a dedicated stereo selection widget is coming.",
    SetupStep.PAIRED_PREVIEW: "Live paired left/right preview requires connected cameras and is provided "
    "by the capture workflow; a dedicated preview widget is coming.",
    SetupStep.CHARUCO_FINE_TUNE: "Optional ChArUco fine-tuning refines intrinsics after coarse rectification; "
    "this step can be skipped to finish with the targetless calibration.",
    SetupStep.PERSIST_PROFILE: "Calibration profile persistence is handled by the export/profile workflow; "
    "a dedicated persist widget is coming.",
}


class PlaceholderStep(BaseStep):
    """Informational stand-in for a stereo step whose widget is not built yet."""

    def __init__(self, title: str, note: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._title = title
        self._note = note
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        headline = QtWidgets.QLabel(self._title)
        headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_status_label(headline, "info", self._title)
        layout.addWidget(headline)

        notice, _ = build_notice(self._note, tone="info")
        layout.addWidget(notice)

        layout.addStretch()
        self.setLayout(layout)

    def get_title(self) -> str:
        return self._title

    def get_description(self) -> str:
        return self._note

    def validate(self) -> tuple[bool, str]:
        # Informational stand-in: never blocks navigation.
        return True, ""


def build_stereo_step_widgets() -> Dict[SetupStep, BaseStep]:
    """Build one widget per canonical :class:`SetupStep`.

    Returns:
        A mapping with an entry for every step in :data:`DEFAULT_SETUP_SPEC`.
        Built gate steps use their genuine widgets; the remaining steps use an
        honest :class:`PlaceholderStep`.
    """
    widgets: Dict[SetupStep, BaseStep] = {
        SetupStep.SYNC_CHECK: SyncCheckStep(),
        SetupStep.FOCUS_EXPOSURE_LOCK: FocusLockStep(),
        SetupStep.OVERLAP_VALIDATION: OverlapStep(),
        SetupStep.COARSE_RECTIFY: RectifyStep(),
        SetupStep.QUALITY_REPORT: QualityReportStep(),
    }
    for step, note in _PLACEHOLDER_NOTES.items():
        widgets[step] = PlaceholderStep(_SPEC_TITLES[step], note)
    return widgets


__all__ = ["PlaceholderStep", "build_stereo_step_widgets"]

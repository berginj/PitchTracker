"""Registry wiring the canonical evidence-gated stereo spec to wizard widgets.

:data:`~ui.setup.state_machine.DEFAULT_SETUP_SPEC` defines the canonical stereo
setup flow (the architecture-note target). This module maps each
:class:`~ui.setup.state_machine.SetupStep` to the widget that drives it so the
genuine stereo wizard can run on the tested
:class:`~ui.setup.state_machine.SetupStateMachine` engine.

All canonical steps are real, synthetic-testable widgets driven by
injectable providers: camera selection, paired preview, sync check,
focus/exposure lock, overlap, coarse rectification, optional ChArUco
fine-tuning, field alignment, profile persistence, and the final quality report. The flow is
navigable end-to-end on the tested state machine without hardware.

:class:`PlaceholderStep` is retained as an honest stand-in for any future step
that has no genuine widget yet; it is currently unused by the registry.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6 import QtCore, QtWidgets

from ui.setup.state_machine import DEFAULT_SETUP_SPEC, SetupStep
from ui.setup.steps import (
    BaseStep,
    CameraSelectStep,
    CharucoFinetuneStep,
    FocusLockStep,
    FieldAlignmentStep,
    OverlapStep,
    PairedPreviewStep,
    PersistProfileStep,
    QualityReportStep,
    RectifyStep,
    SyncCheckStep,
)
from ui.themes import apply_standard_layout, build_notice, style_status_label

# Titles come from the canonical spec so the registry never drifts from it.
_SPEC_TITLES = {spec.step: spec.title for spec in DEFAULT_SETUP_SPEC}

# Steps that do not yet have a genuine widget. Empty: all are built.
_PLACEHOLDER_NOTES: Dict[SetupStep, str] = {}


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
        Every step uses its genuine, provider-driven widget.
    """
    widgets: Dict[SetupStep, BaseStep] = {
        SetupStep.SELECT_CAMERAS: CameraSelectStep(),
        SetupStep.PAIRED_PREVIEW: PairedPreviewStep(),
        SetupStep.SYNC_CHECK: SyncCheckStep(),
        SetupStep.FOCUS_EXPOSURE_LOCK: FocusLockStep(),
        SetupStep.OVERLAP_VALIDATION: OverlapStep(),
        SetupStep.COARSE_RECTIFY: RectifyStep(),
        SetupStep.CHARUCO_FINE_TUNE: CharucoFinetuneStep(),
        SetupStep.FIELD_ALIGNMENT: FieldAlignmentStep(),
        SetupStep.PERSIST_PROFILE: PersistProfileStep(),
        SetupStep.QUALITY_REPORT: QualityReportStep(),
    }
    for step, note in _PLACEHOLDER_NOTES.items():
        widgets[step] = PlaceholderStep(_SPEC_TITLES[step], note)
    return widgets


__all__ = ["PlaceholderStep", "build_stereo_step_widgets"]

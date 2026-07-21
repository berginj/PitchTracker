"""Qt-free step specification for the live setup wizard.

The legacy :class:`~ui.setup.setup_window.SetupWindow` drove navigation with a
hand-rolled ``_current_step_index`` plus ``isinstance`` handoffs. This module
lets the window run on the tested :class:`~ui.setup.state_machine.SetupStateMachine`
engine instead, by describing the six live wizard widgets as an ordered,
prerequisite-gated spec.

Keeping this separate from the window (no PySide6 import) means the wizard's
control flow -- ordering, optional/skippable steps, prerequisite gating -- is
unit-testable with synthetic inputs, exactly like the canonical evidence-gated stereo
spec in :mod:`ui.setup.state_machine`.

The canonical stereo rebuild target remains ``DEFAULT_SETUP_SPEC`` (the 10-step
flow). This spec mirrors the widgets that exist today; new stereo steps migrate
onto the same engine widget-by-widget.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Tuple

from ui.setup.state_machine import StepSpec


class WizardStep(Enum):
    """The six live setup-wizard steps, in presentation order."""

    CAMERAS = "cameras"
    CALIBRATION = "calibration"
    ROI = "roi"
    DETECTOR = "detector"
    VALIDATION = "validation"
    EXPORT = "export"
    QUALITY_REPORT = "quality_report"


# Presentation order and human-readable titles for the step indicator.
WIZARD_STEP_ORDER: Tuple[WizardStep, ...] = (
    WizardStep.CAMERAS,
    WizardStep.CALIBRATION,
    WizardStep.ROI,
    WizardStep.DETECTOR,
    WizardStep.VALIDATION,
    WizardStep.EXPORT,
    WizardStep.QUALITY_REPORT,
)

WIZARD_STEP_TITLES = {
    WizardStep.CAMERAS: "1. Cameras",
    WizardStep.CALIBRATION: "2. Calibration",
    WizardStep.ROI: "3. ROI",
    WizardStep.DETECTOR: "4. Detector",
    WizardStep.VALIDATION: "5. Validate",
    WizardStep.EXPORT: "6. Export",
    WizardStep.QUALITY_REPORT: "7. Quality",
}


def build_wizard_spec(optional: Iterable[WizardStep] = ()) -> Tuple[StepSpec, ...]:
    """Build a linear, prerequisite-gated spec for the live wizard.

    Each step depends on the most recent *required* step before it, so an
    optional step is a non-blocking side step: skipping it never prevents the
    operator from finishing the wizard (matching the canonical stereo spec,
    where ChArUco fine-tuning is optional and nothing downstream depends on it).

    Args:
        optional: Steps that may be skipped without completing them.

    Returns:
        Ordered tuple of :class:`StepSpec`, one per :data:`WIZARD_STEP_ORDER`.
    """
    optional_set = set(optional)
    specs: list[StepSpec] = []
    last_required: WizardStep | None = None
    for step in WIZARD_STEP_ORDER:
        prereqs: Tuple[WizardStep, ...] = (last_required,) if last_required is not None else ()
        is_optional = step in optional_set
        specs.append(
            StepSpec(
                step=step,
                title=WIZARD_STEP_TITLES[step],
                optional=is_optional,
                prerequisites=prereqs,
            )
        )
        if not is_optional:
            last_required = step
    return tuple(specs)


__all__ = [
    "WizardStep",
    "WIZARD_STEP_ORDER",
    "WIZARD_STEP_TITLES",
    "build_wizard_spec",
]

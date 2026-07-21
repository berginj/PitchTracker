"""Integration smoke test: genuine stereo widgets on the canonical machine.

Proves all nine rebuilt step widgets (camera select, paired preview, sync,
focus/exposure, overlap, coarse rectification, ChArUco fine-tune, persist
profile, quality report) drive the tested :class:`SetupStateMachine` over the
canonical 9-step :data:`DEFAULT_SETUP_SPEC`, including skipping the optional
ChArUco fine-tune step and still finishing.
"""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from ui.setup.state_machine import (  # noqa: E402
    DEFAULT_SETUP_SPEC,
    SetupStateMachine,
    SetupStep,
)
from ui.setup.stereo_steps import PlaceholderStep, build_stereo_step_widgets  # noqa: E402
from ui.setup.steps import (  # noqa: E402
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


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


def test_registry_covers_every_canonical_step(qapp):
    widgets = build_stereo_step_widgets()
    assert set(widgets) == {spec.step for spec in DEFAULT_SETUP_SPEC}


def test_genuine_gate_steps_use_real_widgets(qapp):
    widgets = build_stereo_step_widgets()
    assert isinstance(widgets[SetupStep.SELECT_CAMERAS], CameraSelectStep)
    assert isinstance(widgets[SetupStep.PAIRED_PREVIEW], PairedPreviewStep)
    assert isinstance(widgets[SetupStep.SYNC_CHECK], SyncCheckStep)
    assert isinstance(widgets[SetupStep.FOCUS_EXPOSURE_LOCK], FocusLockStep)
    assert isinstance(widgets[SetupStep.OVERLAP_VALIDATION], OverlapStep)
    assert isinstance(widgets[SetupStep.COARSE_RECTIFY], RectifyStep)
    assert isinstance(widgets[SetupStep.CHARUCO_FINE_TUNE], CharucoFinetuneStep)
    assert isinstance(widgets[SetupStep.FIELD_ALIGNMENT], FieldAlignmentStep)
    assert isinstance(widgets[SetupStep.PERSIST_PROFILE], PersistProfileStep)
    assert isinstance(widgets[SetupStep.QUALITY_REPORT], QualityReportStep)
    # Every canonical step now has a genuine widget; none are placeholders.
    assert not any(isinstance(w, PlaceholderStep) for w in widgets.values())


def test_every_widget_renders_on_enter(qapp):
    widgets = build_stereo_step_widgets()
    for step, widget in widgets.items():
        widget.on_enter()
        ok, message = widget.validate()
        assert isinstance(ok, bool)
        assert isinstance(message, str)


def test_machine_drives_full_stereo_flow_skipping_optional(qapp):
    widgets = build_stereo_step_widgets()
    machine = SetupStateMachine(DEFAULT_SETUP_SPEC)
    assert machine.current == SetupStep.SELECT_CAMERAS

    while True:
        step = machine.current
        widgets[step].on_enter()
        if step == SetupStep.CHARUCO_FINE_TUNE and machine.can_skip():
            machine.skip()
            continue
        machine.mark_complete(step, True)
        if machine.can_advance():
            machine.advance()
        else:
            break

    assert machine.current == SetupStep.QUALITY_REPORT
    assert machine.can_finish()

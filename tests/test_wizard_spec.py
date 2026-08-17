"""Tests for the live wizard step spec (ui.setup.wizard_spec)."""

from __future__ import annotations

from ui.setup.state_machine import SetupStateMachine
from ui.setup.wizard_spec import (
    WIZARD_STEP_ORDER,
    WizardStep,
    build_wizard_spec,
)


def test_spec_covers_all_steps_in_order():
    spec = build_wizard_spec()
    assert tuple(s.step for s in spec) == WIZARD_STEP_ORDER
    assert all(s.title for s in spec)


def test_required_chain_links_each_step_to_predecessor():
    spec = build_wizard_spec()
    # First step has no prerequisites; every later step depends on the prior one.
    assert spec[0].prerequisites == ()
    for prev, cur in zip(spec, spec[1:]):
        assert cur.prerequisites == (prev.step,)


def test_optional_step_is_non_blocking():
    # Make the detector step optional; the step after it should depend on the
    # last *required* step (ROI), not the optional detector.
    spec = build_wizard_spec(optional=(WizardStep.DETECTOR,))
    by_step = {s.step: s for s in spec}
    assert by_step[WizardStep.DETECTOR].optional is True
    assert by_step[WizardStep.DETECTOR].prerequisites == (WizardStep.ROI,)
    assert by_step[WizardStep.VALIDATION].prerequisites == (WizardStep.ROI,)


def test_machine_drives_full_required_traversal():
    machine = SetupStateMachine(build_wizard_spec())
    assert machine.current.value == WizardStep.CAMERAS.value
    assert not machine.can_finish()

    for step in WIZARD_STEP_ORDER:
        machine.mark_complete(step, True)
        if machine.can_advance():
            machine.advance()

    assert machine.current.value == WizardStep.QUALITY_REPORT.value
    assert machine.can_finish()


def test_machine_blocks_advance_until_step_complete():
    machine = SetupStateMachine(build_wizard_spec())
    # Cannot advance from CAMERAS until it is marked complete.
    assert not machine.can_advance()
    machine.mark_complete(WizardStep.CAMERAS, True)
    assert machine.can_advance()


def test_optional_step_can_be_skipped_and_still_finish():
    machine = SetupStateMachine(build_wizard_spec(optional=(WizardStep.DETECTOR,)))
    # Complete up to ROI, then skip the optional detector step.
    for step in (WizardStep.CAMERAS, WizardStep.CALIBRATION, WizardStep.ROI):
        machine.mark_complete(step, True)
        machine.advance()
    assert machine.current.value == WizardStep.DETECTOR.value
    assert machine.can_skip()
    machine.skip()
    assert machine.current.value == WizardStep.VALIDATION.value

    machine.mark_complete(WizardStep.VALIDATION, True)
    machine.advance()
    machine.mark_complete(WizardStep.EXPORT, True)
    machine.advance()
    machine.mark_complete(WizardStep.QUALITY_REPORT, True)
    assert machine.can_finish()

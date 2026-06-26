"""Unit tests for the Qt-free setup state machine (ui.setup.state_machine)."""

from __future__ import annotations

import pytest

from ui.setup.state_machine import (
    DEFAULT_SETUP_SPEC,
    SetupStateMachine,
    SetupStep,
    SetupTransitionError,
    StepSpec,
)


def _complete_through(machine: SetupStateMachine, *steps: SetupStep) -> None:
    for step in steps:
        machine.mark_complete(step)


def test_default_spec_starts_at_first_step():
    machine = SetupStateMachine()
    assert machine.current == SetupStep.SELECT_CAMERAS
    assert machine.current_index == 0
    assert len(machine.steps) == len(DEFAULT_SETUP_SPEC)


def test_cannot_advance_until_current_complete():
    machine = SetupStateMachine()
    assert machine.can_advance() is False
    with pytest.raises(SetupTransitionError):
        machine.advance()


def test_advance_after_completion():
    machine = SetupStateMachine()
    machine.mark_complete(SetupStep.SELECT_CAMERAS)
    assert machine.can_advance() is True
    assert machine.advance() == SetupStep.PAIRED_PREVIEW


def test_prerequisites_gate_entry():
    machine = SetupStateMachine()
    # Overlap validation requires focus/exposure lock which requires preview.
    assert machine.can_enter(SetupStep.OVERLAP_VALIDATION) is False
    _complete_through(
        machine,
        SetupStep.SELECT_CAMERAS,
        SetupStep.PAIRED_PREVIEW,
        SetupStep.FOCUS_EXPOSURE_LOCK,
    )
    assert machine.can_enter(SetupStep.OVERLAP_VALIDATION) is True


def test_go_to_respects_prerequisites():
    machine = SetupStateMachine()
    with pytest.raises(SetupTransitionError):
        machine.go_to(SetupStep.COARSE_RECTIFY)
    _complete_through(
        machine,
        SetupStep.SELECT_CAMERAS,
        SetupStep.PAIRED_PREVIEW,
        SetupStep.FOCUS_EXPOSURE_LOCK,
        SetupStep.OVERLAP_VALIDATION,
    )
    assert machine.go_to(SetupStep.COARSE_RECTIFY) == SetupStep.COARSE_RECTIFY


def test_optional_step_can_be_skipped():
    machine = SetupStateMachine()
    _complete_through(
        machine,
        SetupStep.SELECT_CAMERAS,
        SetupStep.PAIRED_PREVIEW,
        SetupStep.FOCUS_EXPOSURE_LOCK,
        SetupStep.OVERLAP_VALIDATION,
        SetupStep.COARSE_RECTIFY,
    )
    machine.go_to(SetupStep.CHARUCO_FINE_TUNE)
    assert machine.is_optional(SetupStep.CHARUCO_FINE_TUNE) is True
    assert machine.can_skip() is True
    assert machine.skip() == SetupStep.PERSIST_PROFILE
    # ChArUco was skipped, not completed.
    assert machine.is_complete(SetupStep.CHARUCO_FINE_TUNE) is False


def test_required_step_cannot_be_skipped():
    machine = SetupStateMachine()
    machine.mark_complete(SetupStep.SELECT_CAMERAS)
    machine.advance()  # at PAIRED_PREVIEW (required)
    assert machine.can_skip() is False
    with pytest.raises(SetupTransitionError):
        machine.skip()


def test_can_finish_only_when_required_steps_complete():
    machine = SetupStateMachine()
    required = [s.step for s in DEFAULT_SETUP_SPEC if not s.optional]
    for step in required[:-1]:
        machine.mark_complete(step)
    assert machine.can_finish() is False
    assert SetupStep.QUALITY_REPORT in machine.missing_required()
    machine.mark_complete(required[-1])
    assert machine.can_finish() is True
    # Optional ChArUco never completed, yet finishing is allowed.
    assert machine.is_complete(SetupStep.CHARUCO_FINE_TUNE) is False


def test_cannot_reach_finish_with_required_step_skipped():
    """Skipping is only legal for optional steps, so a required step can never
    be bypassed to reach a finishable state."""
    machine = SetupStateMachine()
    # Complete everything except OVERLAP_VALIDATION (required) via direct marks.
    for step in machine.steps:
        if step is not SetupStep.OVERLAP_VALIDATION:
            machine.mark_complete(step)
    # PERSIST/QUALITY depend transitively on COARSE_RECTIFY which depends on
    # OVERLAP_VALIDATION, so marking them complete while overlap is missing is
    # invalidated by the dependency cascade -> still not finishable.
    assert machine.can_finish() is False
    assert SetupStep.OVERLAP_VALIDATION in machine.missing_required()


def test_marking_incomplete_cascades_to_dependents():
    machine = SetupStateMachine()
    for step in machine.steps:
        machine.mark_complete(step)
    assert machine.can_finish() is True
    # Invalidate an early step; everything downstream must drop.
    machine.mark_complete(SetupStep.PAIRED_PREVIEW, complete=False)
    assert machine.is_complete(SetupStep.PAIRED_PREVIEW) is False
    assert machine.is_complete(SetupStep.SYNC_CHECK) is False
    assert machine.is_complete(SetupStep.COARSE_RECTIFY) is False
    assert machine.is_complete(SetupStep.QUALITY_REPORT) is False
    # The independent first step is unaffected.
    assert machine.is_complete(SetupStep.SELECT_CAMERAS) is True


def test_back_and_bounds():
    machine = SetupStateMachine()
    assert machine.can_go_back() is False
    with pytest.raises(SetupTransitionError):
        machine.go_back()
    machine.mark_complete(SetupStep.SELECT_CAMERAS)
    machine.advance()
    assert machine.can_go_back() is True
    assert machine.go_back() == SetupStep.SELECT_CAMERAS


def test_progress_counts_required_only():
    machine = SetupStateMachine()
    done, total = machine.progress()
    assert done == 0
    assert total == sum(1 for s in DEFAULT_SETUP_SPEC if not s.optional)
    machine.mark_complete(SetupStep.SELECT_CAMERAS)
    done, _ = machine.progress()
    assert done == 1


def test_reset_clears_state():
    machine = SetupStateMachine()
    machine.mark_complete(SetupStep.SELECT_CAMERAS)
    machine.advance()
    machine.reset()
    assert machine.current == SetupStep.SELECT_CAMERAS
    assert machine.is_complete(SetupStep.SELECT_CAMERAS) is False


def test_rejects_duplicate_steps():
    spec = (
        StepSpec(SetupStep.SELECT_CAMERAS, "A"),
        StepSpec(SetupStep.SELECT_CAMERAS, "B"),
    )
    with pytest.raises(ValueError):
        SetupStateMachine(specs=spec)


def test_rejects_unknown_prerequisite():
    spec = (StepSpec(SetupStep.PAIRED_PREVIEW, "P", prerequisites=(SetupStep.SELECT_CAMERAS,)),)
    with pytest.raises(ValueError):
        SetupStateMachine(specs=spec)


def test_rejects_empty_spec():
    with pytest.raises(ValueError):
        SetupStateMachine(specs=())


def test_custom_two_step_spec():
    spec = (
        StepSpec(SetupStep.SELECT_CAMERAS, "Cameras"),
        StepSpec(SetupStep.PAIRED_PREVIEW, "Preview", prerequisites=(SetupStep.SELECT_CAMERAS,)),
    )
    machine = SetupStateMachine(specs=spec)
    assert machine.can_finish() is False
    machine.mark_complete(SetupStep.SELECT_CAMERAS)
    machine.advance()
    machine.mark_complete(SetupStep.PAIRED_PREVIEW)
    assert machine.can_finish() is True
    assert machine.can_advance() is False  # last step

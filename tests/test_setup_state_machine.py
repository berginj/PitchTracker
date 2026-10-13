"""Qt-free transition coverage for mandatory metric guided setup."""

from enum import Enum
import pytest

from contracts.setup_workflow import GuidedSetupStage as Stage
from ui.setup.state_machine import GUIDED_SETUP_SPEC, SetupStateMachine, SetupTransitionError, StepSpec


def test_default_spec_requires_all_five_stages():
    machine = SetupStateMachine()
    assert machine.current == Stage.CAMERAS
    assert machine.steps == tuple(Stage)
    assert len(GUIDED_SETUP_SPEC) == 5
    assert not any(spec.optional for spec in GUIDED_SETUP_SPEC)


def test_cannot_advance_until_current_complete():
    machine = SetupStateMachine()
    with pytest.raises(SetupTransitionError):
        machine.advance()
    machine.mark_complete(Stage.CAMERAS)
    assert machine.advance() == Stage.IMAGES


def test_prerequisites_and_back_navigation():
    machine = SetupStateMachine()
    with pytest.raises(SetupTransitionError):
        machine.go_to(Stage.FIELD)
    for stage in (Stage.CAMERAS, Stage.IMAGES, Stage.CALIBRATION):
        machine.mark_complete(stage)
    assert machine.go_to(Stage.FIELD) == Stage.FIELD
    assert machine.go_back() == Stage.CALIBRATION


@pytest.mark.parametrize("missing", tuple(Stage))
def test_required_stage_cannot_be_bypassed_to_finish(missing):
    machine = SetupStateMachine()
    for stage in machine.steps:
        if stage != missing:
            machine.mark_complete(stage)
    assert not machine.can_finish()
    assert missing in machine.missing_required()


def test_metric_calibration_is_not_skippable():
    machine = SetupStateMachine()
    for stage in (Stage.CAMERAS, Stage.IMAGES):
        machine.mark_complete(stage)
    machine.go_to(Stage.CALIBRATION)
    assert not machine.can_skip()
    with pytest.raises(SetupTransitionError):
        machine.skip()


def test_invalidation_cascades_through_downstream_evidence():
    machine = SetupStateMachine()
    for stage in machine.steps:
        machine.mark_complete(stage)
    assert machine.can_finish()
    machine.mark_complete(Stage.IMAGES, complete=False)
    assert machine.is_complete(Stage.CAMERAS)
    assert all(not machine.is_complete(stage) for stage in machine.steps[1:])


def test_reset_and_back_bounds():
    machine = SetupStateMachine()
    with pytest.raises(SetupTransitionError):
        machine.go_back()
    machine.mark_complete(Stage.CAMERAS)
    machine.advance()
    machine.reset()
    assert machine.current == Stage.CAMERAS and machine.progress() == (0, 5)


@pytest.mark.parametrize("spec", [
    (),
    (StepSpec(Stage.CAMERAS, "A"), StepSpec(Stage.CAMERAS, "B")),
    (StepSpec(Stage.IMAGES, "Images", prerequisites=(Stage.CAMERAS,)),),
])
def test_rejects_invalid_specs(spec):
    with pytest.raises(ValueError):
        SetupStateMachine(specs=spec)


def test_generic_engine_retains_explicit_optional_step_support():
    class OptionalWorkflow(Enum):
        FIRST = "first"
        NOTE = "note"
        LAST = "last"
    spec = (
        StepSpec(OptionalWorkflow.FIRST, "First"),
        StepSpec(OptionalWorkflow.NOTE, "Note", optional=True, prerequisites=(OptionalWorkflow.FIRST,)),
        StepSpec(OptionalWorkflow.LAST, "Last", prerequisites=(OptionalWorkflow.FIRST,)),
    )
    machine = SetupStateMachine(specs=spec)
    machine.mark_complete(OptionalWorkflow.FIRST)
    machine.advance()
    assert machine.skip() == OptionalWorkflow.LAST
    machine.mark_complete(OptionalWorkflow.LAST)
    assert machine.can_finish() and not machine.is_complete(OptionalWorkflow.NOTE)

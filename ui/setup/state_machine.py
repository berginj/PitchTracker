"""Enum-driven setup state machine for the stereo-rig wizard.

This replaces the ad-hoc ``list + isinstance`` step handoffs in the legacy
``setup_window`` with an explicit, Qt-free engine that owns:

* the canonical ordering of setup steps,
* which steps are optional (skippable),
* a prerequisite matrix (a step cannot be entered until its prerequisites are
  complete), and
* the transition guards (advance / back / skip / finish).

Keeping this pure-logic (no PySide6 import) makes the wizard's control flow
unit-testable with synthetic inputs, which is the whole point of the rebuild:
prove the setup flow is coherent before wiring it to real cameras.

The UI layer owns the step *widgets* and decides when a step is complete (by
calling :meth:`SetupStateMachine.mark_complete`); the machine owns *whether a
transition is legal*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Generic, List, Tuple, TypeVar, cast

from contracts.setup_workflow import GuidedSetupStage
from exceptions import PitchTrackerError
from log_config.logger import get_logger

logger = get_logger(__name__)


class SetupTransitionError(PitchTrackerError):
    """Raised when an illegal setup-state transition is requested."""


StepT = TypeVar("StepT", bound=Enum, default=GuidedSetupStage)


@dataclass(frozen=True)
class StepSpec(Generic[StepT]):
    """Static description of a single setup step.

    Attributes:
        step: The step identity.
        title: Human-readable title for the step indicator.
        optional: True if the step may be skipped without completing it.
        prerequisites: Steps that must be complete before this step can be
            entered. A step is only enterable once every prerequisite is in the
            completed set.
    """

    step: StepT
    title: str
    optional: bool = False
    prerequisites: Tuple[StepT, ...] = ()


GUIDED_SETUP_SPEC: Tuple[StepSpec[GuidedSetupStage], ...] = (
    StepSpec(GuidedSetupStage.CAMERAS, "Cameras"),
    StepSpec(GuidedSetupStage.IMAGES, "Image checks", prerequisites=(GuidedSetupStage.CAMERAS,)),
    StepSpec(GuidedSetupStage.CALIBRATION, "Calibration", prerequisites=(GuidedSetupStage.IMAGES,)),
    StepSpec(GuidedSetupStage.FIELD, "Field and regions", prerequisites=(GuidedSetupStage.CALIBRATION,)),
    StepSpec(GuidedSetupStage.READY, "Ready", prerequisites=(GuidedSetupStage.FIELD,)),
)


@dataclass
class SetupStateMachine(Generic[StepT]):
    """Drives ordered, prerequisite-gated traversal of setup steps.

    Args:
        specs: Ordered step specifications. Defaults to the canonical stereo spec.

    Raises:
        ValueError: If ``specs`` is empty, contains duplicate steps, or
            references a prerequisite that is not present in ``specs``.
    """

    specs: Tuple[StepSpec[StepT], ...] = cast(
        Tuple[StepSpec[StepT], ...],
        GUIDED_SETUP_SPEC,
    )
    _index: int = 0
    _completed: set = field(default_factory=set)
    _order: List[StepT] = field(default_factory=list, init=False)
    _by_step: Dict[StepT, StepSpec[StepT]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if not self.specs:
            raise ValueError("SetupStateMachine requires at least one step spec")
        self._order = [spec.step for spec in self.specs]
        if len(set(self._order)) != len(self._order):
            raise ValueError("Duplicate steps in setup spec")
        self._by_step = {spec.step: spec for spec in self.specs}
        for spec in self.specs:
            for prereq in spec.prerequisites:
                if prereq not in self._by_step:
                    raise ValueError(f"Step {spec.step.value} requires unknown prerequisite {prereq}")

    # -- Introspection -------------------------------------------------------

    @property
    def steps(self) -> Tuple[StepT, ...]:
        """Ordered tuple of steps."""
        return tuple(self._order)

    @property
    def current(self) -> StepT:
        """The currently active step."""
        return self._order[self._index]

    @property
    def current_index(self) -> int:
        """Zero-based index of the current step."""
        return self._index

    def spec_for(self, step: StepT) -> StepSpec[StepT]:
        """Return the :class:`StepSpec` for ``step``."""
        return self._by_step[step]

    def title_for(self, step: StepT) -> str:
        """Return the display title for ``step``."""
        return self._by_step[step].title

    def is_optional(self, step: StepT) -> bool:
        """True if ``step`` may be skipped."""
        return self._by_step[step].optional

    def is_complete(self, step: StepT) -> bool:
        """True if ``step`` is marked complete."""
        return step in self._completed

    # -- Prerequisite / transition guards ------------------------------------

    def prerequisites_met(self, step: StepT) -> bool:
        """True if every prerequisite of ``step`` is complete."""
        return all(p in self._completed for p in self._by_step[step].prerequisites)

    def can_enter(self, step: StepT) -> bool:
        """True if ``step`` may be entered now (prerequisites complete)."""
        return self.prerequisites_met(step)

    def mark_complete(self, step: StepT, complete: bool = True) -> None:
        """Mark ``step`` complete or incomplete.

        Marking a step incomplete also clears the completion of any step that
        (transitively) depends on it, so the operator cannot keep a downstream
        "complete" flag after invalidating an upstream step.
        """
        if complete:
            self._completed.add(step)
        else:
            self._completed.discard(step)
            self._invalidate_dependents(step)

    def _invalidate_dependents(self, step: StepT) -> None:
        changed = True
        while changed:
            changed = False
            for spec in self.specs:
                if spec.step in self._completed and not self.prerequisites_met(spec.step):
                    self._completed.discard(spec.step)
                    changed = True

    def can_advance(self) -> bool:
        """True if the wizard may advance from the current step.

        Advancing requires that the current step is complete (or optional) and
        that the next step's prerequisites are satisfied.
        """
        if self._index >= len(self._order) - 1:
            return False
        current = self.current
        if not (self.is_complete(current) or self.is_optional(current)):
            return False
        return self.can_enter(self._order[self._index + 1])

    def advance(self) -> StepT:
        """Advance to the next step.

        Raises:
            SetupTransitionError: If advancing is not currently legal.
        """
        if not self.can_advance():
            raise SetupTransitionError(
                f"Cannot advance from {self.current.value}: complete the step and its successor's "
                "prerequisites first."
            )
        self._index += 1
        logger.debug("Setup advanced to {}", self.current.value)
        return self.current

    def can_skip(self) -> bool:
        """True if the current (optional) step may be skipped."""
        if self._index >= len(self._order) - 1:
            return False
        return self.is_optional(self.current) and self.can_enter(self._order[self._index + 1])

    def skip(self) -> StepT:
        """Skip the current optional step without marking it complete.

        Raises:
            SetupTransitionError: If the current step is not skippable.
        """
        if not self.can_skip():
            raise SetupTransitionError(f"Step {self.current.value} is not skippable.")
        self._index += 1
        logger.debug("Setup skipped to {}", self.current.value)
        return self.current

    def can_go_back(self) -> bool:
        """True if there is a previous step."""
        return self._index > 0

    def go_back(self) -> StepT:
        """Return to the previous step.

        Raises:
            SetupTransitionError: If already at the first step.
        """
        if not self.can_go_back():
            raise SetupTransitionError("Already at the first step.")
        self._index -= 1
        return self.current

    def go_to(self, step: StepT) -> StepT:
        """Jump directly to ``step`` if its prerequisites are met.

        Raises:
            SetupTransitionError: If ``step`` is unknown or not enterable.
        """
        if step not in self._by_step:
            raise SetupTransitionError(f"Unknown step {step}")
        if not self.can_enter(step):
            raise SetupTransitionError(f"Prerequisites for {step.value} are not complete.")
        self._index = self._order.index(step)
        return self.current

    def can_finish(self) -> bool:
        """True if every required (non-optional) step is complete."""
        return all(spec.step in self._completed for spec in self.specs if not spec.optional)

    def missing_required(self) -> List[StepT]:
        """Required steps that are not yet complete (in order)."""
        return [spec.step for spec in self.specs if not spec.optional and spec.step not in self._completed]

    def reset(self) -> None:
        """Return to the first step and clear all completion state."""
        self._index = 0
        self._completed.clear()

    def progress(self) -> Tuple[int, int]:
        """Return ``(completed_required, total_required)``."""
        required = [spec for spec in self.specs if not spec.optional]
        done = sum(1 for spec in required if spec.step in self._completed)
        return done, len(required)

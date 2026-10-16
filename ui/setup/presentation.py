"""Read-only guided setup presentation; the service owns validity and saves."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SetupPresentation:
    stage: str
    generation: int
    changed: bool
    readiness: str
    blockers: tuple[str, ...]

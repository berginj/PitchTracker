"""Contracts for immediately saved, generation-bound guided rig setup."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GuidedSetupStage(Enum):
    CAMERAS = "cameras"
    IMAGES = "images"
    CALIBRATION = "calibration"
    FIELD = "field"
    READY = "ready"


@dataclass(frozen=True)
class SetupCheck:
    passed: bool
    generation: int
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {"passed": self.passed, "generation": self.generation, "diagnostics": self.diagnostics}


@dataclass(frozen=True)
class SetupReadiness:
    status: str
    blockers: tuple[str, ...]
    permits_recording: bool


@dataclass(frozen=True)
class FieldTarget:
    target_id: str
    left_pixel: tuple[float, float]
    right_pixel: tuple[float, float]
    field_xyz_ft: tuple[float, float, float]
    holdout: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "left_pixel": list(self.left_pixel),
            "right_pixel": list(self.right_pixel),
            "field_xyz_ft": list(self.field_xyz_ft),
            "holdout": self.holdout,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> FieldTarget:
        return cls(
            str(payload["target_id"]), tuple(payload["left_pixel"]), tuple(payload["right_pixel"]),
            tuple(payload["field_xyz_ft"]), bool(payload.get("holdout", False)),
        )

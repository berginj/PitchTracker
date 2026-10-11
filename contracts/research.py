"""Typed requests for desktop measurement research tooling."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class SessionInspectionRequest:
    session_dir: Path
    correlation_id: str = field(default_factory=lambda: uuid4().hex)

    def to_payload(self) -> dict[str, Any]:
        return {"session_dir": str(self.session_dir), "correlation_id": self.correlation_id}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SessionInspectionRequest:
        return cls(Path(payload["session_dir"]), str(payload["correlation_id"]))


@dataclass(frozen=True)
class MeasurementWorkspaceRequest:
    protocol: dict[str, Any]
    dataset: dict[str, Any]
    session_dir: Path
    correlation_id: str = field(default_factory=lambda: uuid4().hex)

    def to_payload(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "dataset": self.dataset,
            "session_dir": str(self.session_dir),
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> MeasurementWorkspaceRequest:
        return cls(
            dict(payload["protocol"]),
            dict(payload["dataset"]),
            Path(payload["session_dir"]),
            str(payload["correlation_id"]),
        )


@dataclass(frozen=True)
class ResearchToolResult:
    report: dict[str, Any]
    correlation_id: str

    def to_payload(self) -> dict[str, Any]:
        return {"report": self.report, "correlation_id": self.correlation_id}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ResearchToolResult:
        return cls(dict(payload["report"]), str(payload["correlation_id"]))

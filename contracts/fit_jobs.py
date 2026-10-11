"""Local, immutable-source research batch contracts."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class FitBatchRequest:
    session_dirs: tuple[Path, ...]
    output_dir: Path
    workflow: str = "observations"
    backend: str = "cpu"
    workers: int = 0
    overrides: dict[str, Any] = field(default_factory=dict)
    config_path: Path | None = None
    calibration_path: Path | None = None
    roi_path: Path | None = None
    field_transform_path: Path | None = None
    job_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.job_id):
            raise ValueError("Invalid batch job identifier")
        if self.workflow not in {"observations", "videos"} or self.backend not in {"cpu", "auto", "cuda", "reference"}:
            raise ValueError("Invalid batch workflow or backend")
        if not self.session_dirs or not 0 <= self.workers <= 16:
            raise ValueError("Select sessions and a worker count between 0 and 16")
        output = self.output_dir.resolve()
        for source in self.session_dirs:
            if output.is_relative_to(source.resolve()) or source.resolve().is_relative_to(output):
                raise ValueError("Research output must be separate from captured sessions")
        if self.workflow == "videos" and any(
            path is None
            for path in (
                self.config_path,
                self.calibration_path,
                self.roi_path,
                self.field_transform_path,
            )
        ):
            raise ValueError("Video replay requires explicit config, calibration, ROI and field transform files")

    def to_payload(self):
        return {
            "session_dirs": [str(path) for path in self.session_dirs],
            "output_dir": str(self.output_dir),
            "workflow": self.workflow,
            "backend": self.backend,
            "workers": self.workers,
            "overrides": self.overrides,
            "config_path": str(self.config_path) if self.config_path else None,
            "calibration_path": str(self.calibration_path) if self.calibration_path else None,
            "roi_path": str(self.roi_path) if self.roi_path else None,
            "field_transform_path": str(self.field_transform_path) if self.field_transform_path else None,
            "job_id": self.job_id,
        }

    @classmethod
    def from_payload(cls, payload):
        data = dict(payload)
        data["session_dirs"] = tuple(Path(path) for path in data["session_dirs"])
        data["output_dir"] = Path(data["output_dir"])
        for name in ("config_path", "calibration_path", "roi_path", "field_transform_path"):
            data[name] = Path(data[name]) if data.get(name) else None
        return cls(**data)


@dataclass(frozen=True)
class FitBatchProgress:
    job_id: str
    completed: int
    total: int
    status: str
    pitch_id: str | None = None


@dataclass(frozen=True)
class FitBatchResult:
    report: dict[str, Any]


@dataclass(frozen=True)
class AnalysisJob:
    event: Any
    config: Any
    ball_radius_in: float
    manual_speed_mph: float | None
    camera_models: dict[str, Any] = field(default_factory=dict)
    submitted_ns: int = 0

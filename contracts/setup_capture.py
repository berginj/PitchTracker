"""Typed contracts for supervised stereo setup capture jobs.

The setup UI must not depend on an in-process camera call returning.  These
contracts cross the parent/worker process boundary and intentionally contain
only JSON-safe metadata plus paths to bounded, local scratch artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


SETUP_CAPTURE_SCHEMA_VERSION = "setup_capture.v1"


class SetupCapturePurpose(str, Enum):
    PREVIEW = "preview"
    SYNC = "sync"
    FOCUS = "focus"
    OVERLAP = "overlap"
    RECTIFY = "rectify"


class SetupCaptureState(str, Enum):
    STARTING = "starting"
    CAPTURING = "capturing"
    SUCCEEDED = "succeeded"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


class SetupCaptureFailureCode(str, Enum):
    CANCELLED_BY_OPERATOR = "CANCELLED_BY_OPERATOR"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    CAMERA_OPEN_FAILED = "CAMERA_OPEN_FAILED"
    CAMERA_CONFIG_FAILED = "CAMERA_CONFIG_FAILED"
    INSUFFICIENT_FRAMES = "INSUFFICIENT_FRAMES"
    WORKER_CRASHED = "WORKER_CRASHED"
    INVALID_RESULT = "INVALID_RESULT"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass(frozen=True)
class SetupCaptureRequest:
    """Immutable request sent to the camera-owning worker process."""

    correlation_id: str
    purpose: SetupCapturePurpose
    left_camera_id: str
    right_camera_id: str
    config_path: Path
    requested_frames_per_camera: int
    overall_deadline_ms: int = 20_000
    backend: str = "uvc"
    artifact_dir: Path | None = None
    config_sha256: str = ""
    assignment_generation: int = 0
    schema_version: str = SETUP_CAPTURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SETUP_CAPTURE_SCHEMA_VERSION:
            raise ValueError(f"unsupported setup capture schema: {self.schema_version}")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")
        if not self.left_camera_id or not self.right_camera_id:
            raise ValueError("left and right camera IDs are required")
        if self.left_camera_id == self.right_camera_id:
            raise ValueError("left and right cameras must be distinct")
        if self.requested_frames_per_camera < 1:
            raise ValueError("requested_frames_per_camera must be positive")
        if self.overall_deadline_ms < 100:
            raise ValueError("overall_deadline_ms must be at least 100ms")
        if self.backend not in {"uvc", "opencv", "sim"}:
            raise ValueError(f"unsupported setup capture backend: {self.backend}")

    def with_artifact_dir(self, artifact_dir: Path) -> "SetupCaptureRequest":
        return replace(self, artifact_dir=Path(artifact_dir))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "purpose": self.purpose.value,
            "left_camera_id": self.left_camera_id,
            "right_camera_id": self.right_camera_id,
            "config_path": str(self.config_path),
            "requested_frames_per_camera": self.requested_frames_per_camera,
            "overall_deadline_ms": self.overall_deadline_ms,
            "backend": self.backend,
            "artifact_dir": None if self.artifact_dir is None else str(self.artifact_dir),
            "config_sha256": self.config_sha256,
            "assignment_generation": self.assignment_generation,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SetupCaptureRequest":
        artifact_dir = payload.get("artifact_dir")
        return cls(
            schema_version=str(payload.get("schema_version", SETUP_CAPTURE_SCHEMA_VERSION)),
            correlation_id=str(payload["correlation_id"]),
            purpose=SetupCapturePurpose(str(payload["purpose"])),
            left_camera_id=str(payload["left_camera_id"]),
            right_camera_id=str(payload["right_camera_id"]),
            config_path=Path(str(payload["config_path"])),
            requested_frames_per_camera=int(payload["requested_frames_per_camera"]),
            overall_deadline_ms=int(payload.get("overall_deadline_ms", 20_000)),
            backend=str(payload.get("backend", "uvc")),
            artifact_dir=None if artifact_dir is None else Path(str(artifact_dir)),
            config_sha256=str(payload.get("config_sha256", "")),
            assignment_generation=int(payload.get("assignment_generation", 0)),
        )


@dataclass(frozen=True)
class SetupFrameRecord:
    camera_id: str
    frame_index: int
    t_capture_monotonic_ns: int
    width: int
    height: int
    pixfmt: str
    image_path: Path | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "frame_index": self.frame_index,
            "t_capture_monotonic_ns": self.t_capture_monotonic_ns,
            "width": self.width,
            "height": self.height,
            "pixfmt": self.pixfmt,
            "image_path": None if self.image_path is None else str(self.image_path),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SetupFrameRecord":
        image_path = payload.get("image_path")
        return cls(
            camera_id=str(payload["camera_id"]),
            frame_index=int(payload["frame_index"]),
            t_capture_monotonic_ns=int(payload["t_capture_monotonic_ns"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
            pixfmt=str(payload["pixfmt"]),
            image_path=None if image_path is None else Path(str(image_path)),
        )


@dataclass(frozen=True)
class SetupCaptureResult:
    """Successful capture result returned by the worker process."""

    correlation_id: str
    purpose: SetupCapturePurpose
    assignment_generation: int
    started_monotonic_ns: int
    completed_monotonic_ns: int
    requested_frames_per_camera: int
    left_frames: tuple[SetupFrameRecord, ...]
    right_frames: tuple[SetupFrameRecord, ...]
    modes: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    controls: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    errors_by_side: Mapping[str, int] = field(default_factory=dict)
    config_sha256: str = ""
    artifact_dir: Path | None = None
    schema_version: str = SETUP_CAPTURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SETUP_CAPTURE_SCHEMA_VERSION:
            raise ValueError(f"unsupported setup capture schema: {self.schema_version}")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")
        if self.completed_monotonic_ns < self.started_monotonic_ns:
            raise ValueError("capture completion precedes capture start")
        if self.requested_frames_per_camera < 1:
            raise ValueError("requested_frames_per_camera must be positive")

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "purpose": self.purpose.value,
            "assignment_generation": self.assignment_generation,
            "started_monotonic_ns": self.started_monotonic_ns,
            "completed_monotonic_ns": self.completed_monotonic_ns,
            "requested_frames_per_camera": self.requested_frames_per_camera,
            "left_frames": [frame.to_payload() for frame in self.left_frames],
            "right_frames": [frame.to_payload() for frame in self.right_frames],
            "modes": {side: dict(values) for side, values in self.modes.items()},
            "controls": {side: dict(values) for side, values in self.controls.items()},
            "errors_by_side": dict(self.errors_by_side),
            "config_sha256": self.config_sha256,
            "artifact_dir": None if self.artifact_dir is None else str(self.artifact_dir),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SetupCaptureResult":
        artifact_dir = payload.get("artifact_dir")
        return cls(
            schema_version=str(payload.get("schema_version", SETUP_CAPTURE_SCHEMA_VERSION)),
            correlation_id=str(payload["correlation_id"]),
            purpose=SetupCapturePurpose(str(payload["purpose"])),
            assignment_generation=int(payload.get("assignment_generation", 0)),
            started_monotonic_ns=int(payload["started_monotonic_ns"]),
            completed_monotonic_ns=int(payload["completed_monotonic_ns"]),
            requested_frames_per_camera=int(payload["requested_frames_per_camera"]),
            left_frames=tuple(SetupFrameRecord.from_payload(item) for item in payload.get("left_frames", ())),
            right_frames=tuple(SetupFrameRecord.from_payload(item) for item in payload.get("right_frames", ())),
            modes={str(side): dict(values) for side, values in dict(payload.get("modes", {})).items()},
            controls={str(side): dict(values) for side, values in dict(payload.get("controls", {})).items()},
            errors_by_side={str(side): int(value) for side, value in dict(payload.get("errors_by_side", {})).items()},
            config_sha256=str(payload.get("config_sha256", "")),
            artifact_dir=None if artifact_dir is None else Path(str(artifact_dir)),
        )


@dataclass(frozen=True)
class SetupCaptureTerminal:
    correlation_id: str
    state: SetupCaptureState
    failure_code: SetupCaptureFailureCode | None = None
    message: str = ""
    force_killed: bool = False


__all__ = [
    "SETUP_CAPTURE_SCHEMA_VERSION",
    "SetupCaptureFailureCode",
    "SetupCapturePurpose",
    "SetupCaptureRequest",
    "SetupCaptureResult",
    "SetupCaptureState",
    "SetupCaptureTerminal",
    "SetupFrameRecord",
]

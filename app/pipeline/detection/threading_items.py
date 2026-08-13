"""Internal work items shared by detection thread-pool collaborators."""

from dataclasses import dataclass

from contracts import Detection, Frame


@dataclass(frozen=True)
class FrameWorkItem:
    opportunity_id: str
    label: str
    frame: Frame


@dataclass(frozen=True)
class DetectionResultItem:
    work: FrameWorkItem
    detections: list[Detection]


@dataclass(frozen=True)
class QueuePutResult:
    displaced: object | None = None
    accepted: bool = True

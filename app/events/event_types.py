"""Event types for service communication.

All events are immutable dataclasses that flow through the EventBus.
Services publish events when significant actions occur, and other services
subscribe to react to those events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.contracts import PitchSummary, SessionSummary
from contracts import Detection, Frame, RayObservation, StereoObservation
from contracts.evidence import (
    AssociationEdgeEvidence,
    DecisionArtifactBindings,
    PairingOutcomeEvidence,
    TriangulationDecisionEvidence,
)


@dataclass(frozen=True)
class FrameCapturedEvent:
    """Published when a frame is captured from camera.

    Published By: CaptureService
    Subscribed By: RecordingService (priority), DetectionService (best-effort)

    Frequency: 60 events/sec (30fps × 2 cameras)

    Attributes:
        camera_id: Camera identifier ("left" or "right")
        frame: Captured frame data
        timestamp_ns: Capture timestamp in nanoseconds
    """

    camera_id: str
    frame: Frame
    timestamp_ns: int


@dataclass(frozen=True)
class FrameProcessingOpportunityEvent:
    """A captured frame offered to the bounded detection pipeline."""

    opportunity_id: str
    frame_id: str
    camera_id: str
    frame_index: int
    timestamp_ns: int
    bindings: DecisionArtifactBindings = field(default_factory=DecisionArtifactBindings)


@dataclass(frozen=True)
class FrameProcessingOutcomeEvent:
    """Exactly one terminal detection-pipeline outcome for an opportunity."""

    opportunity_id: str
    frame_id: str
    camera_id: str
    frame_index: int
    timestamp_ns: int
    status: str
    detections: tuple[Detection, ...] = ()
    reason_codes: tuple[str, ...] = ()
    bindings: DecisionArtifactBindings = field(default_factory=DecisionArtifactBindings)


@dataclass(frozen=True)
class ObservationDetectedEvent:
    """Published when a stereo observation is generated.

    Published By: DetectionService (after stereo matching)
    Subscribed By: RecordingService, AnalysisService, PipelineOrchestrator

    Frequency: Variable, depends on ball detections (typically 0-30/sec)

    Attributes:
        observation: Stereo observation with 3D position
        timestamp_ns: Detection timestamp in nanoseconds
        confidence: Detection confidence score (0.0-1.0)
    """

    observation: StereoObservation
    timestamp_ns: int
    confidence: float = 1.0


@dataclass(frozen=True)
class RayObservationDetectedEvent:
    """Published when a per-camera calibrated ray observation is generated."""

    observation: RayObservation
    timestamp_ns: int
    confidence: float = 1.0


@dataclass(frozen=True)
class StereoFrameProcessedEvent:
    """Published once for every completed left/right frame pair.

    Unlike observation events, this event is also emitted for empty pairs. It
    is therefore the authoritative clock for pitch lifecycle transitions and
    pair-level error-rate accounting.
    """

    pair_id: str
    timestamp_ns: int
    left_timestamp_ns: int
    right_timestamp_ns: int
    left_frame_index: int
    right_frame_index: int
    lane_count: int
    plate_count: int
    observations: tuple[StereoObservation, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    adjusted_left_timestamp_ns: Optional[int] = None
    adjusted_right_timestamp_ns: Optional[int] = None
    time_sync_offset_ns: int = 0

    @property
    def raw_pair_skew_ns(self) -> int:
        return abs(self.left_timestamp_ns - self.right_timestamp_ns)

    @property
    def pair_skew_ns(self) -> int:
        left = self.left_timestamp_ns if self.adjusted_left_timestamp_ns is None else self.adjusted_left_timestamp_ns
        right = self.right_timestamp_ns if self.adjusted_right_timestamp_ns is None else self.adjusted_right_timestamp_ns
        return abs(left - right)


@dataclass(frozen=True)
class PairingOutcomeEvent:
    """Terminal matched/unmatched outcome covering every pairing input frame."""

    outcome: PairingOutcomeEvidence
    bindings: DecisionArtifactBindings = field(default_factory=DecisionArtifactBindings)


@dataclass(frozen=True)
class StereoAssociationOutcomeEvent:
    """Complete candidate graph, assignment, and triangulation decision bundle."""

    pair_id: str
    timestamp_ns: int
    primary_algorithm: str
    edges: tuple[AssociationEdgeEvidence, ...] = ()
    assigned_edge_ids: tuple[str, ...] = ()
    shadow_assigned_edge_ids: tuple[str, ...] = ()
    unmatched_candidate_ids: tuple[str, ...] = ()
    triangulations: tuple[TriangulationDecisionEvidence, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    schema_version: str = "decision_evidence.v2"
    bindings: DecisionArtifactBindings = field(default_factory=DecisionArtifactBindings)


@dataclass(frozen=True)
class PitchStartEvent:
    """Published when pitch detection begins.

    Published By: PipelineOrchestrator (from PitchStateMachineV2)
    Subscribed By: RecordingService (create PitchRecorder, write pre-roll)

    Frequency: Rare, typically 0-10 times per session

    Attributes:
        pitch_id: Unique identifier for the pitch
        pitch_index: Sequential pitch number in session
        timestamp_ns: When pitch started (first detection)
    """

    pitch_id: str
    pitch_index: int
    timestamp_ns: int


@dataclass(frozen=True)
class PitchEndEvent:
    """Published when pitch is finalized.

    Published By: PipelineOrchestrator (from PitchStateMachineV2)
    Subscribed By: RecordingService (finalize PitchRecorder), AnalysisService (analyze trajectory)

    Frequency: Rare, typically 0-10 times per session

    Attributes:
        pitch_id: Unique identifier for the pitch
        observations: All observations collected for this pitch
        timestamp_ns: When pitch ended (last detection + post-roll)
        duration_ns: Total duration of pitch in nanoseconds
    """

    pitch_id: str
    observations: List[StereoObservation]
    timestamp_ns: int
    duration_ns: int
    ray_observations: List[RayObservation] = field(default_factory=list)
    coordinate_frame: str = "camera"
    rig_profile_id: Optional[str] = None


@dataclass(frozen=True)
class PitchAnalyzedEvent:
    """Published when pitch analysis has produced a durable summary.

    Published By: AnalysisService
    Subscribed By: RecordingService, UI observers

    Attributes:
        pitch_id: Unique identifier for the pitch
        summary: Computed pitch summary
        session_summary: Latest aggregate session summary after this pitch
    """

    pitch_id: str
    summary: PitchSummary
    session_summary: SessionSummary


@dataclass(frozen=True)
class ConfigUpdateEvent:
    """Published when configuration changes during session.

    NOTE: Currently unused as config is static per session.
    Reserved for future use if runtime config updates are needed.

    Published By: ConfigService (if/when runtime updates added)
    Subscribed By: All services that need config

    Attributes:
        config_key: What configuration changed
        config_value: New value (as string, services cast as needed)
        timestamp_ns: When config changed
    """

    config_key: str
    config_value: str
    timestamp_ns: int


@dataclass(frozen=True)
class ErrorEvent:
    """Published when errors occur in services.

    Published By: Any service
    Subscribed By: MainWindow (for UI notifications), Logging

    Attributes:
        service_name: Which service encountered the error
        error_type: Error classification (e.g., "CameraConnectionError")
        message: Human-readable error message
        details: Optional additional context
        timestamp_ns: When error occurred
    """

    service_name: str
    error_type: str
    message: str
    details: str = ""
    timestamp_ns: int = 0

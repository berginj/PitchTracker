"""Event types for service communication.

All events are immutable dataclasses that flow through the EventBus.
Services publish events when significant actions occur, and other services
subscribe to react to those events.

AGT-001: Every applicable event carries an optional ``metadata`` field
(``EventMetadata``) providing message_type, schema_version, correlation_id,
timestamp_ns, and session_id/pitch_id/camera_id where applicable.
The field defaults to an empty ``EventMetadata()`` so all existing
positional constructors remain backwards-compatible.  ``__post_init__``
auto-hydrates a default metadata from top-level event fields, ensuring
``metadata.timestamp_ns`` always equals the event's own ``timestamp_ns``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.contracts import PitchSummary, SessionSummary
from app.events.event_metadata import EventMetadata, hydrate_metadata
from contracts import Detection, Frame, RayObservation, StereoObservation
from contracts.evidence import (
    AssociationEdgeEvidence,
    DecisionArtifactBindings,
    PairingOutcomeEvidence,
    TriangulationDecisionEvidence,
)


@dataclass(frozen=True)
class FrameCapturedEvent:
    """Published when a frame is captured from camera."""

    camera_id: str
    frame: Frame
    timestamp_ns: int
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "FrameCapturedEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
            correlation_id=f"{self.camera_id}_{getattr(self.frame, 'frame_index', 0)}",
            camera_id=self.camera_id,
        ))


@dataclass(frozen=True)
class FrameProcessingOpportunityEvent:
    """A captured frame offered to the bounded detection pipeline."""

    opportunity_id: str
    frame_id: str
    camera_id: str
    frame_index: int
    timestamp_ns: int
    bindings: DecisionArtifactBindings = field(default_factory=DecisionArtifactBindings)
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "FrameProcessingOpportunityEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
            correlation_id=self.opportunity_id,
            camera_id=self.camera_id,
        ))


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
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "FrameProcessingOutcomeEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
            correlation_id=self.opportunity_id,
            camera_id=self.camera_id,
        ))


@dataclass(frozen=True)
class ObservationDetectedEvent:
    """Published when a stereo observation is generated."""

    observation: StereoObservation
    timestamp_ns: int
    confidence: float = 1.0
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "ObservationDetectedEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
        ))


@dataclass(frozen=True)
class RayObservationDetectedEvent:
    """Published when a per-camera calibrated ray observation is generated."""

    observation: RayObservation
    timestamp_ns: int
    confidence: float = 1.0
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "RayObservationDetectedEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
        ))


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
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "StereoFrameProcessedEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
            correlation_id=self.pair_id,
        ))

    @property
    def raw_pair_skew_ns(self) -> int:
        return abs(self.left_timestamp_ns - self.right_timestamp_ns)

    @property
    def pair_skew_ns(self) -> int:
        left = (
            self.left_timestamp_ns
            if self.adjusted_left_timestamp_ns is None
            else self.adjusted_left_timestamp_ns
        )
        right = (
            self.right_timestamp_ns
            if self.adjusted_right_timestamp_ns is None
            else self.adjusted_right_timestamp_ns
        )
        return abs(left - right)


@dataclass(frozen=True)
class PairingOutcomeEvent:
    """Terminal matched/unmatched outcome covering every pairing input frame."""

    outcome: PairingOutcomeEvidence
    bindings: DecisionArtifactBindings = field(default_factory=DecisionArtifactBindings)
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        cid = getattr(self.outcome, "outcome_id", "") or ""
        object.__setattr__(self, "metadata", hydrate_metadata(
            "PairingOutcomeEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
            correlation_id=cid,
        ))

    @property
    def timestamp_ns(self) -> int:
        """Use the left timestamp when present, otherwise the right timestamp."""
        left = getattr(self.outcome, "left_timestamp_ns", None)
        if left is not None:
            return int(left)
        return int(getattr(self.outcome, "right_timestamp_ns", None) or 0)


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
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "StereoAssociationOutcomeEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
            correlation_id=self.pair_id,
        ))


@dataclass(frozen=True)
class PitchStartEvent:
    """Published when pitch detection begins."""

    pitch_id: str
    pitch_index: int
    timestamp_ns: int
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "PitchStartEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
            correlation_id=self.pitch_id,
            pitch_id=self.pitch_id,
        ))


@dataclass(frozen=True)
class PitchEndEvent:
    """Published when pitch is finalized."""

    pitch_id: str
    observations: List[StereoObservation]
    timestamp_ns: int
    duration_ns: int
    ray_observations: List[RayObservation] = field(default_factory=list)
    coordinate_frame: str = "camera"
    rig_profile_id: Optional[str] = None
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "PitchEndEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
            correlation_id=self.pitch_id,
            pitch_id=self.pitch_id,
        ))


@dataclass(frozen=True)
class PitchAnalyzedEvent:
    """Published when pitch analysis has produced a durable summary."""

    pitch_id: str
    summary: PitchSummary
    session_summary: SessionSummary
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "PitchAnalyzedEvent", self.metadata,
            correlation_id=self.pitch_id,
            pitch_id=self.pitch_id,
        ))


@dataclass(frozen=True)
class ConfigUpdateEvent:
    """Reserved for future runtime config updates. Do not add metadata."""

    config_key: str
    config_value: str
    timestamp_ns: int


@dataclass(frozen=True)
class ErrorEvent:
    """Published when errors occur in services."""

    service_name: str
    error_type: str
    message: str
    details: str = ""
    timestamp_ns: int = 0
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", hydrate_metadata(
            "ErrorEvent", self.metadata,
            timestamp_ns=self.timestamp_ns,
        ))

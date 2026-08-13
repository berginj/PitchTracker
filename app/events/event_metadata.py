"""Versioned event metadata contract for AGT-001.

Every applicable asynchronous or durable event carries an ``EventMetadata``
instance that provides message_type, schema_version, correlation_id,
timestamp_ns, and optional session_id / pitch_id / camera_id.

Design goals:
- Backwards-compatible: existing positional constructors unchanged.
- Correlation propagation: stable IDs already present in the pipeline
  (pair_id, pitch_id, opportunity_id, frame_id) are reused rather than
  regenerated at every hop.
- Durable: ``to_dict`` / ``from_dict`` support serialization in manifests
  with safe defaults for older artifacts missing the ``metadata`` key.

Correlation conventions
-----------------------
- **Opportunity flow**: ``opportunity_id`` is the correlation_id from the
  ``FrameProcessingOpportunityEvent`` through the matching
  ``FrameProcessingOutcomeEvent``.  Camera_id and timestamp_ns come from
  the originating frame.
- **Pair / association flow**: ``pair_id`` is the correlation_id for
  ``StereoFrameProcessedEvent``, ``StereoAssociationOutcomeEvent``,
  ``PairingOutcomeEvent``, and every ``ObservationDetectedEvent`` produced
  from that pair.  The pair_id encodes *both* frame indices but is a single
  stable token (it does not reuse either frame_id).
- **Pitch flow**: ``pitch_id`` is the correlation_id for
  ``PitchStartEvent``, ``PitchEndEvent``, and ``PitchAnalyzedEvent``.
- **Session**: ``session_id`` links events end-to-end once a recording
  session is started; it is ``None`` before recording.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Dict, Optional

# Schema version for the EventMetadata contract itself.
EVENT_METADATA_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class EventMetadata:
    """Immutable metadata attached to pipeline events.

    Attributes:
        message_type: Canonical event class name (e.g. ``FrameCapturedEvent``).
        schema_version: Version of the event schema contract.
        correlation_id: Stable ID propagated end-to-end through the pipeline.
        timestamp_ns: Monotonic nanosecond timestamp of the event origin.
        session_id: Recording session identifier (set once recording starts).
        pitch_id: Pitch identifier (set for pitch-scoped events).
        camera_id: Camera label or serial (set for camera-scoped events).
    """

    message_type: str = ""
    schema_version: str = EVENT_METADATA_SCHEMA_VERSION
    correlation_id: str = ""
    timestamp_ns: int = 0
    session_id: Optional[str] = None
    pitch_id: Optional[str] = None
    camera_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary for durable storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "EventMetadata":
        """Deserialize from a dictionary, tolerating missing/extra keys."""
        if not data:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


def make_event_metadata(
    message_type: str,
    *,
    correlation_id: str = "",
    timestamp_ns: int = 0,
    session_id: Optional[str] = None,
    pitch_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    schema_version: str = EVENT_METADATA_SCHEMA_VERSION,
) -> EventMetadata:
    """Convenience factory for creating ``EventMetadata`` instances."""
    return EventMetadata(
        message_type=message_type,
        schema_version=schema_version,
        correlation_id=correlation_id,
        timestamp_ns=timestamp_ns,
        session_id=session_id,
        pitch_id=pitch_id,
        camera_id=camera_id,
    )


def hydrate_metadata(
    event_class_name: str,
    metadata: EventMetadata,
    *,
    timestamp_ns: int = 0,
    correlation_id: str = "",
    camera_id: Optional[str] = None,
    pitch_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> EventMetadata:
    """Fill default metadata from top-level event fields.

    Called from ``__post_init__`` on every event that carries metadata.
    When the caller supplies an explicit (non-default) metadata instance,
    only ``message_type`` and ``timestamp_ns`` are normalised to ensure
    they agree with the enclosing event.  When metadata is the bare
    default, all available top-level identifiers are copied in.
    """
    is_default = (
        metadata.message_type == ""
        and metadata.correlation_id == ""
        and metadata.timestamp_ns == 0
    )
    if is_default:
        return EventMetadata(
            message_type=event_class_name,
            schema_version=EVENT_METADATA_SCHEMA_VERSION,
            correlation_id=correlation_id,
            timestamp_ns=timestamp_ns,
            session_id=session_id,
            pitch_id=pitch_id,
            camera_id=camera_id,
        )
    # Explicit metadata — normalise message_type and timestamp_ns only
    patches: Dict[str, Any] = {}
    if metadata.message_type != event_class_name:
        patches["message_type"] = event_class_name
    if metadata.timestamp_ns == 0 and timestamp_ns != 0:
        patches["timestamp_ns"] = timestamp_ns
    if patches:
        return replace(metadata, **patches)
    return metadata

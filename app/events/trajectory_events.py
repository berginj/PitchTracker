"""Typed analysis-to-recording messages for reproducible fit inputs and comparisons."""

from dataclasses import dataclass, field
from typing import Any
from app.events.event_metadata import EventMetadata, hydrate_metadata


@dataclass(frozen=True)
class TrajectoryFitPreparedEvent:
    pitch_id: str
    request_envelope: dict[str, Any]
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self):
        object.__setattr__(
            self,
            "metadata",
            hydrate_metadata(
                "TrajectoryFitPreparedEvent",
                self.metadata,
                correlation_id=self.pitch_id,
                pitch_id=self.pitch_id,
            ),
        )


@dataclass(frozen=True)
class TrajectoryComparisonEvent:
    pitch_id: str
    results: dict[str, Any]
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def __post_init__(self):
        object.__setattr__(
            self,
            "metadata",
            hydrate_metadata(
                "TrajectoryComparisonEvent",
                self.metadata,
                correlation_id=self.pitch_id,
                pitch_id=self.pitch_id,
            ),
        )

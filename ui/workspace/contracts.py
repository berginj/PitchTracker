"""UI navigation context is separate from the pipeline's runtime status."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionPreparation:
    session_name: str = ""
    pitcher_name: str = ""
    prepared: bool = False


@dataclass(frozen=True)
class ReviewSelection:
    session_dir: Path | None = None
    session_id: str | None = None
    pitch_id: str | None = None
    pitcher_name: str | None = None


@dataclass(frozen=True)
class NavigationContext:
    page: str = "live"
    browsed_player: str | None = None
    review: ReviewSelection = ReviewSelection()

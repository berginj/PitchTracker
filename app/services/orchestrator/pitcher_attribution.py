"""Pitch-boundary attribution owned by the orchestrator's event coordinator."""

from dataclasses import replace
from typing import TYPE_CHECKING, cast

from contracts.pitcher import PitcherSelection, validate_pitcher_name

if TYPE_CHECKING:
    from app.services.orchestrator.event_coordination import EventCoordinator


class PitcherAttribution:
    def request_pitcher(self, name: str) -> PitcherSelection:
        owner = cast("EventCoordinator", self)
        name = validate_pitcher_name(name)
        with owner._tracking_lock:
            previous = owner._pitcher
            owner._pitcher = (replace(previous, pending_name=name if name != previous.active_name else None)
                              if owner._pitch_in_progress else PitcherSelection(active_name=name))
            owner._pitcher_changed(owner._pitcher)
            return owner._pitcher

    def _begin_pitch_attribution(self, pitch_id: str) -> str | None:
        owner = cast("EventCoordinator", self)
        owner._pitch_in_progress = True
        owner._pitcher = replace(owner._pitcher, pitch_id=pitch_id)
        owner._pitcher_changed(owner._pitcher)
        return owner._pitcher.active_name

    def _end_pitch_attribution(self) -> None:
        owner = cast("EventCoordinator", self)
        previous = owner._pitcher
        owner._pitch_in_progress = False
        owner._pitcher = PitcherSelection(active_name=previous.pending_name or previous.active_name)
        owner._pitcher_changed(owner._pitcher)

    def on_pitch_rejected(self, pitch_data, reason: str) -> None:
        owner = cast("EventCoordinator", self)
        with owner._tracking_lock:
            owner._end_pitch_attribution()

"""Shared state contract for legacy in-process pipeline mixins."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.pipeline.analysis.pitch_summary import PitchAnalyzer
    from app.pipeline.analysis.session_summary import SessionManager
    from app.pipeline.pitch_tracking_v2 import PitchStateMachineV2
    from app.pipeline.recording.pitch_recorder import PitchRecorder
    from app.pipeline.recording.session_recorder import SessionRecorder


class PipelineServiceMixinHost:
    """Attributes shared by the mixins composing ``InProcessPipelineService``."""

    _session_recorder: Optional[SessionRecorder]
    _pitch_recorder: Optional[PitchRecorder]
    _pitch_analyzer: Optional[PitchAnalyzer]
    _session_manager: Optional[SessionManager]
    _pitch_tracker: Optional[PitchStateMachineV2]

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

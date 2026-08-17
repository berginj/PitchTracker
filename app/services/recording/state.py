"""Type-only state contract shared by the recording service mixins."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

from app.pipeline.recording.evidence_journal import SessionEvidenceJournal
from app.pipeline.recording.pitch_recorder import PitchRecorder
from app.pipeline.recording.session_recorder import SessionRecorder
from app.services.recording.worker import BoundedRecordingWorker
from configs.settings import AppConfig


class RecordingServiceState:
    """State owned by ``RecordingServiceImpl`` and consumed by mixins.

    The mixins intentionally remain small modules, but their methods operate
    on one concrete service instance. This base makes that shared state
    explicit without pretending each mixin owns a separate copy of it.
    """

    _lock: threading.Lock
    _frame_worker: BoundedRecordingWorker
    _session_recorder: Optional[SessionRecorder]
    _pitch_recorder: Optional[PitchRecorder]
    _session_active: bool
    _session_paused: bool
    _pitch_active: bool
    _config: Optional[AppConfig]
    _config_path: Optional[str]
    _record_dir: Optional[Path]
    _session_name: Optional[str]
    _mode: Optional[str]
    _measured_speed_mph: Optional[float]
    _last_pitch_id: Optional[str]
    _current_pitch_id: Optional[str]
    _calibration_profile_id: Optional[str]
    _calibration_report: Optional[dict[str, Any]]
    _completed_pitch_recorders: dict[str, PitchRecorder]
    _pre_roll_buffer: dict[str, Any]
    _pitch_lifecycle_metadata: dict[str, dict[str, dict[str, Any]]]
    _decision_journal: Optional[SessionEvidenceJournal]
    _decision_evidence_incomplete: bool
    _subscribed: bool

    def _invoke_callback(self, name: str, payload: str) -> None:
        raise NotImplementedError

    def _detach_pitch_locked(self) -> tuple[PitchRecorder, Optional[str]] | None:
        raise NotImplementedError

    def _finalize_pitch_locked(self, recorder: PitchRecorder, pitch_id: Optional[str]) -> Optional[Path]:
        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

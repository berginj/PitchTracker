"""RecordingService implementation with EventBus integration.

Manages recording pipeline:
- Session recording (continuous video + metadata)
- Pitch recording (pitch-specific data with pre/post-roll)
- Frame writing (async I/O)
- EventBus integration for event-driven recording

Collaborator modules (extracted for the 500-line cap):
- session_lifecycle.py — start/stop/pause/resume session
- pitch_lifecycle.py — start/stop pitch, pre-roll, FIFO control commands
- frame_routing.py — record_frame, sync callback, writer stats
- event_handlers.py — EventBus handlers and subscription management
"""

from __future__ import annotations

import threading
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from app.events.event_bus import EventBus
from app.pipeline.recording.evidence_journal import SessionEvidenceJournal
from app.pipeline.recording.pitch_recorder import PitchRecorder
from app.pipeline.recording.session_recorder import SessionRecorder
from app.services.recording.event_handlers import EventHandlersMixin
from app.services.recording.frame_routing import FrameRoutingMixin
from app.services.recording.interface import RecordingService, RecordingCallback
from app.services.recording.pitch_lifecycle import PitchLifecycleMixin
from app.services.recording.session_lifecycle import SessionLifecycleMixin
from app.services.recording.worker import BoundedRecordingWorker
from configs.settings import AppConfig
from contracts import Frame, StereoObservation
from log_config.logger import get_logger

logger = get_logger(__name__)


class RecordingServiceImpl(
    SessionLifecycleMixin,
    PitchLifecycleMixin,
    FrameRoutingMixin,
    EventHandlersMixin,
    RecordingService,
):
    """Event-driven recording service implementation.

    Thread Safety:
        - All public methods are thread-safe
        - Frame writing uses a bounded worker queue with explicit drop metrics
        - EventBus handlers run on publisher's thread
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._lock = threading.Lock()

        # Session state
        self._session_recorder: Optional[SessionRecorder] = None
        self._session_active = False
        self._config: Optional[AppConfig] = None
        self._config_path: Optional[str] = None

        # Pitch state
        self._pitch_recorder: Optional[PitchRecorder] = None
        self._pitch_active = False
        self._current_pitch_id: Optional[str] = None
        self._completed_pitch_recorders: Dict[str, PitchRecorder] = {}

        # Pre-roll frame buffer (60 frames × 2 cameras)
        self._pre_roll_buffer: Dict[str, deque[Frame]] = {
            "left": deque(maxlen=60),
            "right": deque(maxlen=60),
        }

        # Callbacks and config
        self._callbacks: List[RecordingCallback] = []
        self._record_dir: Optional[Path] = None
        self._session_name: Optional[str] = None
        self._mode: Optional[str] = None
        self._measured_speed_mph: Optional[float] = None
        self._last_pitch_id: Optional[str] = None
        self._calibration_profile_id: Optional[str] = None
        self._calibration_report: Optional[dict] = None

        # EventBus and worker state
        self._subscribed = False
        self._session_paused = False
        self._frame_worker = BoundedRecordingWorker(
            cast(Any, getattr(self, "_record_frame_sync")), max_queue=240
        )
        self._decision_journal: Optional[SessionEvidenceJournal] = None
        self._decision_evidence_incomplete = False
        self._pitch_lifecycle_metadata: Dict[str, Dict[str, dict]] = {}

        logger.info("RecordingService initialized")

    # --- Accessors and simple mutators (kept in facade) ---

    def record_observation(self, obs: StereoObservation) -> None:
        """Record a stereo observation to current pitch."""
        with self._lock:
            if not self._pitch_active:
                raise RuntimeError("No pitch active")
            recorder = self._pitch_recorder
            if recorder is None:
                raise RuntimeError("No pitch recorder active")
            recorder.add_observation(obs)

    def set_record_directory(self, path: Optional[Path]) -> None:
        """Set base directory for all recordings."""
        with self._lock:
            if path is not None:
                if not path.exists():
                    raise FileNotFoundError(f"Directory does not exist: {path}")
                if not path.is_dir():
                    raise NotADirectoryError(f"Not a directory: {path}")
            self._record_dir = path
            logger.info(f"Recording directory set to: {path}")

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        """Set manual speed override captured in future session manifests."""
        with self._lock:
            self._measured_speed_mph = speed_mph

    def set_calibration_context(
        self, profile_id: Optional[str], report: Optional[dict]
    ) -> None:
        """Set calibration metadata captured in future session manifests."""
        with self._lock:
            self._calibration_profile_id = profile_id
            self._calibration_report = dict(report) if report is not None else None

    def get_session_dir(self) -> Optional[Path]:
        """Get directory path for current session."""
        with self._lock:
            if self._session_recorder is None:
                return None
            recorder = self._session_recorder
            return recorder.get_session_dir() if recorder is not None else None

    def get_pitch_dir(self) -> Optional[Path]:
        """Get directory path for current pitch."""
        with self._lock:
            if self._pitch_recorder is None:
                return None
            recorder = self._pitch_recorder
            return recorder.get_pitch_dir() if recorder is not None else None

    def is_recording_session(self) -> bool:
        with self._lock:
            return self._session_active

    def is_paused(self) -> bool:
        with self._lock:
            return self._session_paused

    def is_recording_pitch(self) -> bool:
        with self._lock:
            return self._pitch_active

    def on_recording_event(self, callback: RecordingCallback) -> None:
        """Register callback for recording events."""
        with self._lock:
            self._callbacks.append(callback)

    def get_disk_space_warning(self) -> Optional[str]:
        """Check disk space and return warning if low."""
        with self._lock:
            if self._session_recorder is None:
                return None
            has_space, warning = self._session_recorder._check_disk_space(
                required_gb=1.0
            )
            return warning if not has_space else None

    # --- Helpers ---

    def _invoke_callback(self, event_type: str, data: str) -> None:
        """Invoke all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Recording callback error: {e}", exc_info=True)

"""Session lifecycle management for RecordingService."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from app.pipeline.recording.evidence_journal import SessionEvidenceJournal
from app.pipeline.recording.session_recorder import SessionRecorder
from app.services.recording.state import RecordingServiceState
from log_config.logger import get_logger
from record.recorder import RecordingBundle

if TYPE_CHECKING:
    from configs.settings import AppConfig

logger = get_logger(__name__)


class SessionLifecycleMixin(RecordingServiceState):
    """Session start/stop/pause/resume and state accessors."""

    _session_name: Optional[str]
    _mode: Optional[str]
    _measured_speed_mph: Optional[float]
    _last_pitch_id: Optional[str]
    _decision_journal: Optional[SessionEvidenceJournal]

    def start_session(
        self: "RecordingServiceState",
        session_name: str,
        config: "AppConfig",
        mode: Optional[str] = None,
        pitch_id: Optional[str] = None,
        config_path: Optional[Path] = None,
    ) -> str:
        """Start a new recording session.

        Returns:
            Warning message if disk space is low, empty string otherwise
        """
        with self._lock:
            if self._session_active:
                raise RuntimeError("Session already active")
            if not self._frame_worker.start():
                raise RuntimeError(
                    "Recording worker from the previous session is still stopping; "
                    "retry after it exits"
                )

            self._config = config
            self._session_name = session_name
            self._mode = mode
            self._config_path = None if config_path is None else str(config_path)
            self._last_pitch_id = pitch_id

            recorder: Optional[SessionRecorder] = None
            try:
                recorder = SessionRecorder(config, self._record_dir)
                self._session_recorder = recorder
                session_dir, warning = recorder.start_session(
                    session_name=session_name,
                    pitch_id=f"session_{session_name}",
                )
                self._decision_journal = SessionEvidenceJournal(session_dir)
                self._decision_evidence_incomplete = False
            except Exception:
                self._session_recorder = None
                self._config = None
                self._session_name = None
                self._mode = None
                self._config_path = None
                self._last_pitch_id = None
                self._decision_journal = None
                self._frame_worker.stop(drain=False)
                if recorder is not None:
                    recorder._monitoring_disk = False
                    recorder._disk_monitor_stop.set()
                    thread = getattr(recorder, "_disk_monitor_thread", None)
                    if thread is not None and thread.is_alive():
                        thread.join(timeout=2.0)
                    recorder._close_writers()
                raise

            self._session_active = True
            self._session_paused = False

            self._subscribe_to_events()

            self._invoke_callback(
                "session_started",
                json.dumps({"session_dir": str(session_dir), "session_name": session_name}),
            )

            logger.info(f"Session started: {session_dir}")
            return str(warning)

    def stop_session(self: "RecordingServiceState") -> RecordingBundle:
        """Stop current session and finalize recordings."""
        with self._lock:
            if not self._session_active:
                raise RuntimeError("No session active")
            self._session_paused = True
            self._unsubscribe_from_events()
            journal = self._decision_journal
            self._decision_journal = None
            evidence_was_incomplete = self._decision_evidence_incomplete

        decision_evidence_manifest = None
        decision_evidence_complete = None
        if journal is not None:
            journal.close()
            journal_stats = journal.stats()
            decision_evidence_manifest = "evidence_journal/manifest.json"
            decision_evidence_complete = bool(
                not evidence_was_incomplete
                and journal_stats["dropped_required"] == 0
                and journal_stats["write_error"] is None
                and journal_stats["accepted"] == journal_stats["written"]
            )

        if not self._frame_worker.stop(drain=True):
            logger.error(
                "Recording frame queue did not drain before session stop; "
                "resources remain open"
            )
            raise RuntimeError(
                "Recording writer is still stopping; session resources remain "
                "open and stop can be retried"
            )

        with self._lock:
            if self._pitch_active:
                self._stop_pitch_internal()

            session_event_metadata = {
                "session_id": self._session_name,
                "message_type": "session_lifecycle",
                "schema_version": "1.0.0",
            }
            recorder = self._session_recorder
            if recorder is None:
                raise RuntimeError("Session recorder is not active")
            recorder.stop_session(
                config_path=self._config_path,
                pitch_id=self._last_pitch_id or "unknown",
                session_name=self._session_name,
                mode=self._mode,
                measured_speed_mph=self._measured_speed_mph,
                calibration_profile_id=self._calibration_profile_id,
                calibration_report=self._calibration_report,
                decision_evidence_manifest=decision_evidence_manifest,
                decision_evidence_complete=decision_evidence_complete,
                event_metadata=session_event_metadata,
            )

            session_dir = recorder.get_session_dir()

            self._session_recorder = None
            self._session_active = False
            self._session_paused = False
            self._config = None
            self._session_name = None
            self._mode = None
            self._measured_speed_mph = None
            self._last_pitch_id = None
            self._config_path = None
            self._completed_pitch_recorders.clear()
            self._decision_evidence_incomplete = False
            self._pitch_lifecycle_metadata.clear()

            self._pre_roll_buffer["left"].clear()
            self._pre_roll_buffer["right"].clear()

            self._invoke_callback(
                "session_ended", json.dumps({"session_dir": str(session_dir)})
            )

            logger.info(f"Session stopped: {session_dir}")

            return RecordingBundle(
                pitch_id="session",
                frames=[],
                detections=[],
                track=[],
                metrics=None,
                session_dir=session_dir,
            )

    def pause_session(self: "RecordingServiceState") -> None:
        """Pause recording while keeping the session open."""
        with self._lock:
            if not self._session_active:
                raise RuntimeError("No session active")
            if self._session_paused:
                return
            self._session_paused = True
            self._unsubscribe_from_events()

        if not self._frame_worker.wait_idle(timeout=10.0):
            logger.warning("Recording frame queue did not drain before pause")

        with self._lock:
            if self._pitch_active:
                self._stop_pitch_internal()

            self._pre_roll_buffer["left"].clear()
            self._pre_roll_buffer["right"].clear()
            logger.info("Recording session paused")

    def resume_session(self: "RecordingServiceState") -> None:
        """Resume recording for an existing session."""
        with self._lock:
            if not self._session_active:
                raise RuntimeError("No session active")
            if not self._session_paused:
                return

            self._subscribe_to_events()
            self._session_paused = False
            logger.info("Recording session resumed")

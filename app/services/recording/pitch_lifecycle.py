"""Pitch lifecycle management for RecordingService."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional, TYPE_CHECKING, cast

from app.pipeline.recording.pitch_recorder import PitchRecorder
from log_config.logger import get_logger

if TYPE_CHECKING:
    from app.services.recording.state import RecordingServiceState

logger = get_logger(__name__)


class PitchLifecycleMixin:
    """Pitch start/stop, pre-roll flush, and FIFO control commands."""

    _current_pitch_id: Optional[str]
    _last_pitch_id: Optional[str]

    def start_pitch(self: "RecordingServiceState", pitch_id: str) -> None:
        """Start recording a pitch within the current session.

        The recorder setup is injected into the worker FIFO as a control
        command so all frames queued before this point are processed first
        (FIFO guarantee).
        """
        with self._lock:
            if not self._session_active:
                raise RuntimeError("No session active")
            if self._pitch_active:
                raise RuntimeError("Pitch already active")
            session_recorder = self._session_recorder
            if session_recorder is None:
                raise RuntimeError("Session directory not available")
            session_dir = session_recorder.get_session_dir()
            if session_dir is None:
                raise RuntimeError("Session directory not available")
            config = self._config

        ready = threading.Event()
        error_box: list[Exception] = []

        def _activate_pitch() -> None:
            try:
                with self._lock:
                    if not self._session_active:
                        error_box.append(RuntimeError("No session active"))
                        return
                    if self._pitch_active:
                        error_box.append(RuntimeError("Pitch already active"))
                        return
                    recorder = PitchRecorder(
                        config=config, session_dir=session_dir, pitch_id=pitch_id
                    )
                    for frame in list(self._pre_roll_buffer["left"]):
                        recorder.buffer_pre_roll("left", frame)
                    for frame in list(self._pre_roll_buffer["right"]):
                        recorder.buffer_pre_roll("right", frame)
                    recorder.start_pitch()
                    self._pitch_recorder = recorder
                    self._pitch_active = True
                    self._current_pitch_id = pitch_id
                    self._last_pitch_id = pitch_id
            except Exception as exc:
                error_box.append(exc)
            finally:
                ready.set()

        if not self._frame_worker.submit_control(_activate_pitch):
            raise RuntimeError("Recording queue did not accept pitch start command")

        if not ready.wait(timeout=10.0):
            raise RuntimeError("Pitch start timed out waiting for worker")
        if error_box:
            raise error_box[0]

        with self._lock:
            pitch_dir = (
                str(self._pitch_recorder.get_pitch_dir()) if self._pitch_recorder else ""
            )
        self._invoke_callback(
            "pitch_started",
            json.dumps({"pitch_id": pitch_id, "pitch_dir": pitch_dir}),
        )
        logger.info(f"Pitch started: {pitch_id}")

    def stop_pitch(self: "RecordingServiceState") -> Optional[Path]:
        """Stop recording current pitch and finalize.

        Returns:
            Path to pitch directory, or None if no pitch was active
        """
        with self._lock:
            if not self._pitch_active:
                return None

        ready = threading.Event()
        result: list[tuple[PitchRecorder, Optional[str]]] = []

        def _detach_after_queued_frames() -> None:
            try:
                with self._lock:
                    detached = self._detach_pitch_locked()
                    if detached is not None:
                        result.append(detached)
            finally:
                ready.set()

        if not self._frame_worker.submit_control(_detach_after_queued_frames):
            raise RuntimeError("Recording queue did not accept pitch stop command")
        if not ready.wait(timeout=10.0):
            raise RuntimeError("Pitch stop timed out waiting for worker")
        if not result:
            return None

        with self._lock:
            return cast(Optional[Path], self._finalize_pitch_locked(*result[0]))

    def _stop_pitch_internal(self: "RecordingServiceState") -> Optional[Path]:
        """Internal pitch stop (assumes lock is held)."""
        detached = self._detach_pitch_locked()
        if detached is None:
            return None
        return cast(Optional[Path], self._finalize_pitch_locked(*detached))

    def _detach_pitch_locked(self: "RecordingServiceState"):
        """Fence new frame submissions from the current pitch."""
        if not self._pitch_active or self._pitch_recorder is None:
            return None
        recorder = self._pitch_recorder
        pitch_id = self._current_pitch_id
        self._pitch_recorder = None
        self._pitch_active = False
        self._current_pitch_id = None
        return recorder, pitch_id

    def _finalize_pitch_locked(
        self: "RecordingServiceState",
        recorder: PitchRecorder,
        pitch_id: Optional[str],
    ) -> Optional[Path]:
        """Close an already-detached recorder and retain it for analysis."""
        pitch_dir = recorder.get_pitch_dir()
        recorder.close(force=False)

        if pitch_id is not None and not (recorder.get_pitch_dir() / "manifest.json").exists():
            self._completed_pitch_recorders[pitch_id] = recorder

        self._invoke_callback(
            "pitch_ended", json.dumps({"pitch_id": pitch_id, "pitch_dir": str(pitch_dir)})
        )
        logger.info(f"Pitch stopped: {pitch_id}")
        return Path(pitch_dir)

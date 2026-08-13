"""RecordingService implementation with EventBus integration.

Manages recording pipeline:
- Session recording (continuous video + metadata)
- Pitch recording (pitch-specific data with pre/post-roll)
- Frame writing (async I/O)
- EventBus integration for event-driven recording
"""

from __future__ import annotations

import json
import threading
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional

from app.events.event_bus import EventBus
from app.events.event_types import (
    FrameCapturedEvent,
    FrameProcessingOpportunityEvent,
    FrameProcessingOutcomeEvent,
    ObservationDetectedEvent,
    PairingOutcomeEvent,
    PitchAnalyzedEvent,
    PitchStartEvent,
    PitchEndEvent,
    StereoFrameProcessedEvent,
    StereoAssociationOutcomeEvent,
)
from app.pipeline.recording.evidence_journal import SessionEvidenceJournal
from app.pipeline.recording.session_recorder import SessionRecorder
from app.pipeline.recording.pitch_recorder import PitchRecorder
from app.services.recording.interface import RecordingService, RecordingCallback
from app.services.recording.worker import BoundedRecordingWorker
from configs.settings import AppConfig
from contracts import Frame, StereoObservation
from log_config.logger import get_logger
from record.recorder import RecordingBundle

logger = get_logger(__name__)


class RecordingServiceImpl(RecordingService):
    """Event-driven recording service implementation.

    Features:
    - EventBus integration for event-driven recording
    - Pre-roll frame buffering (no dropped frames)
    - Priority recording (frames always written before detection)
    - Thread-safe frame writing
    - Session and pitch recording management

    Architecture:
        - Subscribes to FrameCapturedEvent (buffers for pre-roll + writes to session)
        - Subscribes to PitchStartEvent (creates PitchRecorder, flushes pre-roll)
        - Subscribes to ObservationDetectedEvent (records observations)
        - Subscribes to PitchEndEvent (finalizes pitch recording)

    Thread Safety:
        - All public methods are thread-safe
        - Frame writing uses a bounded worker queue with explicit drop metrics
        - EventBus handlers run on publisher's thread
    """

    def __init__(self, event_bus: EventBus):
        """Initialize recording service.

        Args:
            event_bus: EventBus instance for subscribing to events
        """
        self._event_bus = event_bus
        self._lock = threading.Lock()

        # Session recorder
        self._session_recorder: Optional[SessionRecorder] = None
        self._session_active = False
        self._config: Optional[AppConfig] = None
        self._config_path: Optional[str] = None

        # Pitch recorder
        self._pitch_recorder: Optional[PitchRecorder] = None
        self._pitch_active = False
        self._current_pitch_id: Optional[str] = None
        self._completed_pitch_recorders: Dict[str, PitchRecorder] = {}

        # Pre-roll frame buffer (before pitch detection)
        # Maintains 60 frames × 2 cameras (~8MB)
        self._pre_roll_buffer: Dict[str, deque[Frame]] = {"left": deque(maxlen=60), "right": deque(maxlen=60)}

        # Callbacks
        self._callbacks: List[RecordingCallback] = []

        # Recording directory
        self._record_dir: Optional[Path] = None

        # Session metadata (for manifest)
        self._session_name: Optional[str] = None
        self._mode: Optional[str] = None
        self._measured_speed_mph: Optional[float] = None
        self._last_pitch_id: Optional[str] = None
        self._calibration_profile_id: Optional[str] = None
        self._calibration_report: Optional[dict] = None

        # EventBus subscriptions (not subscribed until session starts)
        self._subscribed = False
        self._session_paused = False
        self._frame_worker = BoundedRecordingWorker(self._record_frame_sync, max_queue=240)
        self._decision_journal: Optional[SessionEvidenceJournal] = None
        self._decision_evidence_incomplete = False

        logger.info("RecordingService initialized")

    def start_session(
        self,
        session_name: str,
        config: AppConfig,
        mode: Optional[str] = None,
        pitch_id: Optional[str] = None,
        config_path: Optional[Path] = None,
    ) -> str:
        """Start a new recording session.

        Creates session directory, initializes video writers, exports
        calibration metadata, and subscribes to EventBus.

        Args:
            session_name: Name for the session (used in directory name)
            config: Application configuration
            mode: Optional mode identifier (e.g., "coaching", "practice")

        Returns:
            Warning message if disk space is low, empty string otherwise

        Raises:
            RecordingError: If session already active or initialization fails
        """
        with self._lock:
            if self._session_active:
                raise RuntimeError("Session already active")
            if not self._frame_worker.start():
                raise RuntimeError("Recording worker from the previous session is still stopping; retry after it exits")

            self._config = config
            self._session_name = session_name
            self._mode = mode
            self._config_path = None if config_path is None else str(config_path)
            self._last_pitch_id = pitch_id

            try:
                # Create session recorder
                self._session_recorder = SessionRecorder(config, self._record_dir)

                # Start session recording
                session_dir, warning = self._session_recorder.start_session(
                    session_name=session_name, pitch_id=f"session_{session_name}"  # Fallback pitch ID
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
                raise

            self._session_active = True
            self._session_paused = False

            # Subscribe to EventBus events
            self._subscribe_to_events()

            # Invoke callbacks
            self._invoke_callback(
                "session_started", json.dumps({"session_dir": str(session_dir), "session_name": session_name})
            )

            logger.info(f"Session started: {session_dir}")
            return warning

    def stop_session(self) -> RecordingBundle:
        """Stop current session and finalize recordings.

        Flushes video buffers, writes final manifests, generates summaries.

        Returns:
            RecordingBundle with paths to recorded files

        Raises:
            RecordingError: If no session is active
        """
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
            logger.error("Recording frame queue did not drain before session stop; resources remain open")
            raise RuntimeError(
                "Recording writer is still stopping; session resources remain open and stop can be retried"
            )

        with self._lock:
            # Stop any active pitch recording first
            if self._pitch_active:
                self._stop_pitch_internal()

            # Stop session recorder
            self._session_recorder.stop_session(
                config_path=self._config_path,
                pitch_id=self._last_pitch_id or "unknown",
                session_name=self._session_name,
                mode=self._mode,
                measured_speed_mph=self._measured_speed_mph,
                calibration_profile_id=self._calibration_profile_id,
                calibration_report=self._calibration_report,
                decision_evidence_manifest=decision_evidence_manifest,
                decision_evidence_complete=decision_evidence_complete,
            )

            session_dir = self._session_recorder.get_session_dir()

            # Clear state
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

            # Clear pre-roll buffers
            self._pre_roll_buffer["left"].clear()
            self._pre_roll_buffer["right"].clear()

            # Invoke callbacks
            self._invoke_callback("session_ended", json.dumps({"session_dir": str(session_dir)}))

            logger.info(f"Session stopped: {session_dir}")

            # Return empty bundle (actual data in session_dir)
            return RecordingBundle(
                pitch_id="session",
                frames=[],
                detections=[],
                track=[],
                metrics=None,
                session_dir=session_dir,
            )

    def pause_session(self) -> None:
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

    def resume_session(self) -> None:
        """Resume recording for an existing session."""
        with self._lock:
            if not self._session_active:
                raise RuntimeError("No session active")
            if not self._session_paused:
                return

            self._subscribe_to_events()
            self._session_paused = False
            logger.info("Recording session resumed")

    def start_pitch(self, pitch_id: str) -> None:
        """Start recording a pitch within the current session.

        Creates pitch subdirectory, initializes pitch recorder.

        Args:
            pitch_id: Unique identifier for the pitch

        Raises:
            RecordingError: If no session is active or pitch already active
        """
        # Validate state eagerly so callers get immediate errors.
        with self._lock:
            if not self._session_active:
                raise RuntimeError("No session active")
            if self._pitch_active:
                raise RuntimeError("Pitch already active")
            session_dir = self._session_recorder.get_session_dir()
            if session_dir is None:
                raise RuntimeError("Session directory not available")
            config = self._config

        # The actual recorder setup is injected into the worker FIFO as a
        # control command.  All frames queued before this point are processed
        # first (FIFO guarantee), so the pre-roll snapshot is exact.
        # Crucially, no publisher-blocking lock is held while waiting.
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
                    recorder = PitchRecorder(config=config, session_dir=session_dir, pitch_id=pitch_id)
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

        # Wait without holding any lock — publishers continue submitting.
        if not ready.wait(timeout=10.0):
            raise RuntimeError("Pitch start timed out waiting for worker")
        if error_box:
            raise error_box[0]

        # Callbacks run on caller's thread after the worker has committed.
        with self._lock:
            pitch_dir = str(self._pitch_recorder.get_pitch_dir()) if self._pitch_recorder else ""
        self._invoke_callback(
            "pitch_started",
            json.dumps({"pitch_id": pitch_id, "pitch_dir": pitch_dir}),
        )
        logger.info(f"Pitch started: {pitch_id}")

    def stop_pitch(self) -> Optional[Path]:
        """Stop recording current pitch and finalize.

        Writes pitch manifest, generates summary.

        Returns:
            Path to pitch directory, or None if no pitch was active

        Raises:
            RecordingError: If finalization fails
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
            return self._finalize_pitch_locked(*result[0])

    def _stop_pitch_internal(self) -> Optional[Path]:
        """Internal pitch stop (assumes lock is held).

        Returns:
            Path to pitch directory, or None if no pitch was active
        """
        detached = self._detach_pitch_locked()
        if detached is None:
            return None
        return self._finalize_pitch_locked(*detached)

    def _detach_pitch_locked(self):
        """Fence new frame submissions from the current pitch."""
        if not self._pitch_active or self._pitch_recorder is None:
            return None
        recorder = self._pitch_recorder
        pitch_id = self._current_pitch_id
        self._pitch_recorder = None
        self._pitch_active = False
        self._current_pitch_id = None
        return recorder, pitch_id

    def _finalize_pitch_locked(self, recorder: PitchRecorder, pitch_id: Optional[str]) -> Optional[Path]:
        """Close an already-detached recorder and retain it for analysis."""
        pitch_dir = recorder.get_pitch_dir()
        recorder.close(force=False)

        if pitch_id is not None and not (recorder.get_pitch_dir() / "manifest.json").exists():
            self._completed_pitch_recorders[pitch_id] = recorder

        # Invoke callbacks
        self._invoke_callback("pitch_ended", json.dumps({"pitch_id": pitch_id, "pitch_dir": str(pitch_dir)}))

        logger.info(f"Pitch stopped: {pitch_id}")
        return pitch_dir

    def record_frame(self, camera_id: str, frame: Frame) -> None:
        """Record a frame to current session.

        Frames are queued for bounded asynchronous writing. If the queue is
        full, the frame is dropped explicitly and recorded in worker metrics.

        Args:
            camera_id: Camera identifier ("left" or "right")
            frame: Frame to record

        Raises:
            RecordingError: If no session is active

        Thread-Safety: Thread-safe via lock
        Performance: < 1ms per frame
        """
        with self._lock:
            if not self._session_active:
                raise RuntimeError("No session active")
            if self._session_paused:
                return
        if not self._frame_worker.submit((camera_id, frame)):
            logger.warning(
                "Recording queue full; dropping newest frame camera=%s index=%s",
                camera_id,
                frame.frame_index,
            )

    def _record_frame_sync(self, item) -> None:
        """Perform codec and CSV I/O on the recording worker thread."""
        camera_id, frame = item
        with self._lock:
            if not self._session_active or self._session_recorder is None:
                return
            self._session_recorder.write_frame(camera_id, frame)

            # Buffer for pre-roll (always buffer even if no pitch active)
            self._pre_roll_buffer[camera_id].append(frame)

            # Write to pitch recorder if active (state read at processing
            # time — ordering is guaranteed by FIFO control commands).
            pitch_recorder = self._pitch_recorder if self._pitch_active else None
            if pitch_recorder is not None:
                pitch_recorder.write_frame(camera_id, frame)

                # Check if post-roll complete
                if pitch_recorder.should_close() and pitch_recorder is self._pitch_recorder:
                    self._stop_pitch_internal()

    def get_frame_writer_stats(self) -> dict:
        """Expose queue, loss, and failure rates for quality diagnostics."""
        stats = self._frame_worker.stats()
        attempted = stats.submitted + stats.dropped
        return {
            "submitted": stats.submitted,
            "written": stats.written,
            "dropped": stats.dropped,
            "failed": stats.failed,
            "queue_depth": stats.queue_depth,
            "drop_rate": stats.dropped / max(attempted, 1),
            "failure_rate": stats.failed / max(stats.submitted, 1),
            "drop_policy": "drop_newest",
        }

    def record_observation(self, obs: StereoObservation) -> None:
        """Record a stereo observation to current pitch.

        Args:
            obs: Stereo observation to record

        Raises:
            RecordingError: If no pitch is active

        Thread-Safety: Thread-safe via lock
        """
        with self._lock:
            if not self._pitch_active:
                raise RuntimeError("No pitch active")

            self._pitch_recorder.add_observation(obs)

    def set_record_directory(self, path: Optional[Path]) -> None:
        """Set base directory for all recordings.

        Args:
            path: Base directory path, or None to use default

        Raises:
            FileWriteError: If directory does not exist or is not writable

        Note: Only affects future sessions, not current session.
        """
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
            logger.info(f"Recording manual speed override set to: {speed_mph}")

    def set_calibration_context(self, profile_id: Optional[str], report: Optional[dict]) -> None:
        """Set calibration metadata captured in future session manifests."""
        with self._lock:
            self._calibration_profile_id = profile_id
            self._calibration_report = dict(report) if report is not None else None
            logger.info(f"Recording calibration context set to profile={profile_id}")

    def get_session_dir(self) -> Optional[Path]:
        """Get directory path for current session.

        Returns:
            Path to session directory, or None if no session active
        """
        with self._lock:
            if self._session_recorder is None:
                return None
            return self._session_recorder.get_session_dir()

    def get_pitch_dir(self) -> Optional[Path]:
        """Get directory path for current pitch.

        Returns:
            Path to pitch directory, or None if no pitch active
        """
        with self._lock:
            if self._pitch_recorder is None:
                return None
            return self._pitch_recorder.get_pitch_dir()

    def is_recording_session(self) -> bool:
        """Check if session recording is active.

        Returns:
            True if session is being recorded, False otherwise
        """
        with self._lock:
            return self._session_active

    def is_paused(self) -> bool:
        """Check if session recording is paused."""
        with self._lock:
            return self._session_paused

    def is_recording_pitch(self) -> bool:
        """Check if pitch recording is active.

        Returns:
            True if pitch is being recorded, False otherwise
        """
        with self._lock:
            return self._pitch_active

    def on_recording_event(self, callback: RecordingCallback) -> None:
        """Register callback for recording events.

        Callback will be invoked when recording events occur:
        - session_started
        - pitch_started
        - pitch_ended
        - session_ended

        Args:
            callback: Function to call with (event_type, data)

        Thread-Safety:
            - Callback registration is thread-safe
            - Callback invoked from recording thread
        """
        with self._lock:
            self._callbacks.append(callback)
            logger.debug(f"Registered recording callback ({len(self._callbacks)} total)")

    def get_disk_space_warning(self) -> Optional[str]:
        """Check disk space and return warning if low.

        Returns:
            Warning message if disk space < 1GB, None otherwise

        Note: Checks disk space of current recording directory.
        """
        with self._lock:
            if self._session_recorder is None:
                return None

            # Use SessionRecorder's disk space check
            has_space, warning = self._session_recorder._check_disk_space(required_gb=1.0)
            return warning if not has_space else None

    # EventBus Event Handlers

    def _on_frame_captured(self, event: FrameCapturedEvent) -> None:
        """Handle FrameCapturedEvent from EventBus.

        Writes frame to session video and buffers for pre-roll.

        Args:
            event: FrameCapturedEvent with camera_id, frame, timestamp_ns
        """
        try:
            self.record_frame(event.camera_id, event.frame)
        except Exception as e:
            logger.error(f"Error recording frame: {e}", exc_info=True)

    def _on_observation_detected(self, event: ObservationDetectedEvent) -> None:
        """Handle ObservationDetectedEvent from EventBus.

        Records observation to current pitch.

        Args:
            event: ObservationDetectedEvent with observation, timestamp_ns, confidence
        """
        try:
            if self._pitch_active:
                self.record_observation(event.observation)
        except Exception as e:
            logger.error(f"Error recording observation: {e}", exc_info=True)

    def _on_stereo_frame_processed(self, event: StereoFrameProcessedEvent) -> None:
        """Record pair-level timing and rejection evidence for the active pitch."""
        try:
            with self._lock:
                recorder = self._pitch_recorder if self._pitch_active else None
            if recorder is not None:
                recorder.add_stereo_pair(event)
        except Exception as e:
            logger.error(f"Error recording stereo-pair evidence: {e}", exc_info=True)

    def _on_decision_evidence(self, event) -> None:
        """Queue required replay evidence without doing disk I/O on its publisher."""

        with self._lock:
            journal = self._decision_journal
        if journal is None:
            return
        try:
            result = journal.submit_event(event, required=True)
        except Exception:
            logger.exception("Decision evidence journal submission failed")
            with self._lock:
                self._decision_evidence_incomplete = True
            return
        if not result.accepted:
            with self._lock:
                self._decision_evidence_incomplete = True
            logger.error("Required decision evidence was not journaled at sequence %s", result.sequence)

    def _on_pitch_start(self, event: PitchStartEvent) -> None:
        """Handle PitchStartEvent from EventBus.

        Creates pitch recorder and flushes pre-roll.

        Args:
            event: PitchStartEvent with pitch_id, pitch_index, timestamp_ns
        """
        try:
            self.start_pitch(event.pitch_id)
        except Exception as e:
            logger.error(f"Error starting pitch recording: {e}", exc_info=True)

    def _on_pitch_end(self, event: PitchEndEvent) -> None:
        """Handle PitchEndEvent from EventBus.

        Finalizes pitch recording and writes manifest.

        Args:
            event: PitchEndEvent with pitch_id, observations, timestamp_ns, duration_ns
        """
        try:
            logger.debug("PitchEndEvent received for %s", event.pitch_id)
            with self._lock:
                recorder = (
                    self._pitch_recorder if self._pitch_active and self._current_pitch_id == event.pitch_id else None
                )
            if recorder is not None:
                recorder.add_analysis_observations(
                    list(event.observations),
                    coordinate_frame=event.coordinate_frame,
                    rig_profile_id=event.rig_profile_id,
                )
                # Arm post-roll from the authoritative pitch-end timestamp.
                # Without this transition ``should_close()`` can never become
                # true, leaving the recorder active and blocking the next pitch.
                recorder.end_pitch(event.timestamp_ns)
        except Exception as e:
            logger.error(f"Error handling pitch end: {e}", exc_info=True)

    def _on_pitch_analyzed(self, event: PitchAnalyzedEvent) -> None:
        """Handle PitchAnalyzedEvent from EventBus.

        Writes the finalized pitch manifest once analysis is complete.
        """
        try:
            with self._lock:
                recorder = None
                if self._pitch_active and self._current_pitch_id == event.pitch_id:
                    recorder = self._pitch_recorder
                if recorder is None:
                    recorder = self._completed_pitch_recorders.get(event.pitch_id)

            if recorder is None:
                logger.warning("No pitch recorder available for analyzed pitch %s", event.pitch_id)
                return

            recorder.write_manifest(event.summary, self._config_path)

            with self._lock:
                self._completed_pitch_recorders.pop(event.pitch_id, None)
        except Exception as e:
            logger.error(f"Error writing pitch manifest: {e}", exc_info=True)

    # EventBus Subscription Management

    def _subscribe_to_events(self) -> None:
        """Subscribe to EventBus events.

        Called when session starts.
        """
        if self._subscribed:
            return

        self._event_bus.subscribe(FrameCapturedEvent, self._on_frame_captured)
        self._event_bus.subscribe(ObservationDetectedEvent, self._on_observation_detected)
        self._event_bus.subscribe(PitchStartEvent, self._on_pitch_start)
        self._event_bus.subscribe(PitchEndEvent, self._on_pitch_end)
        self._event_bus.subscribe(PitchAnalyzedEvent, self._on_pitch_analyzed)
        self._event_bus.subscribe(StereoFrameProcessedEvent, self._on_stereo_frame_processed)
        self._event_bus.subscribe(FrameProcessingOpportunityEvent, self._on_decision_evidence)
        self._event_bus.subscribe(FrameProcessingOutcomeEvent, self._on_decision_evidence)
        self._event_bus.subscribe(PairingOutcomeEvent, self._on_decision_evidence)
        self._event_bus.subscribe(StereoAssociationOutcomeEvent, self._on_decision_evidence)

        self._subscribed = True
        logger.info("RecordingService subscribed to EventBus")

    def _unsubscribe_from_events(self) -> None:
        """Unsubscribe from EventBus events.

        Called when session stops.
        """
        if not self._subscribed:
            return

        self._event_bus.unsubscribe(FrameCapturedEvent, self._on_frame_captured)
        self._event_bus.unsubscribe(ObservationDetectedEvent, self._on_observation_detected)
        self._event_bus.unsubscribe(PitchStartEvent, self._on_pitch_start)
        self._event_bus.unsubscribe(PitchEndEvent, self._on_pitch_end)
        self._event_bus.unsubscribe(PitchAnalyzedEvent, self._on_pitch_analyzed)
        self._event_bus.unsubscribe(StereoFrameProcessedEvent, self._on_stereo_frame_processed)
        self._event_bus.unsubscribe(FrameProcessingOpportunityEvent, self._on_decision_evidence)
        self._event_bus.unsubscribe(FrameProcessingOutcomeEvent, self._on_decision_evidence)
        self._event_bus.unsubscribe(PairingOutcomeEvent, self._on_decision_evidence)
        self._event_bus.unsubscribe(StereoAssociationOutcomeEvent, self._on_decision_evidence)

        self._subscribed = False
        logger.info("RecordingService unsubscribed from EventBus")

    # Helper Methods

    def _invoke_callback(self, event_type: str, data: str) -> None:
        """Invoke all registered callbacks.

        Args:
            event_type: Type of recording event
            data: Event-specific JSON data
        """
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Recording callback error: {e}", exc_info=True)

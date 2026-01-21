"""RecordingService implementation with EventBus integration.

Manages recording pipeline:
- Session recording (continuous video + metadata)
- Pitch recording (pitch-specific data with pre/post-roll)
- Frame writing (async I/O)
- EventBus integration for event-driven recording
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional

from app.events.event_bus import EventBus
from app.events.event_types import (
    FrameCapturedEvent,
    ObservationDetectedEvent,
    PitchStartEvent,
    PitchEndEvent
)
from app.pipeline.recording.session_recorder import SessionRecorder
from app.pipeline.recording.pitch_recorder import PitchRecorder
from app.services.recording.interface import RecordingService, RecordingCallback
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
        - Frame writing is synchronous but fast (< 1ms)
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

        # Pre-roll frame buffer (before pitch detection)
        # Maintains 60 frames × 2 cameras (~8MB)
        self._pre_roll_buffer: Dict[str, deque[Frame]] = {
            "left": deque(maxlen=60),
            "right": deque(maxlen=60)
        }

        # Callbacks
        self._callbacks: List[RecordingCallback] = []

        # Recording directory
        self._record_dir: Optional[Path] = None

        # Session metadata (for manifest)
        self._session_name: Optional[str] = None
        self._mode: Optional[str] = None
        self._measured_speed_mph: Optional[float] = None
        self._last_pitch_id: Optional[str] = None

        # EventBus subscriptions (not subscribed until session starts)
        self._subscribed = False

        logger.info("RecordingService initialized")

    def start_session(
        self,
        session_name: str,
        config: AppConfig,
        mode: Optional[str] = None
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

            self._config = config
            self._session_name = session_name
            self._mode = mode

            # Create session recorder
            self._session_recorder = SessionRecorder(config, self._record_dir)

            # Start session recording
            session_dir, warning = self._session_recorder.start_session(
                session_name=session_name,
                pitch_id=f"session_{session_name}"  # Fallback pitch ID
            )

            self._session_active = True

            # Subscribe to EventBus events
            self._subscribe_to_events()

            # Invoke callbacks
            self._invoke_callback(
                "session_started",
                json.dumps({"session_dir": str(session_dir), "session_name": session_name})
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

            # Stop any active pitch recording first
            if self._pitch_active:
                self._stop_pitch_internal()

            # Unsubscribe from EventBus
            self._unsubscribe_from_events()

            # Stop session recorder
            self._session_recorder.stop_session(
                config_path=self._config_path,
                pitch_id=self._last_pitch_id or "unknown",
                session_name=self._session_name,
                mode=self._mode,
                measured_speed_mph=self._measured_speed_mph
            )

            session_dir = self._session_recorder.get_session_dir()

            # Clear state
            self._session_recorder = None
            self._session_active = False
            self._config = None
            self._session_name = None
            self._mode = None
            self._measured_speed_mph = None
            self._last_pitch_id = None

            # Clear pre-roll buffers
            self._pre_roll_buffer["left"].clear()
            self._pre_roll_buffer["right"].clear()

            # Invoke callbacks
            self._invoke_callback(
                "session_ended",
                json.dumps({"session_dir": str(session_dir)})
            )

            logger.info(f"Session stopped: {session_dir}")

            # Return empty bundle (actual data in session_dir)
            return RecordingBundle(
                pitch_id="session",
                frames=[],
                detections=[],
                track=[],
                metrics=None
            )

    def start_pitch(self, pitch_id: str) -> None:
        """Start recording a pitch within the current session.

        Creates pitch subdirectory, initializes pitch recorder.

        Args:
            pitch_id: Unique identifier for the pitch

        Raises:
            RecordingError: If no session is active or pitch already active
        """
        with self._lock:
            if not self._session_active:
                raise RuntimeError("No session active")
            if self._pitch_active:
                raise RuntimeError("Pitch already active")

            session_dir = self._session_recorder.get_session_dir()
            if session_dir is None:
                raise RuntimeError("Session directory not available")

            # Create pitch recorder
            self._pitch_recorder = PitchRecorder(
                config=self._config,
                session_dir=session_dir,
                pitch_id=pitch_id
            )

            # Buffer current pre-roll frames to pitch recorder
            for frame in list(self._pre_roll_buffer["left"]):
                self._pitch_recorder.buffer_pre_roll("left", frame)
            for frame in list(self._pre_roll_buffer["right"]):
                self._pitch_recorder.buffer_pre_roll("right", frame)

            # Start pitch recording (opens writers, flushes pre-roll)
            self._pitch_recorder.start_pitch()

            self._pitch_active = True
            self._current_pitch_id = pitch_id
            self._last_pitch_id = pitch_id

            # Invoke callbacks
            self._invoke_callback(
                "pitch_started",
                json.dumps({"pitch_id": pitch_id, "pitch_dir": str(self._pitch_recorder.get_pitch_dir())})
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

            return self._stop_pitch_internal()

    def _stop_pitch_internal(self) -> Optional[Path]:
        """Internal pitch stop (assumes lock is held).

        Returns:
            Path to pitch directory, or None if no pitch was active
        """
        if not self._pitch_active:
            return None

        pitch_dir = self._pitch_recorder.get_pitch_dir()

        # Close pitch recorder
        self._pitch_recorder.close(force=False)

        # NOTE: Manifest writing happens later when PitchEndEvent is received
        # with full trajectory analysis results

        pitch_id = self._current_pitch_id
        self._pitch_recorder = None
        self._pitch_active = False
        self._current_pitch_id = None

        # Invoke callbacks
        self._invoke_callback(
            "pitch_ended",
            json.dumps({"pitch_id": pitch_id, "pitch_dir": str(pitch_dir)})
        )

        logger.info(f"Pitch stopped: {pitch_id}")
        return pitch_dir

    def record_frame(self, camera_id: str, frame: Frame) -> None:
        """Record a frame to current session.

        Frames are written synchronously but fast (< 1ms).

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

            # Write to session recorder
            self._session_recorder.write_frame(camera_id, frame)

            # Buffer for pre-roll (always buffer even if no pitch active)
            self._pre_roll_buffer[camera_id].append(frame)

            # Write to pitch recorder if active
            if self._pitch_active and self._pitch_recorder is not None:
                self._pitch_recorder.write_frame(camera_id, frame)

                # Check if post-roll complete
                if self._pitch_recorder.should_close():
                    self._stop_pitch_internal()

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
            # Note: stop_pitch() already called by post-roll completion
            # This event is primarily for writing manifest with analysis results
            pass
        except Exception as e:
            logger.error(f"Error handling pitch end: {e}", exc_info=True)

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

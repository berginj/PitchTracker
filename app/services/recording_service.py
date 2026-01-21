"""RecordingService interface for recording frames and metadata.

Responsibility: Record sessions, pitches, frames, and observations to disk.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

from configs.settings import AppConfig
from contracts import Frame, StereoObservation
from record.recorder import RecordingBundle


# Type alias for callback
RecordingCallback = Callable[[str, str], None]
"""Callback invoked when recording events occur.

Args:
    event_type: "session_started", "pitch_started", "pitch_ended", "session_ended"
    data: Event-specific data (JSON string)
"""


class RecordingService(ABC):
    """Abstract interface for recording service.

    Manages recording pipeline:
    - Session recording (continuous video + metadata)
    - Pitch recording (pitch-specific data)
    - Frame writing (async I/O)
    - Manifest generation
    - Disk space monitoring

    Thread-Safety:
        - All methods are thread-safe
        - Frame writing is async (non-blocking)
        - Callbacks invoked from recording thread
    """

    @abstractmethod
    def start_session(
        self,
        session_name: str,
        config: AppConfig,
        mode: Optional[str] = None
    ) -> str:
        """Start a new recording session.

        Creates session directory, initializes video writers, exports
        calibration metadata.

        Args:
            session_name: Name for the session (used in directory name)
            config: Application configuration
            mode: Optional mode identifier (e.g., "coaching", "practice")

        Returns:
            Warning message if disk space is low, empty string otherwise

        Raises:
            FileWriteError: If session directory cannot be created
            RecordingError: If video writers cannot be initialized

        Note: Only one session can be active at a time.
        """

    @abstractmethod
    def stop_session(self) -> RecordingBundle:
        """Stop current session and finalize recordings.

        Flushes video buffers, writes final manifests, generates summaries.

        Returns:
            RecordingBundle with paths to recorded files

        Raises:
            RecordingError: If no session is active
            FileWriteError: If finalization fails

        Note: This may take several seconds to flush buffers.
        """

    @abstractmethod
    def start_pitch(self, pitch_id: str) -> None:
        """Start recording a pitch within the current session.

        Creates pitch subdirectory, initializes pitch recorder.

        Args:
            pitch_id: Unique identifier for the pitch

        Raises:
            RecordingError: If no session is active
            FileWriteError: If pitch directory cannot be created

        Note: Multiple pitches can be recorded per session.
        """

    @abstractmethod
    def stop_pitch(self) -> Optional[Path]:
        """Stop recording current pitch and finalize.

        Writes pitch manifest, generates summary.

        Returns:
            Path to pitch directory, or None if no pitch was active

        Raises:
            RecordingError: If finalization fails

        Note: Returns quickly - actual finalization is async.
        """

    @abstractmethod
    def record_frame(self, camera_id: str, frame: Frame) -> None:
        """Record a frame to current session.

        Frames are written asynchronously to avoid blocking capture.

        Args:
            camera_id: Camera identifier ("left" or "right")
            frame: Frame to record

        Raises:
            RecordingError: If no session is active

        Thread-Safety: Non-blocking, queues frame for async write.
        Performance: Returns in < 1ms, actual write happens async.
        """

    @abstractmethod
    def record_observation(self, obs: StereoObservation) -> None:
        """Record a stereo observation to current pitch.

        Args:
            obs: Stereo observation to record

        Raises:
            RecordingError: If no pitch is active

        Thread-Safety: Thread-safe, buffers for batch write.
        """

    @abstractmethod
    def set_record_directory(self, path: Optional[Path]) -> None:
        """Set base directory for all recordings.

        Args:
            path: Base directory path, or None to use default

        Raises:
            FileWriteError: If directory does not exist or is not writable

        Note: Only affects future sessions, not current session.
        """

    @abstractmethod
    def get_session_dir(self) -> Optional[Path]:
        """Get directory path for current session.

        Returns:
            Path to session directory, or None if no session active
        """

    @abstractmethod
    def get_pitch_dir(self) -> Optional[Path]:
        """Get directory path for current pitch.

        Returns:
            Path to pitch directory, or None if no pitch active
        """

    @abstractmethod
    def is_recording_session(self) -> bool:
        """Check if session recording is active.

        Returns:
            True if session is being recorded, False otherwise
        """

    @abstractmethod
    def is_recording_pitch(self) -> bool:
        """Check if pitch recording is active.

        Returns:
            True if pitch is being recorded, False otherwise
        """

    @abstractmethod
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

    @abstractmethod
    def get_disk_space_warning(self) -> Optional[str]:
        """Check disk space and return warning if low.

        Returns:
            Warning message if disk space < 1GB, None otherwise

        Note: Checks disk space of current recording directory.
        """

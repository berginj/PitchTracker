"""Qt-safe wrapper for PipelineService with signal-based communication.

This wrapper ensures all callbacks from worker threads are properly marshalled
to the Qt main thread using signals, preventing "QObject: Cannot stop timers
from another thread" errors.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6 import QtCore

from app.pipeline_service import InProcessPipelineService
from app.pipeline.pitch_tracking_v2 import PitchData

logger = logging.getLogger(__name__)


class QtPipelineService(QtCore.QObject):
    """Qt-safe wrapper for pipeline service with thread-safe signal emission.

    This class wraps InProcessPipelineService and converts background thread
    callbacks into Qt signals that are safely handled on the main thread.

    Signals:
        pitch_started: Emitted when a pitch starts (pitch_index, pitch_data)
        pitch_ended: Emitted when a pitch ends (pitch_data)
    """

    # Define signals (these are thread-safe and handled on main thread)
    pitch_started = QtCore.Signal(int, object)  # (pitch_index, PitchData)
    pitch_ended = QtCore.Signal(object)  # (PitchData)

    def __init__(self, backend: str = "uvc", parent: Optional[QtCore.QObject] = None):
        """Initialize Qt-safe pipeline service.

        Args:
            backend: Camera backend ("uvc" or other)
            parent: Optional Qt parent object
        """
        super().__init__(parent)

        # Create underlying service
        self._service = InProcessPipelineService(backend=backend)

        # Set up callbacks to emit signals (signals are thread-safe)
        # Note: We don't set these here because they need to be set during
        # start_recording when the pitch tracker is created

    def _on_pitch_start_callback(self, pitch_index: int, pitch_data: PitchData) -> None:
        """Internal callback for pitch start - emits signal.

        This is called from a worker thread but the signal emission is thread-safe.
        The signal will be delivered to slots on the main Qt thread.

        Args:
            pitch_index: Pitch index (1-based)
            pitch_data: Pitch data
        """
        try:
            logger.debug(f"Pitch {pitch_index} started (worker thread), emitting signal")
            # Signal emission is thread-safe - Qt will marshal to main thread
            self.pitch_started.emit(pitch_index, pitch_data)
        except Exception as e:
            logger.error(f"Error emitting pitch_started signal: {e}", exc_info=True)

    def _on_pitch_end_callback(self, pitch_data: PitchData) -> None:
        """Internal callback for pitch end - emits signal.

        This is called from a worker thread but the signal emission is thread-safe.
        The signal will be delivered to slots on the main Qt thread.

        Args:
            pitch_data: Pitch data
        """
        try:
            logger.debug("Pitch ended (worker thread), emitting signal")
            # Signal emission is thread-safe - Qt will marshal to main thread
            self.pitch_ended.emit(pitch_data)
        except Exception as e:
            logger.error(f"Error emitting pitch_ended signal: {e}", exc_info=True)

    # Delegate all other methods to the underlying service
    def start_capture(self, config, left_serial: str, right_serial: str, config_path=None):
        """Start camera capture (delegates to underlying service)."""
        return self._service.start_capture(config, left_serial, right_serial, config_path)

    def stop_capture(self):
        """Stop camera capture (delegates to underlying service)."""
        return self._service.stop_capture()

    def is_capturing(self) -> bool:
        """Check if capturing (delegates to underlying service)."""
        return self._service.is_capturing()

    def start_recording(self, pitch_id: Optional[str] = None, session_name: Optional[str] = None, mode: Optional[str] = None) -> str:
        """Start recording (delegates to underlying service)."""
        # Override the pitch tracker callbacks to use our signal-emitting versions
        warning = self._service.start_recording(pitch_id, session_name, mode)

        # Replace the callbacks with our signal-emitting versions
        if hasattr(self._service, '_pitch_tracker') and self._service._pitch_tracker:
            self._service._pitch_tracker.set_callbacks(
                on_pitch_start=self._on_pitch_start_callback,
                on_pitch_end=self._on_pitch_end_callback,
            )
            logger.debug("Pitch tracker callbacks replaced with signal-emitting versions")

        return warning

    def stop_recording(self):
        """Stop recording (delegates to underlying service)."""
        return self._service.stop_recording()

    def get_preview_frames(self):
        """Get preview frames (delegates to underlying service)."""
        return self._service.get_preview_frames()

    def get_recent_pitches(self):
        """Get recent pitches (delegates to underlying service)."""
        return self._service.get_recent_pitches()

    def get_stats(self):
        """Get camera stats (delegates to underlying service)."""
        return self._service.get_stats()

    def set_record_directory(self, path: Optional[Path]):
        """Set recording directory (delegates to underlying service)."""
        return self._service.set_record_directory(path)

    def set_manual_speed_mph(self, speed_mph: Optional[float]):
        """Set manual speed (delegates to underlying service)."""
        return self._service.set_manual_speed_mph(speed_mph)

    def get_last_session_summary(self):
        """Get last session summary (delegates to underlying service)."""
        return self._service.get_last_session_summary()

    def reload_config(self, config):
        """Reload configuration (delegates to underlying service)."""
        return self._service.reload_config(config)

    def reload_rois(self):
        """Reload ROIs (delegates to underlying service)."""
        return self._service.reload_rois()

"""Recording service module - Async recording of frames and metadata.

This module provides session recording, pitch recording, async frame writing,
and disk space monitoring.
"""

from .interface import RecordingService, RecordingCallback

__all__ = ["RecordingService", "RecordingCallback"]

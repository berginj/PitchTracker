"""Detection service module - Detection orchestration and stereo matching.

This module provides object detection, stereo matching, lane gating,
and observation generation.
"""

from .interface import DetectionService, ObservationCallback

__all__ = ["DetectionService", "ObservationCallback"]

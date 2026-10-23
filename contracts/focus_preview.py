"""Transient focus-preview frames; never calibration or recording evidence."""

from dataclasses import dataclass

import numpy as np

from contracts.timing import TimestampEvidence

FOCUS_PREVIEW_SCHEMA = "focus_preview.v1"


@dataclass(frozen=True)
class FocusPreviewFrame:
    """One decoded display frame with its original camera identity and timing."""

    side: str
    camera_id: str
    frame_index: int
    t_capture_monotonic_ns: int
    image: np.ndarray
    timing: TimestampEvidence

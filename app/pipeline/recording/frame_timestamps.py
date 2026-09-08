"""Additive timestamp CSV columns shared by pitch and session recording."""

import json

from contracts import Frame

TIMESTAMP_COLUMNS = ["camera_id", "frame_index", "t_capture_monotonic_ns", "capture_epoch", "timestamp_evidence"]


def timestamp_row(frame: Frame) -> list:
    return [
        frame.camera_id,
        frame.frame_index,
        frame.t_capture_monotonic_ns,
        frame.capture_epoch,
        json.dumps(frame.timing.to_payload(), sort_keys=True),
    ]

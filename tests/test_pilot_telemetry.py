"""Durable timing and bounded pre-roll telemetry checks without camera I/O."""

import csv
import io
import json

import numpy as np

from app.pipeline.pitch_tracking_v2 import PitchConfig, PitchStateMachineV2
from app.pipeline.recording.frame_timestamps import TIMESTAMP_COLUMNS, timestamp_row
from contracts import Frame
from contracts.timing import HOST_RECEIPT_TIMING, TimestampEvidence


def test_pre_roll_is_time_trimmed_and_reports_retained_image_bytes():
    tracker = PitchStateMachineV2(PitchConfig(pre_roll_ms=500.0))
    for i in range(61):
        frame = Frame("left", i, round(i * 1e9 / 60), np.zeros((8, 10), dtype=np.uint8), 10, 8, "GRAY8")
        tracker.buffer_frame("left", frame)
    stats = tracker.get_buffer_stats()["left"]
    assert stats["frame_count"] == 31
    assert stats["span_ms"] == 500.0
    assert stats["image_bytes"] == 31 * 80
    assert stats["frame_cap"] == 100


def test_timestamp_csv_preserves_receipt_provenance_without_claiming_exposure():
    frame = Frame("left", 7, 123, None, 10, 8, "GRAY8", capture_epoch="capture-1", timing=HOST_RECEIPT_TIMING)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(TIMESTAMP_COLUMNS)
    writer.writerow(timestamp_row(frame))
    buffer.seek(0)
    row = next(csv.DictReader(buffer))
    assert row["capture_epoch"] == "capture-1"
    restored = TimestampEvidence.from_payload(json.loads(row["timestamp_evidence"]))
    assert restored == HOST_RECEIPT_TIMING
    assert not restored.acquisition_verified

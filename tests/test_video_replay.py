"""Offline replay reuses real gates, association and pitch-state transitions."""

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from app.pipeline.initialization import PipelineInitializer
from app.pipeline.recording.frame_timestamps import TIMESTAMP_COLUMNS, timestamp_row
from app.services.analysis.video_replay import replay
from contracts import Detection, Frame
from contracts.fit_jobs import FitBatchRequest


@pytest.mark.parametrize("count,accepted", [(20, True), (6, False)])
def test_replay_conserves_frames_and_records_rejected_attempts(tmp_path, monkeypatch, count, accepted):
    session = tmp_path / "source"
    session.mkdir()
    calibration = tmp_path / "calibration.npz"
    intrinsics = np.asarray([[1200, 0, 640], [0, 1200, 360], [0, 0, 1]], dtype=float)
    np.savez(
        calibration,
        mtx_left=intrinsics,
        mtx_right=intrinsics,
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.asarray([-1.625 * 304.8, 0, 0]),
        img_size=np.asarray([1280, 720]),
        production_ready=True,
    )
    roi = tmp_path / "roi.json"
    polygon = [[0, 0], [1280, 0], [1280, 720], [0, 720]]
    roi.write_text(json.dumps({"lane": polygon, "plate": polygon}))
    transform = tmp_path / "transform.json"
    transform.write_text(
        json.dumps({"matrix_4x4": np.eye(4).tolist(), "rms_residual_ft": 0, "fixture_id": "synthetic"})
    )
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    for label in ("left", "right"):
        (session / f"session_{label}.avi").write_bytes(b"synthetic-decoder")
        with (session / f"session_{label}_timestamps.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(TIMESTAMP_COLUMNS)
            for index in range(count):
                frame = Frame(label, index, 1000000000 + index * 16666667, image, 1280, 720, "BGR8", "epoch")
                writer.writerow(timestamp_row(frame, index, "accepted"))

    class Decoder:
        def __init__(self, path):
            self.frames = iter([image] * count)

        def isOpened(self):
            return True

        def read(self):
            value = next(self.frames, None)
            return value is not None, value

        def release(self):
            pass

    class Detector:
        def detect(self, frame):
            time = frame.frame_index / 60
            z = 60 - 80 * time
            x, y = time, 6 - 16.087 * time**2
            u = 640 + 1200 * (x - (1.625 if frame.camera_id == "right" else 0)) / z
            v = 360 + 1200 * y / z
            return [Detection(frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns, u, v, 7, 1)]

    monkeypatch.setattr("app.services.analysis.video_replay.cv2.VideoCapture", Decoder)
    monkeypatch.setattr(
        PipelineInitializer,
        "build_detectors",
        lambda *args: {
            "left": Detector(),
            "right": Detector(),
        },
    )
    request = FitBatchRequest(
        (session,),
        tmp_path / "derived",
        workflow="videos",
        config_path=Path("configs/default.yaml"),
        calibration_path=calibration,
        roi_path=roi,
        field_transform_path=transform,
    )
    accounting = {}
    rows = list(replay(session, request, lambda: None, accounting))
    assert accounting["frames_processed"] == count * 2
    assert accounting["source_mapping"]["left"]["offered"] == count
    assert accounting["pairing_outcomes"] == {"PAIRED": count}
    assert bool(rows) == accepted
    if accepted:
        assert rows[0][1].observations
        assert len(rows[0][1].observations) <= count
    else:
        assert accounting["rejected_pitches"]

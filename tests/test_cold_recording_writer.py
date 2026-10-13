"""Recording cannot depend on a retired UI import to initialize video I/O."""

from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import cv2

from app.pipeline.recording.session_recording_io import open_video_writer


def test_automatic_selection_recovers_missing_ffmpeg_and_releases_every_attempt(tmp_path, monkeypatch):
    attempts = []

    def construct(*args):
        writer = Mock()
        writer.isOpened.return_value = len(args) == 5
        attempts.append((args, writer))
        return writer
    monkeypatch.setattr(cv2, "VideoWriter", construct)
    recovered = open_video_writer(tmp_path / "video.avi", 64, 48, 30)
    assert len(attempts) == 6 and all(args[1] == cv2.CAP_FFMPEG for args, _ in attempts[:5])
    assert recovered is attempts[-1][1]
    for _, failed in attempts[:-1]:
        failed.release.assert_called_once()
    recovered.release.assert_not_called()


def test_cold_writer_roundtrips_frames_without_importing_ui(tmp_path):
    code = """
import sys
from pathlib import Path
import cv2
import numpy as np
from app.pipeline.recording.session_recorder import SessionRecorder
from app.pipeline.recording.session_recording_io import open_video_writer
assert 'ui' not in sys.modules
paths = [Path(sys.argv[1]) / (camera + '.avi') for camera in ('left', 'right')]
writers = []
try:
    for path in paths:
        writers.append(open_video_writer(path, 1280, 720, 60))
    for index in range(12):
        for writer in writers:
            writer.write(np.full((720, 1280, 3), index * 10, np.uint8))
finally:
    for writer in writers:
        writer.release()
for path in paths:
    reader = cv2.VideoCapture(str(path))
    count = 0
    try:
        assert reader.isOpened()
        while True:
            ok, image = reader.read()
            if not ok:
                break
            assert image.shape == (720, 1280, 3)
            assert abs(float(image.mean()) - count * 10) < 5
            count += 1
    finally:
        reader.release()
    assert count == 12, count
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path(__file__).parents[1], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr

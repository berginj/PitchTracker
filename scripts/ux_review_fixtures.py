"""Synthetic local review artifacts and an in-memory decoder for UX evidence."""

import csv
import json
from pathlib import Path

import numpy as np

from app.review.video_reader import VideoInfo, VideoReader


def write_session(root: Path, name: str = "example-bullpen", *, state: str = "measured") -> Path:
    session = root / name
    session.mkdir(parents=True, exist_ok=True)
    (session / "manifest.json").write_text(json.dumps({"session_id": name, "t_end_utc": "2026-10-14T12:00:00Z"}), encoding="utf-8")
    for camera in ("left", "right"):
        if state != "missing-video":
            (session / f"session_{camera}.avi").write_bytes(b"synthetic fixture; not encoded video")
        with (session / f"session_{camera}_timestamps.csv").open("w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out)
            writer.writerow(["encoded_frame_index", "write_status", "t_capture_monotonic_ns", "capture_epoch"])
            for index in range(4):
                writer.writerow([index, "accepted", index * 1_000_000_000, "synthetic-epoch"])
    if state == "invalid-mapping":
        (session / "session_left_timestamps.csv").write_text("frame_index,t_capture_monotonic_ns\n0,0\n", encoding="utf-8")
    if state != "empty":
        for index in range(2):
            pitch = session / f"pitch_{index + 1:05d}"
            pitch.mkdir(exist_ok=True)
            manifest = {"pitch_id": pitch.name, "t_start_ns": (index + 1) * 1_000_000_000,
                        "t_end_ns": (index + 1) * 1_000_000_000 + 500_000_000,
                        "measured_speed_mph": 72.6 + index, "speed_source": "vision_fit",
                        "vision_speed": {"speed_mph": 72.6 + index, "source": "vision_fit", "reference": "first_observed"},
                        "measurement_status": "REJECTED" if state == "rejected" and index == 1 else "ESTIMATED",
                        "is_strike": index == 0, "strike_call_available": True,
                        "trajectory": {"plate_crossing_xyz_ft": [.1 + index, 2.6, 0]},
                        "observation_quality": {"rejection_reasons": ["Insufficient tracking evidence"] if state == "rejected" else []}}
            if state == "legacy":
                for key in ("measurement_status", "speed_source", "vision_speed"):
                    manifest.pop(key)
            (pitch / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return session


class SyntheticReviewReader(VideoReader):
    """No codecs, cameras or processing; frame color encodes its synthetic index."""

    def open_videos(self, left_video_path: Path, right_video_path: Path) -> tuple[VideoInfo, VideoInfo]:
        self.close()
        if not left_video_path.exists() or not right_video_path.exists():
            raise FileNotFoundError("Synthetic paired video fixture missing")
        self._left_info = VideoInfo(left_video_path, 320, 240, 30., 4, 133., "SYN")
        self._right_info = VideoInfo(right_video_path, 320, 240, 30., 4, 133., "SYN")
        self._total_frames = 4
        return self._left_info, self._right_info

    def is_opened(self) -> bool:
        return self._left_info is not None and self._right_info is not None

    def seek_to_frame(self, frame_index: int) -> bool:
        if not self.is_opened() or not 0 <= frame_index < self._total_frames:
            return False
        self._current_frame_index = frame_index
        return True

    def read_frames(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        if not self.is_opened():
            return None, None
        import cv2
        frame = np.full((240, 320, 3), (30 + self._current_frame_index * 30, 65, 35), dtype=np.uint8)
        cv2.putText(frame, f"SYNTHETIC FRAME {self._current_frame_index}", (18, 110), cv2.FONT_HERSHEY_SIMPLEX, .55, (240, 240, 240), 1)
        cv2.putText(frame, "No camera or athlete imagery", (18, 140), cv2.FONT_HERSHEY_SIMPLEX, .45, (240, 240, 240), 1)
        return frame.copy(), frame.copy()

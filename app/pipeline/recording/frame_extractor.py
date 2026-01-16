"""Extract key frames from pitch video for ML training."""

from pathlib import Path
from typing import Dict
import cv2
from contracts import Frame


class FrameExtractor:
    """Extracts and saves key frames during pitch recording."""

    def __init__(self, pitch_dir: Path, enabled: bool = True):
        """Initialize frame extractor.

        Args:
            pitch_dir: Directory to save frames
            enabled: Whether frame extraction is enabled
        """
        self._pitch_dir = pitch_dir
        self._enabled = enabled
        self._frames_dir = pitch_dir / "frames"

        if self._enabled:
            self._frames_dir.mkdir(exist_ok=True)
            (self._frames_dir / "left").mkdir(exist_ok=True)
            (self._frames_dir / "right").mkdir(exist_ok=True)

        # Track which frames have been saved
        self._saved_frames = {
            "pre_roll_first": False,
            "pre_roll_last": False,
            "first_detection": False,
            "release_point": False,
            "plate_crossing": False,
            "last_detection": False,
            "post_roll_last": False,
        }

        # Frame counters
        self._frame_count: Dict[str, int] = {"left": 0, "right": 0}

    def save_pre_roll_first(self, label: str, frame: Frame):
        """Save first pre-roll frame."""
        if self._enabled and not self._saved_frames["pre_roll_first"]:
            self._save_frame(label, frame, "pre_roll_00001")
            self._saved_frames["pre_roll_first"] = True

    def save_first_detection(self, label: str, frame: Frame):
        """Save first detection frame."""
        if self._enabled and not self._saved_frames["first_detection"]:
            self._save_frame(
                label, frame, f"pitch_{self._frame_count[label]:05d}_first"
            )
            self._saved_frames["first_detection"] = True

    def save_last_detection(self, label: str, frame: Frame):
        """Save last detection frame."""
        if self._enabled:
            # Always update (we don't know which is last until pitch ends)
            self._save_frame(label, frame, f"pitch_{self._frame_count[label]:05d}_last")
            self._saved_frames["last_detection"] = True

    def save_post_roll_last(self, label: str, frame: Frame):
        """Save last post-roll frame."""
        if self._enabled and not self._saved_frames["post_roll_last"]:
            self._save_frame(label, frame, "post_roll_last")
            self._saved_frames["post_roll_last"] = True

    def save_uniform(self, label: str, frame: Frame, interval: int = 5):
        """Save frame at uniform intervals.

        Args:
            label: Camera label
            frame: Frame to save
            interval: Save every Nth frame
        """
        if self._enabled:
            self._frame_count[label] += 1
            if self._frame_count[label] % interval == 0:
                self._save_frame(
                    label, frame, f"uniform_{self._frame_count[label]:05d}"
                )

    def _save_frame(self, label: str, frame: Frame, name: str):
        """Save frame as PNG.

        Args:
            label: Camera label
            frame: Frame to save
            name: File name (without extension)
        """
        if frame.image is None:
            return

        frame_path = self._frames_dir / label / f"{name}.png"
        cv2.imwrite(str(frame_path), frame.image)

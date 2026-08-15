"""Single-clip player used by the review comparison view."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6 import QtCore, QtWidgets

from app.review.video_reader import VideoReader
from ui.review.widgets.video_display_widget import VideoDisplayWidget

logger = logging.getLogger(__name__)


@dataclass
class PitchClip:
    """A bounded pitch clip and its display metadata."""

    pitch_id: str
    video_path: Path
    start_frame: int
    end_frame: int
    label: str
    speed_mph: Optional[float] = None
    spin_rpm: Optional[int] = None
    pitch_type: Optional[str] = None


class SyncVideoPlayer(QtWidgets.QWidget):
    """Display and seek one clip for synchronized comparison."""

    frame_changed = QtCore.Signal(int)

    def __init__(self, label: str = "Video", parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._label = label
        self._video_reader: Optional[VideoReader] = None
        self._current_frame: Optional[np.ndarray] = None
        self._clip: Optional[PitchClip] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self._header = QtWidgets.QLabel(self._label)
        self._header.setObjectName("comparison_header")
        self._header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._header.setAccessibleName(f"{self._label} label")
        self._display = VideoDisplayWidget()
        self._display.setMinimumSize(400, 300)
        self._display.setAccessibleName(f"{self._label} video")
        self._info_label = QtWidgets.QLabel("No clip loaded")
        self._info_label.setObjectName("comparison_info")
        self._info_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._frame_label = QtWidgets.QLabel("Frame: -/-")
        self._frame_label.setObjectName("comparison_frame")
        self._frame_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._header)
        layout.addWidget(self._display, 1)
        layout.addWidget(self._info_label)
        layout.addWidget(self._frame_label)

    def load_clip(self, clip: PitchClip) -> bool:
        """Open a clip and display its first frame."""
        self.close()
        self._clip = clip
        self._video_reader = VideoReader()
        try:
            self._video_reader.open_videos(clip.video_path, clip.video_path)
            self._video_reader.seek_to_frame(clip.start_frame)
            self._header.setText(clip.label)
            self._info_label.setText(self._clip_info(clip))
            self._read_and_display_frame()
            logger.info("Loaded clip: %s", clip.label)
            return True
        except (OSError, ValueError) as exc:
            logger.error("Failed to load clip %s: %s", clip.pitch_id, exc)
            self._release_reader()
            self._info_label.setText(f"Error: {exc}")
            return False

    @staticmethod
    def _clip_info(clip: PitchClip) -> str:
        parts = []
        if clip.speed_mph:
            parts.append(f"{clip.speed_mph:.1f} mph")
        if clip.pitch_type:
            parts.append(clip.pitch_type)
        if clip.spin_rpm:
            parts.append(f"{clip.spin_rpm} RPM")
        return " | ".join(parts) if parts else clip.pitch_id

    def seek_to_relative_frame(self, relative_index: int) -> None:
        if not self._clip or not self._video_reader:
            return
        absolute = max(
            self._clip.start_frame,
            min(self._clip.start_frame + relative_index, self._clip.end_frame),
        )
        self._video_reader.seek_to_frame(absolute)
        self._read_and_display_frame()

    def step_forward(self) -> bool:
        if not self._clip or not self._video_reader:
            return False
        if self._video_reader.current_frame_index >= self._clip.end_frame:
            return False
        self._video_reader.step_forward(1)
        self._read_and_display_frame()
        return True

    def step_backward(self) -> bool:
        if not self._clip or not self._video_reader:
            return False
        if self._video_reader.current_frame_index <= self._clip.start_frame:
            return False
        self._video_reader.step_backward(1)
        self._read_and_display_frame()
        return True

    def seek_to_start(self) -> None:
        if self._clip and self._video_reader:
            self._video_reader.seek_to_frame(self._clip.start_frame)
            self._read_and_display_frame()

    def seek_to_end(self) -> None:
        if self._clip and self._video_reader:
            self._video_reader.seek_to_frame(self._clip.end_frame)
            self._read_and_display_frame()

    def get_relative_frame(self) -> int:
        if not self._clip or not self._video_reader:
            return 0
        return self._video_reader.current_frame_index - self._clip.start_frame

    def get_clip_length(self) -> int:
        if not self._clip:
            return 0
        return self._clip.end_frame - self._clip.start_frame

    def _read_and_display_frame(self) -> None:
        if not self._video_reader:
            return
        left, _ = self._video_reader.read_frames()
        if left is None:
            return
        self._current_frame = left
        self._display.set_frame(left)
        relative = self.get_relative_frame()
        self._frame_label.setText(f"Frame: {relative + 1}/{self.get_clip_length()}")
        self.frame_changed.emit(relative)

    def _release_reader(self) -> None:
        if self._video_reader:
            self._video_reader.close()
            self._video_reader = None

    def close(self) -> None:
        """Release video resources and reset presentation state."""
        self._release_reader()
        self._clip = None
        self._current_frame = None
        self._display.clear()
        self._info_label.setText("No clip loaded")
        self._frame_label.setText("Frame: -/-")

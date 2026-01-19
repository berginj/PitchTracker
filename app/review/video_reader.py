"""Video reader for review and training mode playback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from contracts import Frame
from log_config.logger import get_logger

logger = get_logger(__name__)


class PlaybackState(Enum):
    """Video playback state."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass
class VideoInfo:
    """Video file metadata.

    Attributes:
        path: Path to video file
        width: Frame width in pixels
        height: Frame height in pixels
        fps: Frames per second
        total_frames: Total number of frames
        duration_ms: Video duration in milliseconds
        fourcc: Video codec FourCC code
    """
    path: Path
    width: int
    height: int
    fps: float
    total_frames: int
    duration_ms: float
    fourcc: str


class VideoReader:
    """Reads video files with playback control for review mode.

    Provides frame-by-frame reading, seeking, and playback state management
    for both left and right camera videos.

    Example:
        >>> reader = VideoReader()
        >>> reader.open_videos(left_path, right_path)
        >>> reader.seek_to_frame(100)
        >>> left_frame, right_frame = reader.read_frames()
        >>> print(f"Frame {reader.current_frame_index}/{reader.total_frames}")
    """

    def __init__(self):
        """Initialize video reader."""
        self._left_capture: Optional[cv2.VideoCapture] = None
        self._right_capture: Optional[cv2.VideoCapture] = None

        self._left_info: Optional[VideoInfo] = None
        self._right_info: Optional[VideoInfo] = None

        self._current_frame_index = 0
        self._total_frames = 0
        self._fps = 30.0

        self._playback_state = PlaybackState.STOPPED

        logger.debug("VideoReader initialized")

    def open_videos(self, left_video_path: Path, right_video_path: Path) -> tuple[VideoInfo, VideoInfo]:
        """Open left and right video files.

        Args:
            left_video_path: Path to left camera video
            right_video_path: Path to right camera video

        Returns:
            Tuple of (left_info, right_info) with video metadata

        Raises:
            FileNotFoundError: If video files don't exist
            ValueError: If videos cannot be opened or have mismatched properties
        """
        logger.info(f"Opening videos: left={left_video_path}, right={right_video_path}")

        # Close any existing videos
        self.close()

        # Validate paths
        if not left_video_path.exists():
            raise FileNotFoundError(f"Left video not found: {left_video_path}")
        if not right_video_path.exists():
            raise FileNotFoundError(f"Right video not found: {right_video_path}")

        # Open left video
        self._left_capture = cv2.VideoCapture(str(left_video_path))
        if not self._left_capture.isOpened():
            raise ValueError(f"Failed to open left video: {left_video_path}")

        # Open right video
        self._right_capture = cv2.VideoCapture(str(right_video_path))
        if not self._right_capture.isOpened():
            self._left_capture.release()
            raise ValueError(f"Failed to open right video: {right_video_path}")

        # Get video information
        self._left_info = self._get_video_info(self._left_capture, left_video_path)
        self._right_info = self._get_video_info(self._right_capture, right_video_path)

        # Verify videos have same frame count (approximately)
        if abs(self._left_info.total_frames - self._right_info.total_frames) > 5:
            logger.warning(
                f"Frame count mismatch: left={self._left_info.total_frames}, "
                f"right={self._right_info.total_frames}"
            )

        # Use minimum frame count for safety
        self._total_frames = min(self._left_info.total_frames, self._right_info.total_frames)
        self._fps = self._left_info.fps
        self._current_frame_index = 0
        self._playback_state = PlaybackState.PAUSED

        logger.info(
            f"Videos opened: {self._total_frames} frames @ {self._fps:.1f} fps, "
            f"{self._left_info.width}x{self._left_info.height}"
        )

        return self._left_info, self._right_info

    @staticmethod
    def _get_video_info(capture: cv2.VideoCapture, path: Path) -> VideoInfo:
        """Extract metadata from video capture.

        Args:
            capture: OpenCV VideoCapture object
            path: Path to video file

        Returns:
            VideoInfo object with video metadata
        """
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fourcc_int = int(capture.get(cv2.CAP_PROP_FOURCC))
        fourcc = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)])

        duration_ms = (total_frames / fps) * 1000.0 if fps > 0 else 0.0

        return VideoInfo(
            path=path,
            width=width,
            height=height,
            fps=fps,
            total_frames=total_frames,
            duration_ms=duration_ms,
            fourcc=fourcc,
        )

    def read_frames(self) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Read current frame from both videos.

        Returns:
            Tuple of (left_frame, right_frame) as numpy arrays.
            Returns (None, None) if at end of video or not opened.

        Note:
            Does not advance to next frame - use seek_to_frame() or step_forward()
        """
        if not self.is_opened():
            return None, None

        if self._current_frame_index >= self._total_frames:
            logger.debug("At end of video")
            return None, None

        # Read from both captures
        left_ok, left_frame = self._left_capture.read()
        right_ok, right_frame = self._right_capture.read()

        if not left_ok or not right_ok:
            logger.warning(f"Failed to read frame {self._current_frame_index}")
            return None, None

        return left_frame, right_frame

    def seek_to_frame(self, frame_index: int) -> bool:
        """Seek to specific frame index.

        Args:
            frame_index: Frame index to seek to (0-based)

        Returns:
            True if seek successful, False otherwise
        """
        if not self.is_opened():
            logger.warning("Cannot seek: videos not opened")
            return False

        # Clamp to valid range
        frame_index = max(0, min(frame_index, self._total_frames - 1))

        if frame_index == self._current_frame_index:
            return True  # Already at target frame

        logger.debug(f"Seeking from frame {self._current_frame_index} to {frame_index}")

        # Seek both captures
        left_ok = self._left_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        right_ok = self._right_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

        if not left_ok or not right_ok:
            logger.error(f"Failed to seek to frame {frame_index}")
            return False

        self._current_frame_index = frame_index
        return True

    def seek_to_time(self, time_ms: float) -> bool:
        """Seek to specific timestamp.

        Args:
            time_ms: Time in milliseconds

        Returns:
            True if seek successful, False otherwise
        """
        if not self.is_opened():
            return False

        # Convert time to frame index
        frame_index = int((time_ms / 1000.0) * self._fps)
        return self.seek_to_frame(frame_index)

    def step_forward(self, num_frames: int = 1) -> bool:
        """Step forward by specified number of frames.

        Args:
            num_frames: Number of frames to advance

        Returns:
            True if step successful, False if at end of video
        """
        return self.seek_to_frame(self._current_frame_index + num_frames)

    def step_backward(self, num_frames: int = 1) -> bool:
        """Step backward by specified number of frames.

        Args:
            num_frames: Number of frames to go back

        Returns:
            True if step successful, False if at beginning
        """
        return self.seek_to_frame(self._current_frame_index - num_frames)

    def seek_to_start(self) -> bool:
        """Seek to start of video.

        Returns:
            True if seek successful
        """
        return self.seek_to_frame(0)

    def seek_to_end(self) -> bool:
        """Seek to end of video.

        Returns:
            True if seek successful
        """
        return self.seek_to_frame(self._total_frames - 1)

    def is_opened(self) -> bool:
        """Check if videos are opened.

        Returns:
            True if both videos are opened, False otherwise
        """
        return (
            self._left_capture is not None
            and self._right_capture is not None
            and self._left_capture.isOpened()
            and self._right_capture.isOpened()
        )

    def close(self) -> None:
        """Close video files and release resources."""
        if self._left_capture is not None:
            self._left_capture.release()
            self._left_capture = None

        if self._right_capture is not None:
            self._right_capture.release()
            self._right_capture = None

        self._left_info = None
        self._right_info = None
        self._current_frame_index = 0
        self._total_frames = 0
        self._playback_state = PlaybackState.STOPPED

        logger.debug("Videos closed")

    @property
    def current_frame_index(self) -> int:
        """Get current frame index (0-based)."""
        return self._current_frame_index

    @property
    def total_frames(self) -> int:
        """Get total number of frames."""
        return self._total_frames

    @property
    def fps(self) -> float:
        """Get video frame rate."""
        return self._fps

    @property
    def current_time_ms(self) -> float:
        """Get current playback time in milliseconds."""
        if self._fps <= 0:
            return 0.0
        return (self._current_frame_index / self._fps) * 1000.0

    @property
    def duration_ms(self) -> float:
        """Get total video duration in milliseconds."""
        if self._left_info:
            return self._left_info.duration_ms
        return 0.0

    @property
    def playback_state(self) -> PlaybackState:
        """Get current playback state."""
        return self._playback_state

    @playback_state.setter
    def playback_state(self, state: PlaybackState) -> None:
        """Set playback state."""
        self._playback_state = state

    @property
    def left_info(self) -> Optional[VideoInfo]:
        """Get left video information."""
        return self._left_info

    @property
    def right_info(self) -> Optional[VideoInfo]:
        """Get right video information."""
        return self._right_info

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close videos."""
        self.close()

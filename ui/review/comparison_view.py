"""Side-by-side pitch comparison view for review mode.

Provides:
- Synchronized playback of two pitches
- Frame-by-frame comparison
- Overlay toggle for trajectory visualization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.review.video_reader import VideoReader
from ui.review.widgets.video_display_widget import VideoDisplayWidget

logger = logging.getLogger(__name__)


@dataclass
class PitchClip:
    """Represents a pitch video clip for comparison."""

    pitch_id: str
    video_path: Path
    start_frame: int
    end_frame: int
    label: str  # Display label (e.g., "Fastball #12" or "Best Pitch")

    # Metrics for display
    speed_mph: Optional[float] = None
    spin_rpm: Optional[int] = None
    pitch_type: Optional[str] = None


class SyncVideoPlayer(QtWidgets.QWidget):
    """Video player widget with synchronized playback support.

    Displays a single video with frame display and info label.
    """

    frame_changed = QtCore.Signal(int)  # current frame index

    def __init__(
        self,
        label: str = "Video",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Initialize sync video player.

        Args:
            label: Display label for the player
            parent: Parent widget
        """
        super().__init__(parent)
        self._label = label
        self._video_reader: Optional[VideoReader] = None
        self._current_frame: Optional[np.ndarray] = None
        self._clip: Optional[PitchClip] = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the player UI."""
        # Header label
        self._header = QtWidgets.QLabel(self._label)
        self._header.setObjectName("comparison_header")
        self._header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Video display
        self._display = VideoDisplayWidget()
        self._display.setMinimumSize(400, 300)

        # Info panel
        self._info_label = QtWidgets.QLabel("No clip loaded")
        self._info_label.setObjectName("comparison_info")
        self._info_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Frame counter
        self._frame_label = QtWidgets.QLabel("Frame: -/-")
        self._frame_label.setObjectName("comparison_frame")
        self._frame_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._header)
        layout.addWidget(self._display, 1)
        layout.addWidget(self._info_label)
        layout.addWidget(self._frame_label)

        self.setLayout(layout)

    def load_clip(self, clip: PitchClip) -> bool:
        """Load a pitch clip for playback.

        Args:
            clip: PitchClip to load

        Returns:
            True if loaded successfully
        """
        self._clip = clip

        # Create video reader
        self._video_reader = VideoReader()

        try:
            # Open video (use same path for left/right for single video)
            self._video_reader.open_videos(clip.video_path, clip.video_path)

            # Seek to start frame
            self._video_reader.seek_to_frame(clip.start_frame)

            # Update header
            self._header.setText(clip.label)

            # Update info
            info_parts = []
            if clip.speed_mph:
                info_parts.append(f"{clip.speed_mph:.1f} mph")
            if clip.pitch_type:
                info_parts.append(clip.pitch_type)
            if clip.spin_rpm:
                info_parts.append(f"{clip.spin_rpm} RPM")

            self._info_label.setText(" | ".join(info_parts) if info_parts else clip.pitch_id)

            # Read first frame
            self._read_and_display_frame()

            logger.info(f"Loaded clip: {clip.label}")
            return True

        except Exception as e:
            logger.error(f"Failed to load clip {clip.pitch_id}: {e}")
            self._info_label.setText(f"Error: {e}")
            return False

    def seek_to_relative_frame(self, relative_index: int) -> None:
        """Seek to frame relative to clip start.

        Args:
            relative_index: Frame index relative to clip start
        """
        if not self._clip or not self._video_reader:
            return

        absolute_frame = self._clip.start_frame + relative_index
        absolute_frame = max(
            self._clip.start_frame,
            min(absolute_frame, self._clip.end_frame),
        )

        self._video_reader.seek_to_frame(absolute_frame)
        self._read_and_display_frame()

    def step_forward(self) -> bool:
        """Step forward one frame.

        Returns:
            True if step successful
        """
        if not self._clip or not self._video_reader:
            return False

        current = self._video_reader.current_frame_index
        if current >= self._clip.end_frame:
            return False

        self._video_reader.step_forward(1)
        self._read_and_display_frame()
        return True

    def step_backward(self) -> bool:
        """Step backward one frame.

        Returns:
            True if step successful
        """
        if not self._clip or not self._video_reader:
            return False

        current = self._video_reader.current_frame_index
        if current <= self._clip.start_frame:
            return False

        self._video_reader.step_backward(1)
        self._read_and_display_frame()
        return True

    def seek_to_start(self) -> None:
        """Seek to clip start."""
        if self._clip and self._video_reader:
            self._video_reader.seek_to_frame(self._clip.start_frame)
            self._read_and_display_frame()

    def seek_to_end(self) -> None:
        """Seek to clip end."""
        if self._clip and self._video_reader:
            self._video_reader.seek_to_frame(self._clip.end_frame)
            self._read_and_display_frame()

    def get_relative_frame(self) -> int:
        """Get current frame index relative to clip start.

        Returns:
            Relative frame index
        """
        if not self._clip or not self._video_reader:
            return 0

        return self._video_reader.current_frame_index - self._clip.start_frame

    def get_clip_length(self) -> int:
        """Get clip length in frames.

        Returns:
            Number of frames in clip
        """
        if not self._clip:
            return 0

        return self._clip.end_frame - self._clip.start_frame

    def _read_and_display_frame(self) -> None:
        """Read current frame and update display."""
        if not self._video_reader:
            return

        left, _ = self._video_reader.read_frames()

        if left is not None:
            self._current_frame = left
            self._display.set_frame(left)

            # Update frame counter
            relative = self.get_relative_frame()
            total = self.get_clip_length()
            self._frame_label.setText(f"Frame: {relative + 1}/{total}")

            self.frame_changed.emit(relative)

    def close(self) -> None:
        """Close video reader and release resources."""
        if self._video_reader:
            self._video_reader.close()
            self._video_reader = None

        self._clip = None
        self._current_frame = None
        self._display.clear()
        self._info_label.setText("No clip loaded")
        self._frame_label.setText("Frame: -/-")


class ComparisonView(QtWidgets.QWidget):
    """Side-by-side video comparison of two pitches.

    Features:
    - Synchronized playback
    - Frame-by-frame stepping
    - Toggle sync mode
    - Overlay support (future)
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize comparison view.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._sync_enabled = True

        self._build_ui()
        self._apply_style()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Build the comparison UI."""
        # Header
        header = QtWidgets.QLabel("PITCH COMPARISON")
        header.setObjectName("comparison_title")
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Video players
        self._player_a = SyncVideoPlayer("Pitch A")
        self._player_b = SyncVideoPlayer("Pitch B")

        players_layout = QtWidgets.QHBoxLayout()
        players_layout.setSpacing(8)
        players_layout.addWidget(self._player_a, 1)
        players_layout.addWidget(self._player_b, 1)

        # Controls
        controls = self._build_controls()

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(header)
        layout.addLayout(players_layout, 1)
        layout.addWidget(controls)

        self.setLayout(layout)

    def _build_controls(self) -> QtWidgets.QWidget:
        """Build playback control buttons."""
        widget = QtWidgets.QWidget()
        widget.setObjectName("comparison_controls")

        # Sync toggle
        self._sync_btn = QtWidgets.QPushButton("Sync: ON")
        self._sync_btn.setCheckable(True)
        self._sync_btn.setChecked(True)
        self._sync_btn.clicked.connect(self._on_sync_toggled)
        self._sync_btn.setMinimumHeight(32)

        # Navigation buttons
        self._start_btn = QtWidgets.QPushButton("Start")
        self._start_btn.clicked.connect(self._seek_to_start)
        self._start_btn.setMinimumHeight(32)

        self._back_btn = QtWidgets.QPushButton("Step Back")
        self._back_btn.clicked.connect(self._step_backward)
        self._back_btn.setMinimumHeight(32)

        self._forward_btn = QtWidgets.QPushButton("Step Forward")
        self._forward_btn.clicked.connect(self._step_forward)
        self._forward_btn.setMinimumHeight(32)

        self._end_btn = QtWidgets.QPushButton("End")
        self._end_btn.clicked.connect(self._seek_to_end)
        self._end_btn.setMinimumHeight(32)

        # Timeline slider
        self._timeline = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._timeline.setMinimum(0)
        self._timeline.setMaximum(100)
        self._timeline.valueChanged.connect(self._on_timeline_changed)

        # Layout
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self._sync_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self._start_btn)
        btn_layout.addWidget(self._back_btn)
        btn_layout.addWidget(self._forward_btn)
        btn_layout.addWidget(self._end_btn)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 8, 0, 0)
        layout.addWidget(self._timeline)
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def _apply_style(self) -> None:
        """Apply glass-themed styling."""
        try:
            from ui.themes import get_style_manager

            theme = get_style_manager().theme

            self.setStyleSheet(f"""
                ComparisonView {{
                    background-color: {theme.background_dark};
                }}
                #comparison_title {{
                    font-size: 16px;
                    font-weight: bold;
                    color: {theme.accent_primary};
                    padding: 8px;
                }}
                #comparison_header {{
                    font-size: 14px;
                    font-weight: bold;
                    color: {theme.text_primary};
                    background-color: {theme.surface_glass};
                    border-radius: 4px;
                    padding: 4px;
                }}
                #comparison_info {{
                    font-size: 12px;
                    color: {theme.text_secondary};
                    padding: 4px;
                }}
                #comparison_frame {{
                    font-size: 11px;
                    color: {theme.text_muted};
                }}
                #comparison_controls {{
                    background-color: {theme.surface_glass};
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                    padding: 8px;
                }}
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {theme.border_glass};
                    border-radius: 4px;
                    padding: 6px 12px;
                    color: {theme.text_secondary};
                }}
                QPushButton:hover {{
                    background-color: {theme.surface_glass_hover};
                    color: {theme.text_primary};
                }}
                QPushButton:checked {{
                    background-color: {theme.accent_primary_dim};
                    border-color: {theme.accent_primary};
                    color: {theme.accent_primary};
                }}
                QSlider::groove:horizontal {{
                    height: 6px;
                    background: {theme.surface_glass};
                    border-radius: 3px;
                }}
                QSlider::handle:horizontal {{
                    width: 14px;
                    margin: -4px 0;
                    background: {theme.accent_primary};
                    border-radius: 7px;
                }}
            """)

        except ImportError:
            pass

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._player_a.frame_changed.connect(self._on_player_a_frame_changed)

    def load_pitches(
        self,
        pitch_a: PitchClip,
        pitch_b: PitchClip,
    ) -> bool:
        """Load two pitches for comparison.

        Args:
            pitch_a: First pitch clip
            pitch_b: Second pitch clip

        Returns:
            True if both loaded successfully
        """
        success_a = self._player_a.load_clip(pitch_a)
        success_b = self._player_b.load_clip(pitch_b)

        if success_a and success_b:
            # Update timeline to match longest clip
            max_frames = max(
                self._player_a.get_clip_length(),
                self._player_b.get_clip_length(),
            )
            self._timeline.setMaximum(max(1, max_frames - 1))
            self._timeline.setValue(0)

            logger.info(f"Loaded comparison: {pitch_a.label} vs {pitch_b.label}")

        return success_a and success_b

    def toggle_sync(self, synced: bool) -> None:
        """Toggle synchronized playback mode.

        Args:
            synced: True to enable sync mode
        """
        self._sync_enabled = synced
        self._sync_btn.setChecked(synced)
        self._sync_btn.setText(f"Sync: {'ON' if synced else 'OFF'}")

    def _on_sync_toggled(self, checked: bool) -> None:
        """Handle sync button toggle."""
        self.toggle_sync(checked)

    def _on_timeline_changed(self, value: int) -> None:
        """Handle timeline slider change."""
        self._player_a.seek_to_relative_frame(value)

        if self._sync_enabled:
            self._player_b.seek_to_relative_frame(value)

    def _on_player_a_frame_changed(self, frame: int) -> None:
        """Handle player A frame change for sync."""
        # Block timeline signals to avoid feedback loop
        self._timeline.blockSignals(True)
        self._timeline.setValue(frame)
        self._timeline.blockSignals(False)

        if self._sync_enabled:
            self._player_b.seek_to_relative_frame(frame)

    def _step_forward(self) -> None:
        """Step both players forward."""
        self._player_a.step_forward()

        if self._sync_enabled:
            self._player_b.step_forward()

    def _step_backward(self) -> None:
        """Step both players backward."""
        self._player_a.step_backward()

        if self._sync_enabled:
            self._player_b.step_backward()

    def _seek_to_start(self) -> None:
        """Seek both players to start."""
        self._player_a.seek_to_start()

        if self._sync_enabled:
            self._player_b.seek_to_start()

        self._timeline.setValue(0)

    def _seek_to_end(self) -> None:
        """Seek both players to end."""
        self._player_a.seek_to_end()

        if self._sync_enabled:
            self._player_b.seek_to_end()

        self._timeline.setValue(self._timeline.maximum())

    def close(self) -> None:
        """Close players and release resources."""
        self._player_a.close()
        self._player_b.close()


class ComparisonDialog(QtWidgets.QDialog):
    """Dialog wrapper for pitch comparison view."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize comparison dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Pitch Comparison")
        self.setMinimumSize(1000, 600)

        self._comparison_view = ComparisonView()

        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._comparison_view, 1)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def load_pitches(
        self,
        pitch_a: PitchClip,
        pitch_b: PitchClip,
    ) -> bool:
        """Load pitches for comparison.

        Args:
            pitch_a: First pitch
            pitch_b: Second pitch

        Returns:
            True if both loaded
        """
        return self._comparison_view.load_pitches(pitch_a, pitch_b)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle close event."""
        self._comparison_view.close()
        super().closeEvent(event)


__all__ = [
    "PitchClip",
    "SyncVideoPlayer",
    "ComparisonView",
    "ComparisonDialog",
]

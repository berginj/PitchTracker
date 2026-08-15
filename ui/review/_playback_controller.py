"""Playback and frame navigation controller for ReviewWindow."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6 import QtCore, QtWidgets

from app.review import ReviewService

logger = logging.getLogger(__name__)


class PlaybackController:
    """Manages playback timer, speed, looping, and frame stepping."""

    def __init__(
        self,
        service: ReviewService,
        *,
        status_bar: QtWidgets.QStatusBar,
        on_frame_changed: Callable[[], None],
        get_timeline_updater: Callable[[int], None],
    ) -> None:
        self._service = service
        self._status_bar = status_bar
        self._on_frame_changed = on_frame_changed
        self._set_timeline_frame = get_timeline_updater

        self._playback_timer = QtCore.QTimer()
        self._playback_timer.timeout.connect(self._on_playback_tick)
        self._is_playing = False
        self._loop_enabled = False

        # Reference to controls widget set externally
        self._controls_widget = None

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def loop_enabled(self) -> bool:
        return self._loop_enabled

    def set_controls_widget(self, controls) -> None:
        """Set the PlaybackControls widget for state sync."""
        self._controls_widget = controls

    def toggle_playback(self) -> None:
        """Toggle between play and pause."""
        if not self._service.session:
            return

        if self._is_playing:
            self._playback_timer.stop()
            self._is_playing = False
            if self._controls_widget:
                self._controls_widget.set_playing(False)
            self._status_bar.showMessage("Paused")
            logger.debug("Playback paused")
        else:
            fps = self._service.video_reader.fps
            speed = self._service.playback_speed
            interval_ms = int(1000.0 / (fps * speed))

            self._playback_timer.start(interval_ms)
            self._is_playing = True
            if self._controls_widget:
                self._controls_widget.set_playing(True)
            self._status_bar.showMessage(f"Playing (Speed: {speed:.1f}x)")
            logger.debug(f"Playback started at {speed:.1f}x speed")

    def stop_playback(self) -> None:
        """Stop playback unconditionally."""
        if self._is_playing:
            self._playback_timer.stop()
            self._is_playing = False
            if self._controls_widget:
                self._controls_widget.set_playing(False)

    def step_forward(self) -> None:
        """Step forward one frame."""
        if not self._service.session:
            return
        if self._service.step_forward():
            self._on_frame_changed()
            self._set_timeline_frame(self._service.current_frame_index)
            self._status_bar.showMessage(
                f"Frame {self._service.current_frame_index + 1}/{self._service.total_frames}"
            )

    def step_backward(self) -> None:
        """Step backward one frame."""
        if not self._service.session:
            return
        if self._service.step_backward():
            self._on_frame_changed()
            self._set_timeline_frame(self._service.current_frame_index)
            self._status_bar.showMessage(
                f"Frame {self._service.current_frame_index + 1}/{self._service.total_frames}"
            )

    def seek_to_start(self) -> None:
        """Seek to first frame."""
        if not self._service.session:
            return
        self._service.seek_to_start()
        self._on_frame_changed()
        self._set_timeline_frame(0)
        self._status_bar.showMessage("Seeked to start")

    def seek_to_end(self) -> None:
        """Seek to last frame."""
        if not self._service.session:
            return
        self._service.seek_to_end()
        self._on_frame_changed()
        self._set_timeline_frame(self._service.current_frame_index)
        self._status_bar.showMessage("Seeked to end")

    def seek_to_frame(self, frame_index: int) -> None:
        """Seek to specific frame."""
        if not self._service.session:
            return
        self._service.seek_to_frame(frame_index)
        self._on_frame_changed()
        self._status_bar.showMessage(
            f"Seeked to frame {frame_index + 1}/{self._service.total_frames}"
        )

    def on_speed_changed(self, speed: float) -> None:
        """Handle playback speed change."""
        self._service.playback_speed = speed
        if self._is_playing:
            self._playback_timer.stop()
            fps = self._service.video_reader.fps
            interval_ms = int(1000.0 / (fps * speed))
            self._playback_timer.start(interval_ms)
        self._status_bar.showMessage(f"Playback speed: {speed:.1f}x")

    def on_loop_toggled(self, enabled: bool) -> None:
        """Handle loop toggle."""
        self._loop_enabled = enabled
        mode_str = "ON" if enabled else "OFF"
        self._status_bar.showMessage(f"Loop mode: {mode_str}")
        logger.info(f"Loop mode: {mode_str}")

    def seek_to_pitch(self, pitch_index: int) -> None:
        """Seek to specific pitch start frame."""
        if not self._service.session:
            return
        self._service.seek_to_pitch(pitch_index)
        self._on_frame_changed()
        self._set_timeline_frame(self._service.current_frame_index)

    def prev_pitch(self) -> Optional[int]:
        """Navigate to previous pitch."""
        if not self._service.session:
            return
        pitches = self._service.session.pitches
        if not pitches:
            return

        current_frame = self._service.current_frame_index
        current_pitch_idx = -1
        for i, pitch in enumerate(pitches):
            pitch_start_frame = self._service.get_frame_for_timestamp(pitch.t_start_ns)
            if pitch_start_frame is not None and pitch_start_frame <= current_frame:
                current_pitch_idx = i

        target_idx = max(0, current_pitch_idx - 1)
        return target_idx if target_idx < len(pitches) else None

    def next_pitch(self) -> Optional[int]:
        """Navigate to next pitch. Returns target index or None."""
        if not self._service.session:
            return None
        pitches = self._service.session.pitches
        if not pitches:
            return None

        current_frame = self._service.current_frame_index
        current_pitch_idx = -1
        for i, pitch in enumerate(pitches):
            pitch_start_frame = self._service.get_frame_for_timestamp(pitch.t_start_ns)
            if pitch_start_frame is not None and pitch_start_frame <= current_frame:
                current_pitch_idx = i

        target_idx = min(len(pitches) - 1, current_pitch_idx + 1)
        return target_idx if target_idx >= 0 else None

    def teardown(self) -> None:
        """Stop timer for cleanup."""
        if self._is_playing:
            self._playback_timer.stop()
            self._is_playing = False

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_playback_tick(self) -> None:
        """Advance one frame on timer tick."""
        if not self._service.step_forward():
            if self._loop_enabled:
                self._service.seek_to_start()
                self._on_frame_changed()
                self._set_timeline_frame(0)
                return
            else:
                self.toggle_playback()
                self._status_bar.showMessage("Reached end of video")
                return

        self._on_frame_changed()
        self._set_timeline_frame(self._service.current_frame_index)

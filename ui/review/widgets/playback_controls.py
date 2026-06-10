"""Playback controls widget for review mode."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets
from ui.themes import get_style_manager


class PlaybackControls(QtWidgets.QWidget):
    """Widget with playback control buttons.

    Provides controls for:
    - Play/Pause
    - Step forward/backward
    - Seek to start/end
    - Playback speed adjustment (0.1x to 2.0x)
    - Loop mode for continuous playback
    - Previous/Next pitch navigation

    Signals:
        play_pause_clicked: Emitted when play/pause button clicked
        step_forward_clicked: Emitted when step forward clicked
        step_backward_clicked: Emitted when step backward clicked
        seek_start_clicked: Emitted when seek to start clicked
        seek_end_clicked: Emitted when seek to end clicked
        speed_changed: Emitted when playback speed changes (float)
        loop_toggled: Emitted when loop mode is toggled (bool)
        prev_pitch_clicked: Emitted when previous pitch button clicked
        next_pitch_clicked: Emitted when next pitch button clicked
    """

    # Signals
    play_pause_clicked = QtCore.Signal()
    step_forward_clicked = QtCore.Signal()
    step_backward_clicked = QtCore.Signal()
    seek_start_clicked = QtCore.Signal()
    seek_end_clicked = QtCore.Signal()
    speed_changed = QtCore.Signal(float)
    loop_toggled = QtCore.Signal(bool)
    prev_pitch_clicked = QtCore.Signal()
    next_pitch_clicked = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize playback controls.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._is_playing = False
        self._is_looping = False
        self._build_ui()

    def _build_ui(self) -> None:
        """Build control buttons layout."""
        # Seek to start button
        self._seek_start_btn = QtWidgets.QPushButton("Start")
        self._seek_start_btn.setToolTip("Seek to start (Home)")
        self._seek_start_btn.clicked.connect(self.seek_start_clicked.emit)
        self._seek_start_btn.setMinimumHeight(self._style_manager.theme.button_height_md)
        self._seek_start_btn.setAccessibleName("Seek to Start")
        self._style_manager.style_button(self._seek_start_btn, "default")

        # Step backward button
        self._step_back_btn = QtWidgets.QPushButton("Step Back")
        self._step_back_btn.setToolTip("Step backward one frame (Left Arrow)")
        self._step_back_btn.clicked.connect(self.step_backward_clicked.emit)
        self._step_back_btn.setMinimumHeight(self._style_manager.theme.button_height_md)
        self._step_back_btn.setAccessibleName("Step Backward")
        self._style_manager.style_button(self._step_back_btn, "default")

        # Play/Pause button
        self._play_pause_btn = QtWidgets.QPushButton("Play")
        self._play_pause_btn.setToolTip("Play/Pause (Space)")
        self._play_pause_btn.clicked.connect(self.play_pause_clicked.emit)
        self._play_pause_btn.setMinimumHeight(self._style_manager.theme.button_height_md)
        self._play_pause_btn.setAccessibleName("Play or Pause")
        self._style_manager.style_button(self._play_pause_btn, "success")

        # Step forward button
        self._step_forward_btn = QtWidgets.QPushButton("Step Forward")
        self._step_forward_btn.setToolTip("Step forward one frame (Right Arrow)")
        self._step_forward_btn.clicked.connect(self.step_forward_clicked.emit)
        self._step_forward_btn.setMinimumHeight(self._style_manager.theme.button_height_md)
        self._step_forward_btn.setAccessibleName("Step Forward")
        self._style_manager.style_button(self._step_forward_btn, "default")

        # Seek to end button
        self._seek_end_btn = QtWidgets.QPushButton("End")
        self._seek_end_btn.setToolTip("Seek to end (End)")
        self._seek_end_btn.clicked.connect(self.seek_end_clicked.emit)
        self._seek_end_btn.setMinimumHeight(self._style_manager.theme.button_height_md)
        self._seek_end_btn.setAccessibleName("Seek to End")
        self._style_manager.style_button(self._seek_end_btn, "default")

        # Speed control
        speed_label = QtWidgets.QLabel("Speed:")
        self._style_manager.style_label(speed_label, "eyebrow")
        self._speed_combo = QtWidgets.QComboBox()
        self._speed_combo.setAccessibleName("Playback Speed")
        self._speed_combo.addItem("0.1x", 0.1)
        self._speed_combo.addItem("0.25x", 0.25)
        self._speed_combo.addItem("0.5x", 0.5)
        self._speed_combo.addItem("1.0x", 1.0)
        self._speed_combo.addItem("1.5x", 1.5)
        self._speed_combo.addItem("2.0x", 2.0)
        self._speed_combo.setCurrentIndex(3)  # Default to 1.0x
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        self._style_manager.style_input(self._speed_combo)

        # Loop mode toggle
        self._loop_btn = QtWidgets.QPushButton("Loop")
        self._loop_btn.setAccessibleName("Toggle Loop")
        self._loop_btn.setToolTip("Toggle loop mode (L)")
        self._loop_btn.setCheckable(True)
        self._loop_btn.clicked.connect(self._on_loop_toggled)
        self._loop_btn.setMinimumHeight(self._style_manager.theme.button_height_sm)
        self._style_manager.style_button(self._loop_btn, "ghost")

        # Pitch navigation
        self._prev_pitch_btn = QtWidgets.QPushButton("Prev Pitch")
        self._prev_pitch_btn.setToolTip("Jump to previous pitch (PgUp)")
        self._prev_pitch_btn.clicked.connect(self.prev_pitch_clicked.emit)
        self._prev_pitch_btn.setMinimumHeight(self._style_manager.theme.button_height_sm)
        self._prev_pitch_btn.setAccessibleName("Previous Pitch")
        self._style_manager.style_button(self._prev_pitch_btn, "default")

        self._next_pitch_btn = QtWidgets.QPushButton("Next Pitch")
        self._next_pitch_btn.setToolTip("Jump to next pitch (PgDown)")
        self._next_pitch_btn.clicked.connect(self.next_pitch_clicked.emit)
        self._next_pitch_btn.setMinimumHeight(self._style_manager.theme.button_height_sm)
        self._next_pitch_btn.setAccessibleName("Next Pitch")
        self._style_manager.style_button(self._next_pitch_btn, "default")

        # Top row: Frame controls
        frame_layout = QtWidgets.QHBoxLayout()
        frame_layout.addWidget(self._seek_start_btn)
        frame_layout.addWidget(self._step_back_btn)
        frame_layout.addWidget(self._play_pause_btn, 1)  # Play button takes more space
        frame_layout.addWidget(self._step_forward_btn)
        frame_layout.addWidget(self._seek_end_btn)

        # Bottom row: Speed, loop, and pitch navigation
        options_layout = QtWidgets.QHBoxLayout()
        options_layout.addWidget(self._prev_pitch_btn)
        options_layout.addWidget(self._next_pitch_btn)
        options_layout.addStretch()
        options_layout.addWidget(self._loop_btn)
        options_layout.addWidget(speed_label)
        options_layout.addWidget(self._speed_combo)

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addLayout(frame_layout)
        layout.addLayout(options_layout)

        self.setLayout(layout)
        self.setProperty("surface", "card")
        self._style_manager.polish(self)

    def set_playing(self, is_playing: bool) -> None:
        """Update button state for playing/paused.

        Args:
            is_playing: True if video is playing, False if paused
        """
        self._is_playing = is_playing

        if is_playing:
            self._play_pause_btn.setText("Pause")
            self._style_manager.style_button(self._play_pause_btn, "primary")
        else:
            self._play_pause_btn.setText("Play")
            self._style_manager.style_button(self._play_pause_btn, "success")

    def _on_speed_changed(self, index: int) -> None:
        """Handle speed combo box change.

        Args:
            index: Selected index
        """
        speed = self._speed_combo.itemData(index)
        self.speed_changed.emit(speed)

    def _on_loop_toggled(self, checked: bool) -> None:
        """Handle loop mode toggle.

        Args:
            checked: True if loop mode is enabled
        """
        self._is_looping = checked
        if checked:
            self._style_manager.style_button(self._loop_btn, "primary")
        else:
            self._style_manager.style_button(self._loop_btn, "ghost")
        self.loop_toggled.emit(checked)

    def is_looping(self) -> bool:
        """Check if loop mode is enabled.

        Returns:
            True if loop mode is on
        """
        return self._is_looping

    def set_looping(self, looping: bool) -> None:
        """Set loop mode state.

        Args:
            looping: True to enable loop mode
        """
        self._loop_btn.setChecked(looping)
        self._on_loop_toggled(looping)

    def set_speed(self, speed: float) -> None:
        """Set playback speed.

        Args:
            speed: Speed multiplier (0.1-2.0)
        """
        for i in range(self._speed_combo.count()):
            if self._speed_combo.itemData(i) == speed:
                self._speed_combo.setCurrentIndex(i)
                return

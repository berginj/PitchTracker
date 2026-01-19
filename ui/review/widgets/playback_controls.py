"""Playback controls widget for review mode."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets


class PlaybackControls(QtWidgets.QWidget):
    """Widget with playback control buttons.

    Provides controls for:
    - Play/Pause
    - Step forward/backward
    - Seek to start/end
    - Playback speed adjustment

    Signals:
        play_pause_clicked: Emitted when play/pause button clicked
        step_forward_clicked: Emitted when step forward clicked
        step_backward_clicked: Emitted when step backward clicked
        seek_start_clicked: Emitted when seek to start clicked
        seek_end_clicked: Emitted when seek to end clicked
        speed_changed: Emitted when playback speed changes (float)
    """

    # Signals
    play_pause_clicked = QtCore.Signal()
    step_forward_clicked = QtCore.Signal()
    step_backward_clicked = QtCore.Signal()
    seek_start_clicked = QtCore.Signal()
    seek_end_clicked = QtCore.Signal()
    speed_changed = QtCore.Signal(float)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize playback controls.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        self._is_playing = False
        self._build_ui()

    def _build_ui(self) -> None:
        """Build control buttons layout."""
        # Seek to start button
        self._seek_start_btn = QtWidgets.QPushButton("⏮ Start")
        self._seek_start_btn.setToolTip("Seek to start (Home)")
        self._seek_start_btn.clicked.connect(self.seek_start_clicked.emit)
        self._seek_start_btn.setMinimumHeight(40)

        # Step backward button
        self._step_back_btn = QtWidgets.QPushButton("◀ Step Back")
        self._step_back_btn.setToolTip("Step backward one frame (Left Arrow)")
        self._step_back_btn.clicked.connect(self.step_backward_clicked.emit)
        self._step_back_btn.setMinimumHeight(40)

        # Play/Pause button
        self._play_pause_btn = QtWidgets.QPushButton("▶ Play")
        self._play_pause_btn.setToolTip("Play/Pause (Space)")
        self._play_pause_btn.clicked.connect(self.play_pause_clicked.emit)
        self._play_pause_btn.setMinimumHeight(40)
        self._play_pause_btn.setStyleSheet(
            "font-size: 14pt; font-weight: bold; background-color: #4CAF50; color: white;"
        )

        # Step forward button
        self._step_forward_btn = QtWidgets.QPushButton("Step Forward ▶")
        self._step_forward_btn.setToolTip("Step forward one frame (Right Arrow)")
        self._step_forward_btn.clicked.connect(self.step_forward_clicked.emit)
        self._step_forward_btn.setMinimumHeight(40)

        # Seek to end button
        self._seek_end_btn = QtWidgets.QPushButton("End ⏭")
        self._seek_end_btn.setToolTip("Seek to end (End)")
        self._seek_end_btn.clicked.connect(self.seek_end_clicked.emit)
        self._seek_end_btn.setMinimumHeight(40)

        # Speed control
        speed_label = QtWidgets.QLabel("Speed:")
        self._speed_combo = QtWidgets.QComboBox()
        self._speed_combo.addItem("0.1x", 0.1)
        self._speed_combo.addItem("0.25x", 0.25)
        self._speed_combo.addItem("0.5x", 0.5)
        self._speed_combo.addItem("1.0x", 1.0)
        self._speed_combo.addItem("1.5x", 1.5)
        self._speed_combo.addItem("2.0x", 2.0)
        self._speed_combo.setCurrentIndex(3)  # Default to 1.0x
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        # Layout
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._seek_start_btn)
        layout.addWidget(self._step_back_btn)
        layout.addWidget(self._play_pause_btn, 1)  # Play button takes more space
        layout.addWidget(self._step_forward_btn)
        layout.addWidget(self._seek_end_btn)
        layout.addStretch()
        layout.addWidget(speed_label)
        layout.addWidget(self._speed_combo)

        self.setLayout(layout)

    def set_playing(self, is_playing: bool) -> None:
        """Update button state for playing/paused.

        Args:
            is_playing: True if video is playing, False if paused
        """
        self._is_playing = is_playing

        if is_playing:
            self._play_pause_btn.setText("⏸ Pause")
            self._play_pause_btn.setStyleSheet(
                "font-size: 14pt; font-weight: bold; background-color: #FF9800; color: white;"
            )
        else:
            self._play_pause_btn.setText("▶ Play")
            self._play_pause_btn.setStyleSheet(
                "font-size: 14pt; font-weight: bold; background-color: #4CAF50; color: white;"
            )

    def _on_speed_changed(self, index: int) -> None:
        """Handle speed combo box change.

        Args:
            index: Selected index
        """
        speed = self._speed_combo.itemData(index)
        self.speed_changed.emit(speed)

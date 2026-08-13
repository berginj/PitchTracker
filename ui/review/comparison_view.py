"""Side-by-side synchronized pitch comparison for review mode."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.review.comparison_player import PitchClip, SyncVideoPlayer
from ui.themes import get_style_manager
from ui.themes.dialog_helpers import MARGINS_TIGHT

logger = logging.getLogger(__name__)


class ComparisonView(QtWidgets.QWidget):
    """Present two pitch clips with synchronized frame controls."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._sync_enabled = True
        self._style_manager = get_style_manager()
        self._build_ui()
        self._apply_style()
        self._connect_signals()

    def _build_ui(self) -> None:
        header = QtWidgets.QLabel("PITCH COMPARISON")
        header.setObjectName("comparison_title")
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header.setAccessibleName("Pitch comparison title")
        self._player_a = SyncVideoPlayer("Pitch A")
        self._player_b = SyncVideoPlayer("Pitch B")
        players_layout = QtWidgets.QHBoxLayout()
        players_layout.setSpacing(MARGINS_TIGHT[0])
        players_layout.addWidget(self._player_a, 1)
        players_layout.addWidget(self._player_b, 1)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(*MARGINS_TIGHT)
        layout.addWidget(header)
        layout.addLayout(players_layout, 1)
        layout.addWidget(self._build_controls())

    def _build_controls(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        widget.setObjectName("comparison_controls")
        widget.setAccessibleName("Comparison playback controls")
        self._sync_btn = self._button("Sync: ON", "Toggle synchronized playback")
        self._sync_btn.setCheckable(True)
        self._sync_btn.setChecked(True)
        self._start_btn = self._button("Start", "Seek both pitches to start")
        self._back_btn = self._button("Step Back", "Step pitches backward one frame")
        self._forward_btn = self._button("Step Forward", "Step pitches forward one frame")
        self._end_btn = self._button("End", "Seek both pitches to end")
        self._sync_btn.clicked.connect(self._on_sync_toggled)
        self._start_btn.clicked.connect(self._seek_to_start)
        self._back_btn.clicked.connect(self._step_backward)
        self._forward_btn.clicked.connect(self._step_forward)
        self._end_btn.clicked.connect(self._seek_to_end)
        self._timeline = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._timeline.setRange(0, 100)
        self._timeline.setAccessibleName("Comparison timeline")
        self._timeline.setAccessibleDescription("Seek through the loaded pitch comparison by relative frame")
        self._timeline.valueChanged.connect(self._on_timeline_changed)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self._sync_btn)
        button_layout.addStretch()
        for button in (
            self._start_btn,
            self._back_btn,
            self._forward_btn,
            self._end_btn,
        ):
            button_layout.addWidget(button)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, MARGINS_TIGHT[1], 0, 0)
        layout.addWidget(self._timeline)
        layout.addLayout(button_layout)
        return widget

    def _button(self, text: str, accessible_name: str) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.setAccessibleName(accessible_name)
        button.setMinimumHeight(self._style_manager.theme.button_height_sm)
        self._style_manager.style_button(button, "default")
        return button

    def _apply_style(self) -> None:
        theme = self._style_manager.theme
        self._style_manager.style_panel(self.findChild(QtWidgets.QWidget, "comparison_controls"), "normal")
        self._style_manager.style_slider(self._timeline)
        self.setStyleSheet(f"""
            ComparisonView {{ background-color: {theme.background_dark}; }}
            #comparison_title {{
                font-size: {theme.font_size_subtitle}px;
                font-weight: bold;
                color: {theme.accent_primary};
                padding: {MARGINS_TIGHT[0]}px;
            }}
            #comparison_header {{
                font-size: {theme.font_size_body}px;
                font-weight: bold;
                color: {theme.text_primary};
                background-color: {theme.surface_glass};
                border-radius: {theme.border_radius_small}px;
                padding: {MARGINS_TIGHT[0] // 2}px;
            }}
            #comparison_info {{
                font-size: {theme.font_size_small}px;
                color: {theme.text_secondary};
                padding: {MARGINS_TIGHT[0] // 2}px;
            }}
            #comparison_frame {{
                font-size: {theme.font_size_caption}px;
                color: {theme.text_muted};
            }}
            """)

    def _connect_signals(self) -> None:
        self._player_a.frame_changed.connect(self._on_player_a_frame_changed)

    def load_pitches(self, pitch_a: PitchClip, pitch_b: PitchClip) -> bool:
        """Load both clips and size the shared relative-frame timeline."""
        success_a = self._player_a.load_clip(pitch_a)
        success_b = self._player_b.load_clip(pitch_b)
        if success_a and success_b:
            max_frames = max(
                self._player_a.get_clip_length(),
                self._player_b.get_clip_length(),
            )
            self._timeline.setMaximum(max(1, max_frames - 1))
            self._timeline.setValue(0)
            logger.info("Loaded comparison: %s vs %s", pitch_a.label, pitch_b.label)
        return success_a and success_b

    def toggle_sync(self, synced: bool) -> None:
        """Set synchronized playback mode."""
        self._sync_enabled = synced
        self._sync_btn.setChecked(synced)
        self._sync_btn.setText(f"Sync: {'ON' if synced else 'OFF'}")

    def _on_sync_toggled(self, checked: bool) -> None:
        self.toggle_sync(checked)

    def _on_timeline_changed(self, value: int) -> None:
        self._player_a.seek_to_relative_frame(value)
        if self._sync_enabled:
            self._player_b.seek_to_relative_frame(value)

    def _on_player_a_frame_changed(self, frame: int) -> None:
        with QtCore.QSignalBlocker(self._timeline):
            self._timeline.setValue(frame)
        if self._sync_enabled:
            self._player_b.seek_to_relative_frame(frame)

    def _step_forward(self) -> None:
        self._player_a.step_forward()
        if self._sync_enabled:
            self._player_b.step_forward()

    def _step_backward(self) -> None:
        self._player_a.step_backward()
        if self._sync_enabled:
            self._player_b.step_backward()

    def _seek_to_start(self) -> None:
        self._player_a.seek_to_start()
        if self._sync_enabled:
            self._player_b.seek_to_start()
        self._timeline.setValue(0)

    def _seek_to_end(self) -> None:
        self._player_a.seek_to_end()
        if self._sync_enabled:
            self._player_b.seek_to_end()
        self._timeline.setValue(self._timeline.maximum())

    def close(self) -> None:
        """Release both clip readers."""
        self._player_a.close()
        self._player_b.close()


class ComparisonDialog(QtWidgets.QDialog):
    """Dialog wrapper for pitch comparison."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pitch Comparison")
        self.setMinimumSize(1000, 600)
        self.setAccessibleName("Pitch comparison dialog")
        self._comparison_view = ComparisonView()
        close_button = QtWidgets.QPushButton("Close")
        close_button.setAccessibleName("Close pitch comparison")
        get_style_manager().style_button(close_button, "ghost")
        close_button.clicked.connect(self.accept)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._comparison_view, 1)
        layout.addWidget(close_button)

    def load_pitches(self, pitch_a: PitchClip, pitch_b: PitchClip) -> bool:
        """Load both comparison pitches."""
        return self._comparison_view.load_pitches(pitch_a, pitch_b)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._comparison_view.close()
        super().closeEvent(event)


__all__ = ["PitchClip", "SyncVideoPlayer", "ComparisonView", "ComparisonDialog"]

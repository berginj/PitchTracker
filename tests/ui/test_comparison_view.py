"""Characterization tests for review pitch comparison widgets."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from ui.review.comparison_view import ComparisonView, PitchClip, SyncVideoPlayer


def _clip(label="Pitch A"):
    return PitchClip("pitch_1", Path("clip.avi"), 10, 20, label)


def test_sync_player_preserves_relative_frame_semantics(qtbot):
    player = SyncVideoPlayer()
    qtbot.addWidget(player)
    reader = MagicMock(current_frame_index=10)
    reader.read_frames.return_value = (np.zeros((4, 4), dtype=np.uint8), None)

    with patch("ui.review.comparison_player.VideoReader", return_value=reader):
        assert player.load_clip(_clip())
        player.seek_to_relative_frame(4)

    reader.seek_to_frame.assert_called_with(14)
    assert player.get_clip_length() == 10


def test_comparison_view_sync_controls_are_accessible(qtbot):
    view = ComparisonView()
    qtbot.addWidget(view)

    assert view._timeline.accessibleName() == "Comparison timeline"
    assert view._sync_btn.accessibleName() == "Toggle synchronized playback"
    assert view._forward_btn.minimumHeight() == view._style_manager.theme.button_height_sm


def test_timeline_seeks_both_players_when_synced(qtbot):
    view = ComparisonView()
    qtbot.addWidget(view)
    view._player_a.seek_to_relative_frame = MagicMock()
    view._player_b.seek_to_relative_frame = MagicMock()

    view._on_timeline_changed(7)

    view._player_a.seek_to_relative_frame.assert_called_once_with(7)
    view._player_b.seek_to_relative_frame.assert_called_once_with(7)

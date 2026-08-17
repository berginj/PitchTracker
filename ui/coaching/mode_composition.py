"""Coaching mode composition — mode stack, switching, and persistence."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6 import QtWidgets

from configs.app_state import load_state, save_state
from ui.coaching.game_state_manager import GameStateManager
from ui.coaching.session_history_tracker import SessionHistoryTracker
from ui.coaching.strike_zone_mapping import StrikeZoneOverlayConfig
from ui.coaching.widgets.mode_widgets import (
    BaseModeWidget,
    BroadcastViewWidget,
    GameModeWidget,
    SessionProgressionWidget,
)
from ui.themes import get_style_manager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def build_mode_content(
    config,
    strike_zone_overlay_config: StrikeZoneOverlayConfig,
) -> tuple[
    QtWidgets.QWidget,
    QtWidgets.QComboBox,
    QtWidgets.QStackedWidget,
    SessionHistoryTracker,
    GameStateManager,
    BroadcastViewWidget,
    SessionProgressionWidget,
    GameModeWidget,
]:
    """Build the main content area with mode selector and stack.

    Returns the container widget and all component references needed by
    CoachWindow.
    """
    style_manager = get_style_manager()

    # Mode selector toolbar
    mode_toolbar = QtWidgets.QFrame()
    style_manager.style_panel(mode_toolbar, "subtle")
    mode_toolbar_layout = QtWidgets.QHBoxLayout()
    mode_toolbar_layout.setContentsMargins(18, 14, 18, 14)

    mode_label = QtWidgets.QLabel("View Mode:")
    style_manager.style_label(mode_label, "eyebrow")
    mode_toolbar_layout.addWidget(mode_label)

    mode_selector = QtWidgets.QComboBox()
    mode_selector.setAccessibleName("View Mode")
    style_manager.style_input(mode_selector)
    mode_selector.addItems(["Broadcast View", "Session Progression", "Game Mode"])
    mode_toolbar_layout.addStretch()
    mode_toolbar.setLayout(mode_toolbar_layout)

    # Trackers
    session_tracker = SessionHistoryTracker()
    game_state_mgr = GameStateManager()

    # Mode stack
    mode_stack = QtWidgets.QStackedWidget()

    broadcast_mode = BroadcastViewWidget(strike_zone_overlay_config)
    progression_mode = SessionProgressionWidget(session_tracker, strike_zone_overlay_config)
    game_mode = GameModeWidget(game_state_mgr)

    mode_stack.addWidget(broadcast_mode)
    mode_stack.addWidget(progression_mode)
    mode_stack.addWidget(game_mode)

    # Load last mode from settings
    state = load_state()
    last_mode = state.get("last_coaching_mode", 0)
    mode_selector.setCurrentIndex(int(last_mode) if isinstance(last_mode, (str, int, float)) else 0)

    # Add selector to toolbar (after setting index to avoid premature signal)
    mode_toolbar_layout.insertWidget(1, mode_selector)

    # Main layout
    layout = QtWidgets.QVBoxLayout()
    layout.addWidget(mode_toolbar)
    layout.addWidget(mode_stack, 1)
    layout.setContentsMargins(0, 0, 0, 0)

    widget = QtWidgets.QWidget()
    widget.setLayout(layout)

    return (
        widget,
        mode_selector,
        mode_stack,
        session_tracker,
        game_state_mgr,
        broadcast_mode,
        progression_mode,
        game_mode,
    )


def on_mode_changed(
    index: int,
    mode_stack: QtWidgets.QStackedWidget,
    pitch_snapshot: list,
) -> None:
    """Handle mode selection change."""
    current_mode = mode_stack.currentWidget()
    if not isinstance(current_mode, BaseModeWidget):
        raise RuntimeError("Coaching mode stack contains an unsupported widget")
    camera = current_mode.get_current_camera_selection()

    mode_stack.setCurrentIndex(index)

    new_mode = mode_stack.currentWidget()
    if not isinstance(new_mode, BaseModeWidget):
        raise RuntimeError("Coaching mode stack contains an unsupported widget")
    new_mode.set_camera_selection(camera)
    new_mode.update_pitch_data(pitch_snapshot, new_pitches=[])

    state = load_state()
    state["last_coaching_mode"] = index
    save_state(state)

    mode_names = ["Broadcast View", "Session Progression", "Game Mode"]
    logger.debug(f"Switched to {mode_names[index]}")

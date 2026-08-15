"""Menu bar construction for ReviewWindow."""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets


def build_menu_bar(window: QtWidgets.QMainWindow, handlers: dict) -> None:
    """Build menu bar with File, Playback, Tools, Export menus.

    Args:
        window: The QMainWindow to add the menu bar to
        handlers: Dict mapping action keys to callables and state holders
    """
    menubar = window.menuBar()

    # --- File menu ---
    file_menu = menubar.addMenu("&File")

    _add(file_menu, "&Open Session...", "Ctrl+O", handlers["open_session"])
    _add(file_menu, "Review &All Sessions", "Ctrl+Shift+O", handlers["review_all"])
    file_menu.addSeparator()

    prev_action = _add(file_menu, "&Previous Session", "Ctrl+PgUp", handlers["prev_session"])
    next_action = _add(file_menu, "&Next Session", "Ctrl+PgDown", handlers["next_session"])
    file_menu.addSeparator()

    delete_action = _add(file_menu, "&Delete Current Session...", "Ctrl+D", handlers["delete_session"])
    file_menu.addSeparator()

    _add(file_menu, "&Close Session", "Ctrl+W", handlers["close_session"])
    file_menu.addSeparator()
    _add(file_menu, "E&xit", "Ctrl+Q", window.close)

    # --- Playback menu ---
    playback_menu = menubar.addMenu("&Playback")
    _add(playback_menu, "Play/Pause", "Space", handlers["play_pause"])
    _add(playback_menu, "Step Forward", "Right", handlers["step_forward"])
    _add(playback_menu, "Step Backward", "Left", handlers["step_backward"])
    playback_menu.addSeparator()
    _add(playback_menu, "Seek to Start", "Home", handlers["seek_start"])
    _add(playback_menu, "Seek to End", "End", handlers["seek_end"])

    # --- Tools menu ---
    tools_menu = menubar.addMenu("&Tools")

    annotation_action = QtGui.QAction("Toggle Annotation Mode", window)
    annotation_action.setShortcut("A")
    annotation_action.setCheckable(True)
    annotation_action.triggered.connect(handlers["toggle_annotation"])
    tools_menu.addAction(annotation_action)

    _add(tools_menu, "Clear Annotations", None, handlers["clear_annotations"])
    tools_menu.addSeparator()

    trajectory_action = QtGui.QAction("Toggle Trajectory Overlay", window)
    trajectory_action.setShortcut("T")
    trajectory_action.setCheckable(True)
    trajectory_action.triggered.connect(handlers["toggle_trajectory"])
    tools_menu.addAction(trajectory_action)

    # --- Export menu ---
    export_menu = menubar.addMenu("&Export")
    _add(export_menu, "Export &Config...", None, handlers["export_config"])
    _add(export_menu, "Export &Annotations...", None, handlers["export_annotations"])

    # Return action references needed by window state updates
    handlers["_actions"] = {
        "prev_session": prev_action,
        "next_session": next_action,
        "delete_session": delete_action,
        "annotation": annotation_action,
        "trajectory": trajectory_action,
    }


def _add(menu, text: str, shortcut, handler) -> QtGui.QAction:
    """Add a simple action to a menu."""
    action = QtGui.QAction(text, menu.parent())
    if shortcut:
        action.setShortcut(shortcut)
    action.triggered.connect(handler)
    menu.addAction(action)
    return action

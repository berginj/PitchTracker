"""Compact workspace controls and scrollable secondary coaching views."""

from typing import TYPE_CHECKING
from dataclasses import asdict
import json

from PySide6 import QtWidgets

from ui.themes import get_style_manager

if TYPE_CHECKING:
    from ui.coaching.coach_window import CoachWindow


def install_scrolling_layout(owner: QtWidgets.QWidget, content_layout: QtWidgets.QVBoxLayout) -> None:
    content = content_layout.parentWidget()
    assert content is not None
    scroll = QtWidgets.QScrollArea(owner)
    scroll.setAccessibleName("Coaching view content")
    scroll.setWidgetResizable(True)
    scroll.setMinimumSize(0, 0)
    scroll.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    scroll.setWidget(content)
    outer = QtWidgets.QVBoxLayout(owner)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(scroll)


def configure_live_workspace(host: "CoachWindow") -> None:
    host._session_bar.hide()
    host._controls_bar.hide()
    toolbar = QtWidgets.QWidget(host)
    row = QtWidgets.QHBoxLayout(toolbar)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(host._pitch_count_label)
    row.addWidget(host._quality_indicator)
    row.addStretch()
    switch = host._switch_pitcher_btn
    switch.setText("Change Pitcher")
    switch.setAccessibleName("Change active pitcher")
    switch.setMaximumSize(16777215, 16777215)
    switch.setMinimumHeight(get_style_manager().theme.button_height_md)
    row.addWidget(switch)
    tools = QtWidgets.QPushButton("Advanced Tools", toolbar)
    tools.setAccessibleName("Advanced coaching tools")
    menu = QtWidgets.QMenu(tools)
    host._advanced_actions = []
    details = menu.addAction("Latest pitch details")
    details.triggered.connect(lambda: show_pitch_details(host))
    for label, button in (("Tracking diagnostics", host._diagnostics_button),
                          ("Detector timing trial", host._detector_trial_button),
                          ("Adjust lane regions", host._lane_button), ("Rig settings", host._settings_button)):
        action = menu.addAction(label)
        action.setData(label)
        action.triggered.connect(button.click)
        host._advanced_actions.append((action, button))
    fatigue = menu.addAction("Fatigue indicator (research)")
    fatigue.triggered.connect(lambda: show_fatigue(host))
    tools.setMenu(menu)
    get_style_manager().style_button(tools, "ghost")
    row.addWidget(tools)
    layout = host.centralWidget().layout()
    assert isinstance(layout, QtWidgets.QVBoxLayout)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.setSpacing(8)
    layout.insertWidget(0, toolbar)
    host._lane_button.hide()
    host._settings_button.hide()


def show_fatigue(host: "CoachWindow") -> None:
    dialog = getattr(host, "_fatigue_dialog", None)
    if dialog is None:
        dialog = QtWidgets.QDialog(host)
        dialog.setWindowTitle("Fatigue indicator · research")
        layout = QtWidgets.QVBoxLayout(dialog)
        label = QtWidgets.QLabel("Session fatigue indicator · research")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(host._fatigue_indicator)
        close = QtWidgets.QPushButton("Close")
        close.setAccessibleName("Close fatigue research indicator")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        host._fatigue_dialog = dialog
    dialog.show()
    dialog.raise_()


def show_pitch_details(host: "CoachWindow") -> None:
    dialog = QtWidgets.QDialog(host)
    dialog.setWindowTitle("Latest pitch details")
    dialog.resize(620, 440)
    layout = QtWidgets.QVBoxLayout(dialog)
    notice = QtWidgets.QLabel("Recorded fields. Run/rise are endpoint displacement; induced break requires validation.")
    notice.setWordWrap(True)
    layout.addWidget(notice)
    text = QtWidgets.QPlainTextEdit()
    text.setAccessibleName("Latest recorded pitch fields")
    text.setReadOnly(True)
    text.setPlainText(json.dumps(asdict(host._pitch_snapshot[-1]), indent=2, default=str)
                      if host._pitch_snapshot else "No recorded pitch yet.")
    layout.addWidget(text)
    close = QtWidgets.QPushButton("Close")
    close.setAccessibleName("Close latest pitch details")
    close.clicked.connect(dialog.accept)
    layout.addWidget(close)
    dialog.exec()

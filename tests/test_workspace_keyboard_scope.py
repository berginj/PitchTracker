"""Hosted Review shortcuts must not intercept workspace navigation keys."""

from PySide6 import QtCore, QtGui, QtWidgets

from tests import test_workspace_navigation as navigation

workspace = navigation.workspace


def test_review_space_shortcut_does_not_consume_navigation_button_activation(workspace, qtbot):
    window, _pipeline = workspace
    window.activateWindow()
    assert window.navigate("sessions")
    players = window._nav["players"]
    players.setFocus()
    qtbot.waitUntil(lambda: QtWidgets.QApplication.focusWidget() is players)
    qtbot.keyClick(players, QtCore.Qt.Key.Key_Space)
    assert window.navigation_context.page == "players"


def test_review_shortcut_remains_available_inside_its_page(workspace, qtbot):
    window, _pipeline = workspace
    window.activateWindow()
    window.navigate("sessions")
    review = window.page("sessions").review
    action = next(action for action in review.findChildren(QtGui.QAction) if action.text() == "Play/Pause")
    triggered = []
    action.triggered.connect(lambda: triggered.append(True))
    review.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
    review.setFocus()
    qtbot.waitUntil(lambda: QtWidgets.QApplication.focusWidget() is review)
    qtbot.keyClick(review, QtCore.Qt.Key.Key_Space)
    assert triggered == [True]

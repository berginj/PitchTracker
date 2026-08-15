"""Tests for UI viewport reachability, accessibility, and keyboard traversal.

Covers UI-002 (setup width), UI-003 (review/launcher responsiveness),
and UI-004 (accessible names) from docs/review/UI_UX_REVIEW.md.

Tab reachability is verified by checking that interactive controls have a
focus policy that includes ``Qt.FocusPolicy.TabFocus``.  Actual keystroke
simulation is unreliable under ``QT_QPA_PLATFORM=offscreen`` and is not
attempted.

Manual screen-reader and DPI validation is NOT performed by these tests;
that remains a separate physical verification step.
"""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from PySide6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_PYTEST_QT = importlib.util.find_spec("pytestqt") is not None

requires_pytest_qt = pytest.mark.skipif(
    not HAS_PYTEST_QT,
    reason="pytest-qt not installed",
)

INTERACTIVE_TYPES = (
    QtWidgets.QPushButton,
    QtWidgets.QComboBox,
    QtWidgets.QCheckBox,
    QtWidgets.QRadioButton,
    QtWidgets.QLineEdit,
    QtWidgets.QSpinBox,
    QtWidgets.QDoubleSpinBox,
    QtWidgets.QSlider,
)

_TAB_MASK = int(QtCore.Qt.FocusPolicy.TabFocus)


# ── helpers ─────────────────────────────────────────────────────────
def _visible_interactive(root: QtWidgets.QWidget) -> list[QtWidgets.QWidget]:
    """Return visible interactive child widgets, excluding Qt internals."""
    return [
        w
        for w in root.findChildren(QtWidgets.QWidget)
        if (
            isinstance(w, INTERACTIVE_TYPES)
            and w.isVisibleTo(root)
            and not w.objectName().startswith("qt_")
            and not (
                isinstance(w, QtWidgets.QLineEdit)
                and isinstance(w.parent(), (QtWidgets.QComboBox, QtWidgets.QAbstractSpinBox))
            )
        )
    ]


def _is_within_viewport(
    widget: QtWidgets.QWidget, viewport: QtWidgets.QWidget
) -> bool:
    """True if at least part of *widget* is inside *viewport* bounds."""
    if not widget.isVisibleTo(viewport):
        return False
    pos = widget.mapTo(viewport, QtCore.QPoint(0, 0))
    vp = viewport.size()
    return (
        pos.x() + widget.width() > 0
        and pos.x() < vp.width()
        and pos.y() + widget.height() > 0
        and pos.y() < vp.height()
    )


def _is_tab_reachable(widget: QtWidgets.QWidget) -> bool:
    """True if *widget* accepts Tab focus."""
    return bool(int(widget.focusPolicy()) & _TAB_MASK)


def _assert_unique_names(root: QtWidgets.QWidget) -> None:
    """Assert all visible interactive controls have unique accessible names."""
    seen: dict[str, str] = {}
    for w in _visible_interactive(root):
        name = w.accessibleName()
        cls = w.__class__.__name__
        assert name, f"{cls} (obj={w.objectName()!r}) missing accessible name"
        assert name not in seen, (
            f"Duplicate accessible name {name!r}: "
            f"{seen[name]} and {cls}"
        )
        seen[name] = cls


def _make_launcher():
    """Create LauncherWindow with instant mock validation (no bg thread)."""
    from launcher import LauncherWindow

    mock_service = Mock()
    mock_service.validate_environment.return_value = SimpleNamespace(errors=[], warnings=[])
    return LauncherWindow(validation_service=mock_service)


# ── Launcher ────────────────────────────────────────────────────────
class TestLauncherViewportAndAccessibility:
    """UI-003 / UI-004: Launcher responsiveness and accessibility."""

    @requires_pytest_qt
    def test_role_buttons_tab_reachable(self, qtbot: "QtBot") -> None:
        window = _make_launcher()
        qtbot.addWidget(window)

        for btn in [window._setup_button, window._coach_button, window._review_button]:
            assert _is_tab_reachable(btn), (
                f"Role button {btn.accessibleName()!r} not tab-reachable"
            )

    @requires_pytest_qt
    def test_role_buttons_visible_at_1024x768(self, qtbot: "QtBot") -> None:
        window = _make_launcher()
        qtbot.addWidget(window)
        window.resize(1024, 768)
        window.show()
        qtbot.waitExposed(window)

        for btn in [window._setup_button, window._coach_button, window._review_button]:
            assert _is_within_viewport(btn, window), (
                f"Role button {btn.accessibleName()!r} not visible at 1024x768"
            )

    @requires_pytest_qt
    def test_about_and_auto_update_tab_reachable(self, qtbot: "QtBot") -> None:
        window = _make_launcher()
        qtbot.addWidget(window)

        assert _is_tab_reachable(window._auto_update_checkbox)
        about_btns = [
            b
            for b in window.findChildren(QtWidgets.QPushButton)
            if b.accessibleName() == "About PitchTracker"
        ]
        assert about_btns
        assert _is_tab_reachable(about_btns[0])

    @requires_pytest_qt
    def test_all_interactive_controls_have_unique_names(
        self, qtbot: "QtBot"
    ) -> None:
        window = _make_launcher()
        qtbot.addWidget(window)
        _assert_unique_names(window)


# ── Review ──────────────────────────────────────────────────────────
class TestReviewViewportAndAccessibility:
    """UI-003 / UI-004: Review responsiveness and accessibility."""

    @requires_pytest_qt
    def test_playback_controls_visible_at_1024x768(self, qtbot: "QtBot") -> None:
        from ui.review.review_window import ReviewWindow

        window = ReviewWindow()
        qtbot.addWidget(window)
        window.resize(1024, 768)
        window.show()
        qtbot.waitExposed(window)

        for attr in ("_play_pause_btn", "_seek_start_btn", "_seek_end_btn"):
            btn = getattr(window._controls, attr)
            assert _is_within_viewport(btn, window), (
                f"Playback {attr} not visible at 1024x768"
            )

    @requires_pytest_qt
    def test_playback_controls_tab_reachable(self, qtbot: "QtBot") -> None:
        from ui.review.review_window import ReviewWindow

        window = ReviewWindow()
        qtbot.addWidget(window)

        for attr in (
            "_play_pause_btn",
            "_seek_start_btn",
            "_seek_end_btn",
            "_prev_pitch_btn",
            "_next_pitch_btn",
        ):
            btn = getattr(window._controls, attr)
            assert _is_tab_reachable(btn), (
                f"Playback {attr} not tab-reachable"
            )

    @requires_pytest_qt
    def test_unique_accessible_names(self, qtbot: "QtBot") -> None:
        from ui.review.review_window import ReviewWindow

        window = ReviewWindow()
        qtbot.addWidget(window)
        _assert_unique_names(window)

    @requires_pytest_qt
    def test_right_panel_scroll_exists(self, qtbot: "QtBot") -> None:
        """Right panel has exactly one QScrollArea (no nested outer scroll)."""
        from ui.review.review_window import ReviewWindow

        window = ReviewWindow()
        qtbot.addWidget(window)

        scrolls = window.findChildren(QtWidgets.QScrollArea)
        assert len(scrolls) == 1, (
            f"Expected 1 scroll area (right panel), found {len(scrolls)}"
        )


# ── Setup ───────────────────────────────────────────────────────────
class TestSetupViewportAndAccessibility:
    """UI-002 / UI-004: Setup wizard responsiveness and accessibility."""

    @requires_pytest_qt
    def test_next_button_visible_at_1024x768(self, qtbot: "QtBot") -> None:
        from ui.setup.stereo_setup_window import StereoSetupWindow

        window = StereoSetupWindow()
        qtbot.addWidget(window)
        window.resize(1024, 768)
        window.show()
        qtbot.waitExposed(window)

        assert _is_within_viewport(window._next_button, window), (
            "Next button not visible at 1024x768"
        )

    @requires_pytest_qt
    def test_accepts_800x600_with_scroll(self, qtbot: "QtBot") -> None:
        from ui.setup.stereo_setup_window import StereoSetupWindow

        window = StereoSetupWindow()
        qtbot.addWidget(window)
        window.resize(800, 600)
        window.show()
        qtbot.waitExposed(window)

        assert window.size().width() <= 800, (
            f"Setup forced width {window.size().width()} > 800"
        )
        # Content scroll and step-indicator scroll exist
        scrolls = window.findChildren(QtWidgets.QScrollArea)
        assert len(scrolls) >= 2, (
            f"Expected >=2 scroll areas at 800x600, found {len(scrolls)}"
        )

    @requires_pytest_qt
    def test_nav_buttons_tab_reachable(self, qtbot: "QtBot") -> None:
        from ui.setup.stereo_setup_window import StereoSetupWindow

        window = StereoSetupWindow()
        qtbot.addWidget(window)

        for attr in ("_back_button", "_next_button", "_skip_button"):
            btn = getattr(window, attr)
            assert _is_tab_reachable(btn), (
                f"Setup nav {attr} not tab-reachable"
            )

    @requires_pytest_qt
    def test_nav_buttons_have_unique_accessible_names(
        self, qtbot: "QtBot"
    ) -> None:
        from ui.setup.stereo_setup_window import StereoSetupWindow

        window = StereoSetupWindow()
        qtbot.addWidget(window)

        nav_names = [
            window._back_button.accessibleName(),
            window._next_button.accessibleName(),
            window._skip_button.accessibleName(),
            window._finish_button.accessibleName(),
        ]
        assert all(nav_names), f"Nav button missing name: {nav_names}"
        assert len(set(nav_names)) == len(nav_names), (
            f"Duplicate nav names: {nav_names}"
        )


# ── Recording Settings ──────────────────────────────────────────────
class TestRecordingSettingsAccessibility:
    """UI-004: Recording settings controls have accessible names."""

    @requires_pytest_qt
    def test_form_controls_have_unique_accessible_names(
        self, qtbot: "QtBot"
    ) -> None:
        from ui.dialogs.recording_settings_dialog import RecordingSettingsDialog

        dialog = RecordingSettingsDialog(None, "test", ".", 60.0)
        qtbot.addWidget(dialog)
        _assert_unique_names(dialog)


# ── Startup Dialog ──────────────────────────────────────────────────
class TestStartupDialogAccessibility:
    """UI-004: Startup dialog controls have accessible names."""

    @requires_pytest_qt
    def test_form_controls_have_unique_accessible_names(
        self, qtbot: "QtBot"
    ) -> None:
        from ui.dialogs.startup_dialog import StartupDialog

        dialog = StartupDialog()
        qtbot.addWidget(dialog)
        _assert_unique_names(dialog)

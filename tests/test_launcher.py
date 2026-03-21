"""Tests for launcher startup behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

import launcher
import startup_validator


def _ensure_qapp() -> launcher.QtWidgets.QApplication:
    app = launcher.QtWidgets.QApplication.instance()
    if app is None:
        app = launcher.QtWidgets.QApplication([])
    return app


def test_launcher_window_starts_in_pending_validation_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_qapp()
    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)

    window = launcher.LauncherWindow()

    assert window._validation_state == "pending"
    assert window._setup_button.isEnabled() is False
    assert window._coach_button.isEnabled() is False
    assert window._warning_title.text() == "Checking system readiness"
    assert "background" in window._warning_body.text()


def test_launcher_window_enables_actions_when_validation_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_qapp()
    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)

    window = launcher.LauncherWindow()
    window._on_validation_complete([], ["warning one", "warning two"])

    assert window._validation_state == "completed"
    assert window._setup_button.isEnabled() is True
    assert window._coach_button.isEnabled() is True
    assert window._warning_title.text() == "Startup warnings"
    assert "warning one" in window._warning_body.text()
    assert "warning two" in window._warning_body.text()


def test_launcher_window_keeps_actions_disabled_when_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_qapp()
    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)

    window = launcher.LauncherWindow()
    window._on_validation_failed("worker crashed")

    assert window._validation_state == "completed"
    assert window._setup_button.isEnabled() is False
    assert window._coach_button.isEnabled() is False
    assert window._warning_title.text() == "Startup issues"
    assert "worker crashed" in window._warning_body.text()


def test_project_root_is_not_added_twice_when_path_case_differs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(launcher.sys, "path", [r"C:\Users\bergi\app\PitchTracker"])

    launcher._ensure_project_root_on_sys_path(Path(r"C:\Users\bergi\App\PitchTracker"))

    assert launcher.sys.path == [r"C:\Users\bergi\app\PitchTracker"]


def test_dependency_checker_loads_by_file_path() -> None:
    checker = startup_validator._load_dependency_checker()

    assert hasattr(checker, "check_dependencies")


def test_main_shows_launcher_without_blocking_on_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyApp:
        def setStyle(self, _style: str) -> None:
            pass

        def setApplicationName(self, _name: str) -> None:
            pass

        def setApplicationVersion(self, _version: str) -> None:
            pass

        def setOrganizationName(self, _name: str) -> None:
            pass

        def exec(self) -> int:
            return 0

    class DummyLauncher:
        def __init__(self) -> None:
            self.shown = False

        def show(self) -> None:
            self.shown = True

    app = DummyApp()
    created_windows: list[DummyLauncher] = []

    monkeypatch.setattr(launcher, "create_required_directories", lambda: None)
    monkeypatch.setattr(launcher, "get_current_version", lambda: "1.0.0")
    monkeypatch.setattr(launcher.QtWidgets, "QApplication", lambda _argv: app)

    def build_launcher() -> DummyLauncher:
        window = DummyLauncher()
        created_windows.append(window)
        return window

    monkeypatch.setattr(launcher, "LauncherWindow", build_launcher)
    monkeypatch.setattr(
        launcher.sys,
        "exit",
        lambda code=0: (_ for _ in ()).throw(SystemExit(code)),
    )

    with pytest.raises(SystemExit) as exc_info:
        launcher.main()

    assert exc_info.value.code == 0
    assert len(created_windows) == 1
    assert created_windows[0].shown is True

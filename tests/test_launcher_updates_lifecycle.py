"""Launcher updater threads must finish before window teardown or installation."""

from pathlib import Path
from threading import Event

import pytest

import launcher
import launcher_updates
from launcher_threads import SilentUpdateThread, UpdateCheckThread


@pytest.mark.parametrize("kind", ["check", "download"])
def test_close_waits_for_active_updater_and_blocks_late_results(monkeypatch, qtbot, kind) -> None:
    started, release = Event(), Event()

    class BlockedCheck(UpdateCheckThread):
        def run(self):
            started.set()
            release.wait(5)
            self.update_available.emit({"version": "test"})

    class BlockedDownload(SilentUpdateThread):
        def run(self):
            started.set()
            release.wait(5)
            self.ready.emit(Path("test-installer.exe"))

    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)
    monkeypatch.setattr(launcher_updates, "UpdateCheckThread", BlockedCheck)
    monkeypatch.setattr(launcher_updates, "SilentUpdateThread", BlockedDownload)
    monkeypatch.setattr(launcher_updates, "install_update", lambda *_args, **_kwargs: pytest.fail("Late install"))
    monkeypatch.setattr(
        launcher_updates.LauncherUpdateController, "_is_version_skipped",
        lambda *_args: pytest.fail("Late update notification"),
    )
    window = launcher.LauncherWindow()
    qtbot.addWidget(window)
    window.show()
    controller = window._update_controller
    if kind == "check":
        controller.check_for_updates()
        worker = controller._update_thread
        controller.check_for_updates()
        assert controller._update_thread is worker
    else:
        controller._start_silent_update({"download_url": "test", "expected_sha256": "test"})
        worker = controller._silent_update_thread
    try:
        qtbot.waitUntil(started.is_set)
        assert not window.close()
        assert not window.close()
        assert window.isVisible()
        assert worker.isInterruptionRequested()
        # The scheduled two-second callback must be harmless during shutdown.
        controller.check_for_updates()
        controller._start_silent_update({"download_url": "late"})
        assert (controller._update_thread is worker) if kind == "check" else controller._update_thread is None
        release.set()
        qtbot.waitUntil(lambda: not window.isVisible())
        assert controller._update_thread is None
        assert controller._silent_update_thread is None
        assert controller._pending_installer is None
    finally:
        release.set()
        if controller._update_thread is worker or controller._silent_update_thread is worker:
            worker.wait(5000)


@pytest.mark.parametrize("result", ["ready", "failed"])
def test_download_result_keeps_worker_until_terminal_signal(monkeypatch, qtbot, result) -> None:
    release = Event()
    installed = []

    class PausedResultDownload(SilentUpdateThread):
        def run(self):
            if result == "ready":
                self.ready.emit(Path("test-installer.exe"))
            else:
                self.failed.emit("test failure")
            release.wait(5)

    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)
    monkeypatch.setattr(launcher_updates, "SilentUpdateThread", PausedResultDownload)
    window = launcher.LauncherWindow()
    qtbot.addWidget(window)
    window.show()
    controller = window._update_controller

    def install_after_terminal(*_args, **_kwargs):
        assert controller._silent_update_thread is None
        installed.append(True)
        return False

    monkeypatch.setattr(launcher_updates, "install_update", install_after_terminal)
    controller._start_silent_update({"download_url": "test"})
    worker = controller._silent_update_thread
    try:
        if result == "ready":
            qtbot.waitUntil(lambda: controller._pending_installer is not None)
        else:
            qtbot.wait(20)
        assert controller._silent_update_thread is worker
        assert worker.isRunning()
        assert not installed
        controller._start_silent_update({"download_url": "duplicate"})
        assert controller._silent_update_thread is worker
        release.set()
        qtbot.waitUntil(lambda: controller._silent_update_thread is None)
        assert len(installed) == (1 if result == "ready" else 0)
    finally:
        release.set()
        if controller._silent_update_thread is worker:
            worker.wait(5000)
        window.close()

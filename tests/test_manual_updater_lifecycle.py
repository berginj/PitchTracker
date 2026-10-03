"""Manual update dialogs retain downloads until native QThread completion."""

from pathlib import Path
from threading import Event

import pytest

from PySide6 import QtCore, QtWidgets
import ui.update_dialog as updates

INFO = {"version": "test", "release_notes": "test", "release_date": "", "download_url": "unused"}


@pytest.mark.parametrize("close_action", ["reject", "close", "accept"])
def test_dialog_defers_close_and_suppresses_late_download(monkeypatch, qtbot, close_action):
    started, release = Event(), Event()

    class BlockedDownload(updates.DownloadThread):
        def run(self):
            started.set()
            release.wait(5)
            self.downloaded.emit(Path("never-install.exe"))

    monkeypatch.setattr(updates, "DownloadThread", BlockedDownload)
    monkeypatch.setattr(updates, "install_update", lambda *_args: pytest.fail("Late installer launch"))
    monkeypatch.setattr(updates, "ask_confirmation", lambda *_args, **_kwargs: pytest.fail("Late prompt"))
    dialog = updates.UpdateDialog(INFO)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog._download_and_install()
    worker = dialog._download_thread
    try:
        qtbot.waitUntil(started.is_set)
        getattr(dialog, close_action)()
        assert dialog.isVisible()
        assert worker.isInterruptionRequested()
        assert dialog._download_thread is worker
        dialog._download_and_install()
        assert dialog._download_thread is worker
        release.set()
        qtbot.waitUntil(lambda: dialog._download_thread is None)
        assert not dialog.isVisible()
        dialog._download_and_install()
        assert dialog._download_thread is None
    finally:
        release.set()
        if dialog._download_thread is worker:
            worker.wait(5000)


@pytest.mark.parametrize("result", ["ready", "error"])
def test_download_result_and_retry_wait_for_terminal_worker(monkeypatch, qtbot, result):
    release = Event()
    presented = []

    class PausedResult(updates.DownloadThread):
        def run(self):
            if result == "ready":
                self.downloaded.emit(Path("test.exe"))
            else:
                self.error.emit("test error")
            release.wait(5)

    monkeypatch.setattr(updates, "DownloadThread", PausedResult)
    dialog = updates.UpdateDialog(INFO)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(dialog, "_present_download", lambda *_args: presented.append("ready"))
    monkeypatch.setattr(dialog, "_present_download_error", lambda *_args: presented.append("error"))
    dialog._download_and_install()
    worker = dialog._download_thread
    try:
        qtbot.waitUntil(lambda: dialog._download_result is not None or dialog._download_error is not None)
        assert not presented
        dialog._download_and_install()
        assert dialog._download_thread is worker
        release.set()
        qtbot.waitUntil(lambda: dialog._download_thread is None)
        assert presented == [result]
    finally:
        release.set()
        if dialog._download_thread is worker:
            worker.wait(5000)


def test_manual_install_requests_guarded_parent_close(monkeypatch, qtbot):
    class Parent(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.close_requested = False

        def closeEvent(self, event):
            self.close_requested = True
            event.ignore()

    parent = Parent()
    qtbot.addWidget(parent)
    dialog = updates.UpdateDialog(INFO, parent)
    monkeypatch.setattr(updates, "ask_confirmation", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(updates, "install_update", lambda *_args: True)
    dialog._present_download(Path("mock.exe"))
    assert parent.close_requested


def test_missing_checksum_does_not_contact_network(monkeypatch):
    import updater
    monkeypatch.setattr(updater, "urlopen", lambda *_args, **_kwargs: pytest.fail("Unverifiable download"))
    assert updater.download_update("unused") is None


def test_launcher_close_waits_for_modal_manual_download(monkeypatch, qtbot):
    import launcher
    import launcher_updates

    release = Event()

    class BlockedDownload(updates.DownloadThread):
        def run(self):
            release.wait(5)

    monkeypatch.setattr(updates, "DownloadThread", BlockedDownload)
    monkeypatch.setattr(launcher_updates.LauncherUpdateController, "_is_version_skipped", lambda *_args: False)
    window = launcher.LauncherWindow(background_tasks=False)
    qtbot.addWidget(window)
    window.show()
    controller = window._update_controller
    observations = []

    def start_download():
        assert controller._manual_dialog is not None
        controller._manual_dialog._download_and_install()

    def request_close():
        dialog = controller._manual_dialog
        assert dialog is not None
        assert not window.close()
        assert window.isVisible()
        assert dialog.isVisible()
        assert dialog._download_thread is not None
        assert dialog._download_thread.isInterruptionRequested()
        observations.append("deferred")
        release.set()

    QtCore.QTimer.singleShot(0, start_download)
    QtCore.QTimer.singleShot(40, request_close)
    try:
        controller._on_update_available(INFO)
        assert observations == ["deferred"]
        assert controller._manual_dialog is None
        assert not window.isVisible()
    finally:
        release.set()

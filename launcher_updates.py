"""On-load update orchestration for the launcher.

Coordinates the background update check, SHA-256-verified download, and a
session-safe silent install. Kept separate from ``launcher.py`` so the launcher
window stays focused on role selection and under the file-length cap.
"""

from __future__ import annotations

import json

from loguru import logger
from PySide6 import QtCore, QtWidgets

from launcher_threads import SilentUpdateThread, UpdateCheckThread
from updater import install_update, is_auto_update_enabled


class LauncherUpdateController(QtCore.QObject):
    """Drive update checks and installs on behalf of the launcher window.

    The owning window is visible only on the launcher screen (it hides while a
    workflow runs), so its visibility is used to decide whether a verified
    installer may launch immediately or must be deferred until the user returns.
    """

    shutdown_finished = QtCore.Signal()

    def __init__(self, window: QtWidgets.QMainWindow):
        super().__init__(window)
        self._window = window
        self._update_thread: UpdateCheckThread | None = None
        self._silent_update_thread: SilentUpdateThread | None = None
        self._pending_installer = None
        self._closing = False
        self._manual_dialog: QtWidgets.QDialog | None = None

    def begin_shutdown(self) -> bool:
        """Prevent new work and retain active Qt workers until they finish."""
        self._closing = True
        if self._manual_dialog is not None:
            self._manual_dialog.reject()
        for thread in (self._update_thread, self._silent_update_thread):
            if thread is not None:
                thread.requestInterruption()
        return not self._has_active_workers()

    def _has_active_workers(self) -> bool:
        return (self._update_thread is not None or self._silent_update_thread is not None
                or self._manual_dialog is not None)

    def check_for_updates(self) -> None:
        """Check for updates in a background worker thread (non-blocking)."""
        if self._closing or self._update_thread is not None:
            return
        self._update_thread = UpdateCheckThread()
        self._update_thread.update_available.connect(self._on_update_available)
        self._update_thread.finished.connect(self._on_update_check_finished)
        self._update_thread.start()

    def _on_update_check_finished(self) -> None:
        thread = self._update_thread
        if thread is not None:
            thread.wait()
            self._update_thread = None
            thread.deleteLater()
        self._on_worker_finished()

    def _on_silent_update_finished(self) -> None:
        thread = self._silent_update_thread
        if thread is not None:
            thread.wait()
            self._silent_update_thread = None
            thread.deleteLater()
        self._on_worker_finished()

    def _on_worker_finished(self) -> None:
        if self._closing:
            if not self._has_active_workers():
                self.shutdown_finished.emit()
        else:
            self.install_pending_update()

    def install_pending_update(self) -> None:
        """Launch a pending verified installer, but only from the launcher screen.

        If a workflow (Setup/Coaching/Review) is active the launcher is hidden;
        in that case we defer so a silent install never interrupts a live or
        recording session. The install runs once the user returns to the launcher.
        """
        if self._closing or self._has_active_workers() or not self._pending_installer:
            return
        if not self._window.isVisible():
            logger.info("Auto-update ready; deferring install until current workflow closes")
            return
        installer_path = self._pending_installer
        self._pending_installer = None
        logger.info(f"Auto-update: launching verified installer silently: {installer_path}")
        if install_update(installer_path, silent=True):
            # Go through the launcher's close guard so validation also drains.
            self._window.close()
        else:
            logger.warning("Auto-update: installer failed to launch")

    def _on_update_available(self, update_info: dict) -> None:
        """Decide between silent auto-install and the manual update dialog."""
        if self._closing:
            return
        if self._is_version_skipped(update_info["version"]):
            return

        # Fully silent path: only when enabled AND a checksum is available to
        # verify against (never auto-launch an unverifiable installer).
        if is_auto_update_enabled() and update_info.get("expected_sha256"):
            self._start_silent_update(update_info)
            return

        # Manual path: notify and let the user download/install.
        from ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(update_info, parent=self._window)
        self._manual_dialog = dialog
        try:
            dialog.exec()
        finally:
            self._manual_dialog = None
            dialog.deleteLater()
            self._on_worker_finished()

    def _start_silent_update(self, update_info: dict) -> None:
        """Download + SHA-256-verify the update in the background, then install."""
        if self._closing or self._silent_update_thread is not None:
            return
        logger.info(f"Auto-update: downloading v{update_info.get('version')} in background")
        self._silent_update_thread = SilentUpdateThread(update_info["download_url"], update_info.get("expected_sha256"))
        self._silent_update_thread.ready.connect(self._on_silent_update_ready)
        self._silent_update_thread.failed.connect(self._on_silent_update_failed)
        self._silent_update_thread.finished.connect(self._on_silent_update_finished)
        self._silent_update_thread.start()

    def _on_silent_update_ready(self, installer_path) -> None:
        """A verified installer is ready; install now or defer if a session is open."""
        if self._closing:
            return
        self._pending_installer = installer_path

    def _on_silent_update_failed(self, message: str) -> None:
        """Log a silent-update failure without interrupting the user."""
        logger.warning(f"Auto-update download/verification failed: {message}")

    @staticmethod
    def _is_version_skipped(version: str) -> bool:
        """Return True if the user previously chose to skip this version."""
        try:
            from updater import UPDATE_SETTINGS_PATH
            settings_file = UPDATE_SETTINGS_PATH
            if not settings_file.exists():
                return False

            with open(settings_file) as f:
                settings = json.load(f)

            return bool(settings.get("skipped_version") == version)

        except Exception:
            return False


__all__ = ["LauncherUpdateController"]

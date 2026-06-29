"""Background worker threads used by the launcher."""

from __future__ import annotations

from PySide6 import QtCore

from app.services.tooling import ToolingService
from updater import check_for_updates, download_update


class UpdateCheckThread(QtCore.QThread):
    """Background thread for checking updates without blocking UI."""

    update_available = QtCore.Signal(dict)

    def run(self) -> None:
        """Check for updates in background."""
        try:
            update_info = check_for_updates(timeout=5)
            if update_info["available"]:
                self.update_available.emit(update_info)
        except Exception:
            pass


class SilentUpdateThread(QtCore.QThread):
    """Download and SHA-256-verify an update in the background for silent install.

    Verification is mandatory (``require_checksum=True``); if the release has no
    checksum or it does not match, the thread reports failure and no installer is
    produced, so an unverified binary is never launched.
    """

    ready = QtCore.Signal(object)  # Path to the verified installer
    failed = QtCore.Signal(str)

    def __init__(self, url: str, expected_sha256: str | None):
        super().__init__()
        self._url = url
        self._expected_sha256 = expected_sha256

    def run(self) -> None:
        try:
            installer_path = download_update(
                self._url,
                expected_sha256=self._expected_sha256,
                require_checksum=True,
            )
            if installer_path:
                self.ready.emit(installer_path)
            else:
                self.failed.emit("download or SHA-256 verification failed")
        except Exception as exc:  # noqa: BLE001 - surface worker failures
            self.failed.emit(str(exc))


class StartupValidationThread(QtCore.QThread):
    """Run startup validation in a subprocess without blocking the launcher UI."""

    validation_complete = QtCore.Signal(list, list)
    validation_failed = QtCore.Signal(str)

    def __init__(self, tooling_service: ToolingService):
        super().__init__()
        self._tooling_service = tooling_service

    def run(self) -> None:
        try:
            result = self._tooling_service.validate_environment()
            self.validation_complete.emit(result.errors, result.warnings)
        except Exception as exc:  # noqa: BLE001 - surface worker failures
            self.validation_failed.emit(str(exc))


__all__ = ["StartupValidationThread", "UpdateCheckThread", "SilentUpdateThread"]

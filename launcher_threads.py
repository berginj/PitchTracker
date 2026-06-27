"""Background worker threads used by the launcher."""

from __future__ import annotations

from PySide6 import QtCore

from app.services.tooling import ToolingService
from updater import check_for_updates


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


__all__ = ["StartupValidationThread", "UpdateCheckThread"]

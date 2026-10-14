"""Drain pipeline work outside the GUI thread while retaining its owner."""

from PySide6 import QtCore

from app.qt_pipeline_service import QtPipelineService


class PipelineShutdownThread(QtCore.QThread):
    def __init__(self, service: QtPipelineService, parent: QtCore.QObject):
        super().__init__(parent)
        self._service = service
        self.error: str | None = None

    def run(self) -> None:
        try:
            self._service.shutdown()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Workspace pipeline shutdown remains incomplete")
            self.error = str(exc)

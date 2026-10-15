"""Keep local review reachable when the selected Live configuration is invalid."""

from PySide6 import QtCore, QtWidgets

from app.qt_pipeline_service import QtPipelineService
from ui.workspace.contracts import SessionPreparation
from ui.coaching.session_commands import SessionOperation


class UnavailableLivePage(QtWidgets.QWidget):
    preparation_changed = QtCore.Signal(object)
    review_requested = QtCore.Signal()
    setup_requested = QtCore.Signal()
    exit_requested = QtCore.Signal()
    session_operation_changed = QtCore.Signal()
    configuration_available = False

    def __init__(self, pipeline: QtPipelineService, message: str):
        super().__init__()
        self._pipeline = pipeline
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Live configuration unavailable")
        title.setWordWrap(True)
        detail = QtWidgets.QLabel(
            message + "\n\nCorrect the selected configuration and restart. "
            "Sessions and Players remain available without camera acquisition.")
        detail.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(detail)
        review = QtWidgets.QPushButton("Open Sessions")
        review.setAccessibleName("Open sessions while Live configuration is unavailable")
        review.clicked.connect(self.review_requested)
        layout.addWidget(review)
        layout.addStretch()

    def host_in_workspace(self, parent: QtWidgets.QWidget) -> None:
        self.setParent(parent)

    def stop_updates(self) -> None:
        pass

    def preparation(self) -> SessionPreparation:
        return SessionPreparation()

    def session_operation(self) -> SessionOperation:
        return SessionOperation()

    def session_command_busy(self) -> bool:
        return False

    def begin_session_shutdown(self) -> bool:
        return True

    def apply_runtime_status(self, status) -> None:
        pass

    def perform_session_action(self, action: str) -> None:
        raise RuntimeError("Correct the selected configuration and restart before preparing Live capture")

    def request_pitcher(self, name: str) -> None:
        raise RuntimeError("Correct the selected configuration before changing the active pitcher")

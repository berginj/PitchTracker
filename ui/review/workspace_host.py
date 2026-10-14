"""Public page hosting and selection handoffs for the existing review facade."""

from PySide6 import QtGui, QtWidgets

from app.review import ReviewService
from ui.review._session_controller import SessionController
from ui.workspace.contracts import ReviewSelection


class ReviewWorkspaceHost(QtWidgets.QMainWindow):
    _service: ReviewService
    _session_ctrl: SessionController
    _selected_pitch_id: str | None

    def host_in_workspace(self, parent: QtWidgets.QWidget) -> None:
        from ui.workspace.hosting import embed_window
        self._workspace_hosted = True
        embed_window(self, parent, scroll_content=True)

    def selection(self) -> ReviewSelection:
        session = self._service.session
        return ReviewSelection(session.session_dir, session.session_id, self._selected_pitch_id) if session else ReviewSelection()

    def open_session(self, selection: ReviewSelection) -> None:
        if selection.session_dir is not None:
            self._session_ctrl.load_session(selection.session_dir)

    def shutdown_for_workspace(self) -> bool:
        self._workspace_shutdown = True
        event = QtGui.QCloseEvent()
        self.closeEvent(event)
        return event.isAccepted()

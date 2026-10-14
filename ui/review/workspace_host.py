"""Public page hosting and selection handoffs for the existing review facade."""

from PySide6 import QtGui, QtWidgets
from pathlib import Path
from typing import TYPE_CHECKING, cast

from app.review import ReviewService
from app.services.orchestrator.runtime_status import RuntimeStatus
from ui.review._session_controller import SessionController
from ui.workspace.contracts import ReviewSelection

if TYPE_CHECKING:
    from ui.review.review_window import ReviewWindow


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

    def open_session(self, selection: ReviewSelection) -> bool:
        if selection.session_dir is not None:
            if not self._session_ctrl.load_session(selection.session_dir):
                return False
            if selection.pitch_id:
                session = self._service.session
                if session:
                    index = next((i for i, pitch in enumerate(session.pitches) if pitch.pitch_id == selection.pitch_id), None)
                    if index is not None:
                        cast("ReviewWindow", self)._on_pitch_selected(index)
                    else:
                        self._session_ctrl.close_session()
                        return False
            return True
        return False

    def update_runtime(self, status: RuntimeStatus) -> None:
        self._service.update_runtime(status)

    def available_sessions(self, root: Path) -> list[Path]:
        return self._service.available_sessions(root)

    def open_local_session(self) -> None:
        self._session_ctrl.open_session_dialog()

    def set_recordings_root(self, root: Path) -> None:
        self._session_ctrl.recordings_root = root

    def browse_session_video(self) -> None:
        from ui.review.experience_layout import browse_session_video
        browse_session_video(cast("ReviewWindow", self))

    def shutdown_for_workspace(self) -> bool:
        self._workspace_shutdown = True
        event = QtGui.QCloseEvent()
        self.closeEvent(event)
        return event.isAccepted()

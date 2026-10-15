"""Local completed-session browsing and public review context handoff."""

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from app.services.orchestrator.runtime_status import RuntimeStatus
from ui.review.review_window import ReviewWindow
from ui.themes import get_style_manager
from ui.workspace.contracts import ReviewSelection


class SessionsPage(QtWidgets.QWidget):
    selection_changed = QtCore.Signal(object)
    exit_requested = QtCore.Signal()

    def __init__(self, recordings_root: Path = Path("recordings")):
        super().__init__()
        self._shutdown_complete = False
        self._runtime = RuntimeStatus()
        self._player_filter: str | None = None
        self._recordings_root = recordings_root
        self._review = ReviewWindow()
        self._review.set_recordings_root(recordings_root)
        self._review.host_in_workspace(self)
        self._review.selection_changed.connect(self._selection_changed)
        self._review.exit_requested.connect(self.exit_requested)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        self._selection_label = QtWidgets.QLabel("Choose a completed local session. Active recording is shown above.")
        self._selection_label.setWordWrap(True)
        self._selection_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(self._selection_label)
        row = QtWidgets.QHBoxLayout()
        self._sessions = QtWidgets.QComboBox()
        self._sessions.setAccessibleName("Completed local sessions")
        self._sessions.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._sessions.setMinimumContentsLength(12)
        row.addWidget(self._sessions, 1)
        for text, name, callback in (("Review", "Review selected completed session", self._open_selected),
                                     ("Refresh", "Refresh local session history", self.refresh),
                                     ("Open Local…", "Open a local session directory", self._review.open_local_session)):
            button = QtWidgets.QPushButton(text)
            button.setAccessibleName(name)
            get_style_manager().style_button(button, "primary" if text == "Review" else "ghost")
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        raw = QtWidgets.QPushButton("Browse full session video")
        raw.setAccessibleName("Browse session video without pitch association")
        get_style_manager().style_button(raw, "ghost")
        raw.clicked.connect(self._review.browse_session_video)
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.addWidget(raw)
        self._clear_player = QtWidgets.QPushButton("Show all players")
        self._clear_player.setAccessibleName("Clear historical player filter")
        self._clear_player.clicked.connect(lambda: self.browse_player(None))
        filter_row.addWidget(self._clear_player)
        self._clear_player.hide()
        layout.addLayout(filter_row)
        layout.addWidget(self._review, 1)
        self.refresh()

    @property
    def review(self) -> ReviewWindow:
        return self._review

    def refresh(self) -> None:
        selected = self._sessions.currentData()
        self._sessions.clear()
        for path in self._review.available_sessions(self._recordings_root, pitcher_name=self._player_filter):
            self._sessions.addItem(path.name, path)
        if self._sessions.count() == 0:
            self._sessions.addItem("No completed local sessions", None)
        index = self._sessions.findData(selected)
        if index >= 0:
            self._sessions.setCurrentIndex(index)

    def _open_selected(self) -> None:
        path = self._sessions.currentData()
        if path is not None:
            self.open_selection(ReviewSelection(path, pitcher_name=self._player_filter))
        else:
            self._selection_label.setText("No completed session found. Use Open Local or finish a recording, then Refresh.")

    def open_selection(self, selection: ReviewSelection) -> None:
        if selection.pitcher_name != self._player_filter:
            self._player_filter = selection.pitcher_name
            self.refresh()
        self._clear_player.setVisible(self._player_filter is not None)
        if not self._review.open_session(selection):
            self._selection_label.setText("Could not open the requested session or pitch. Check its local files and try again.")

    def _selection_changed(self, selection: ReviewSelection) -> None:
        self._selection_label.setText(
            f"Historical: {selection.session_id} · {selection.pitch_id or 'session video'}"
            if selection.session_dir else "Choose a completed local session. Active recording is shown above.")
        self.selection_changed.emit(selection)

    def update_runtime(self, status: RuntimeStatus) -> None:
        self._runtime = status
        self._review.update_runtime(status)

    def browse_player(self, player_name: str | None) -> None:
        self._review.close_session()
        self._player_filter = player_name
        self._clear_player.setVisible(player_name is not None)
        self.refresh()
        self._selection_label.setText(
            f"History filter: {player_name}. Only explicitly attributed pitches match; legacy attribution stays unknown."
            if player_name else "All players. Choose a completed recorded session.")

    def shutdown_for_workspace(self) -> bool:
        if not self._shutdown_complete:
            self._shutdown_complete = self._review.shutdown_for_workspace()
        return self._shutdown_complete

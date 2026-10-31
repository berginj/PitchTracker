"""Local completed-session browsing and public review context handoff."""

import logging
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
        self._history: list[Path] = []
        self._history_unavailable = False
        self._history_selection: Path | None = None
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
        self._build_history_controls(layout)
        self._build_review_actions(layout)
        layout.addWidget(self._review, 1)
        self.refresh()

    def _build_history_controls(self, layout: QtWidgets.QVBoxLayout) -> None:
        search_row = QtWidgets.QHBoxLayout()
        search_label = QtWidgets.QLabel("Search sessions")
        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Find a session by name")
        self._search.setAccessibleName("Search completed sessions by name")
        search_label.setBuddy(self._search)
        self._search.textChanged.connect(self._apply_search)
        self._search.returnPressed.connect(self._open_selected)
        search_row.addWidget(search_label)
        search_row.addWidget(self._search, 1)
        self._clear_search = QtWidgets.QPushButton("Clear search")
        self._clear_search.setAccessibleName("Clear session name search")
        get_style_manager().style_button(self._clear_search, "ghost")
        self._clear_search.clicked.connect(self._search.clear)
        search_row.addWidget(self._clear_search)
        layout.addLayout(search_row)
        row = QtWidgets.QHBoxLayout()
        self._sessions = QtWidgets.QComboBox()
        self._sessions.setAccessibleName("Completed local sessions")
        self._sessions.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._sessions.setMinimumContentsLength(12)
        self._sessions.currentIndexChanged.connect(self._remember_history_selection)
        row.addWidget(self._sessions, 1)
        for text, name, callback in (("Review", "Review selected completed session", self._open_selected),
                                     ("Refresh", "Refresh local session history", self.refresh),
                                     ("Open Local…", "Open a local session directory", self._review.open_local_session)):
            button = QtWidgets.QPushButton(text)
            button.setAccessibleName(name)
            get_style_manager().style_button(button, "primary" if text == "Review" else "ghost")
            button.clicked.connect(callback)
            row.addWidget(button)
            if text == "Review":
                self._review_button = button
        layout.addLayout(row)
        self._history_status = QtWidgets.QLabel()
        self._history_status.setWordWrap(True)
        self._history_status.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._history_status.setAccessibleName("Session search results")
        get_style_manager().style_label(self._history_status, "muted")
        layout.addWidget(self._history_status)

    def _build_review_actions(self, layout: QtWidgets.QVBoxLayout) -> None:
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

    @property
    def review(self) -> ReviewWindow:
        return self._review

    def refresh(self) -> None:
        """Refresh service-admitted history while retaining search and selection."""
        try:
            self._history = self._review.available_sessions(self._recordings_root, pitcher_name=self._player_filter)
            self._history_unavailable = False
        except OSError:
            logging.getLogger(__name__).warning("Could not refresh local session history", exc_info=True)
            self._history = []
            self._history_unavailable = True
        self._apply_search()

    def _remember_history_selection(self, _index: int) -> None:
        path = self._sessions.currentData()
        if isinstance(path, Path):
            self._history_selection = path

    def _apply_search(self) -> None:
        query = self._search.text().strip().casefold()
        matches = [path for path in self._history if query in path.name.casefold()]
        selected = self._history_selection.absolute() if self._history_selection is not None else None
        with QtCore.QSignalBlocker(self._sessions):
            self._sessions.clear()
            for path in matches:
                self._sessions.addItem(path.name, path)
            if matches:
                index = next((i for i, path in enumerate(matches) if path.absolute() == selected), 0)
                self._sessions.setCurrentIndex(index)
                if self._history_selection is None:
                    self._history_selection = matches[index]
            else:
                placeholder = "No matching sessions" if self._history else "No completed local sessions"
                self._sessions.addItem("Session history unavailable" if self._history_unavailable else placeholder, None)
        self._sessions.setEnabled(bool(matches))
        self._review_button.setEnabled(bool(matches))
        self._clear_search.setEnabled(bool(self._search.text()))
        self._history_status.setText(self._history_message(len(matches)))

    def _history_message(self, matches: int) -> str:
        if self._history_unavailable:
            return "Session history is unavailable. Check the recording folder, then Refresh or use Open Local…"
        if not self._history:
            if self._player_filter is not None:
                return f"No completed sessions recorded for {self._player_filter}. Show all players or use Open Local…"
            return "No completed local sessions. Use Open Local… or finish a recording, then Refresh."
        if not matches:
            return f'No session names match “{self._search.text().strip()}”. Clear search or try another name.'
        count = f"{matches} of {len(self._history)}" if self._search.text().strip() else str(matches)
        message = f"{count} completed session{'s' if len(self._history) != 1 else ''}"
        return message + (f" · Recorded player: {self._player_filter}" if self._player_filter is not None else "")

    def _open_selected(self) -> None:
        path = self._sessions.currentData()
        if path is not None:
            self.open_selection(ReviewSelection(path, pitcher_name=self._player_filter))

    def open_selection(self, selection: ReviewSelection) -> None:
        if not self._review.open_session(selection):
            self._selection_label.setText("Could not open the requested session or pitch. Check its local files and try again.")
            return
        self._player_filter = selection.pitcher_name
        self._history_selection = selection.session_dir
        query = self._search.text().strip().casefold()
        if selection.session_dir is not None and query not in selection.session_dir.name.casefold():
            with QtCore.QSignalBlocker(self._search):
                self._search.clear()
        self._clear_player.setVisible(self._player_filter is not None)
        self.refresh()

    def _selection_changed(self, selection: ReviewSelection) -> None:
        self._selection_label.setText(
            f"Historical: {selection.session_id} · {selection.pitch_id or 'session video'}"
            if selection.session_dir else "Choose a completed local session. Active recording is shown above.")
        self.selection_changed.emit(selection)

    def update_runtime(self, status: RuntimeStatus) -> None:
        if status.sequence < self._runtime.sequence:
            return
        previous_active = self._runtime.active_session_dir
        self._runtime = status
        self._review.update_runtime(status)
        if status.active_session_dir != previous_active:
            self.refresh()

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

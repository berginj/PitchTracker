"""Session loading and navigation coordination for ReviewWindow."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Callable, List, Optional

from PySide6 import QtWidgets

from app.review import ReviewService, SessionLoader
from ui.themes import ask_confirmation, show_message_dialog

logger = logging.getLogger(__name__)


class SessionController:
    """Coordinates session loading, navigation, and deletion.

    This controller owns session list state and navigation index, delegating
    actual file I/O to app.review.SessionLoader / ReviewService.
    """

    def __init__(
        self,
        service: ReviewService,
        *,
        parent_widget: QtWidgets.QWidget,
        on_session_loaded: Callable[[], None],
        on_session_closed: Callable[[], None],
        status_bar: QtWidgets.QStatusBar,
    ) -> None:
        self._service = service
        self._parent = parent_widget
        self._on_session_loaded = on_session_loaded
        self._on_session_closed = on_session_closed
        self._status_bar = status_bar

        self._session_list: List[Path] = []
        self._current_session_index: int = -1

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def session_list(self) -> List[Path]:
        return self._session_list

    @property
    def current_session_index(self) -> int:
        return self._current_session_index

    @property
    def has_session(self) -> bool:
        return self._service.session is not None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_session_dialog(self) -> None:
        """Show dialog to select and open a session."""
        recordings_dir = Path("recordings")
        if not recordings_dir.exists():
            show_message_dialog(
                self._parent,
                "Recordings Not Found",
                f"Recordings directory not found: {recordings_dir}\n\n"
                "Please record at least one session before using Review Mode.",
                tone="warning",
            )
            return

        session_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self._parent,
            "Select Session Directory",
            str(recordings_dir),
            QtWidgets.QFileDialog.Option.ShowDirsOnly,
        )

        if not session_dir:
            return

        self.load_session(Path(session_dir))

    def load_session(self, session_dir: Path) -> None:
        """Load a session for review."""
        try:
            logger.info(f"Loading session: {session_dir}")
            self._status_bar.showMessage(f"Loading session: {session_dir.name}...")
            QtWidgets.QApplication.processEvents()

            self._service.load_session(session_dir)
            self._on_session_loaded()

            session = self._service.session
            self._status_bar.showMessage(
                f"Loaded session: {session.session_id} "
                f"({len(session.pitches)} pitches, {self._service.total_frames} frames)"
            )
            logger.info(f"Session loaded successfully: {session.session_id}")

        except Exception as e:
            logger.exception(f"Failed to load session: {e}")
            show_message_dialog(
                self._parent,
                "Load Error",
                f"Failed to load session:\n{str(e)}",
                tone="error",
            )
            self._status_bar.showMessage("Failed to load session")

    def close_session(self) -> None:
        """Close the current session."""
        self._on_session_closed()
        self._service.close()
        self._status_bar.showMessage("Session closed. Open a session to begin.")
        logger.info("Session closed")

    def review_all_sessions(self) -> None:
        """Load all sessions for sequential review."""
        recordings_dir = Path("recordings")
        if not recordings_dir.exists():
            show_message_dialog(
                self._parent,
                "Recordings Not Found",
                f"Recordings directory not found: {recordings_dir}\n\n"
                "Please record at least one session before using Review Mode.",
                tone="warning",
            )
            return

        self._session_list = SessionLoader.get_available_sessions()

        if not self._session_list:
            show_message_dialog(
                self._parent,
                "No Sessions Found",
                "No recorded sessions found in the recordings directory.",
                tone="info",
            )
            return

        self._current_session_index = 0
        self.load_session(self._session_list[0])
        logger.info(f"Loaded {len(self._session_list)} sessions for review")

    def next_session(self) -> None:
        """Navigate to next session."""
        if not self._session_list or self._current_session_index < 0:
            show_message_dialog(self._parent, "No Sessions", "Use 'Review All Sessions' first.", tone="info")
            return

        if self._current_session_index >= len(self._session_list) - 1:
            show_message_dialog(self._parent, "Last Session", "This is the last session in the list.", tone="info")
            return

        self._current_session_index += 1
        self.load_session(self._session_list[self._current_session_index])

    def previous_session(self) -> None:
        """Navigate to previous session."""
        if not self._session_list or self._current_session_index < 0:
            show_message_dialog(self._parent, "No Sessions", "Use 'Review All Sessions' first.", tone="info")
            return

        if self._current_session_index <= 0:
            show_message_dialog(self._parent, "First Session", "This is the first session in the list.", tone="info")
            return

        self._current_session_index -= 1
        self.load_session(self._session_list[self._current_session_index])

    def delete_current_session(self) -> None:
        """Delete the currently loaded session from disk."""
        if not self._service.session:
            show_message_dialog(self._parent, "No Session", "No session is currently loaded.", tone="warning")
            return

        session = self._service.session
        session_dir = session.session_dir

        if not ask_confirmation(
            self._parent,
            "Delete Session",
            f"Are you sure you want to delete this session?\n\n"
            f"Session: {session.session_id}\n"
            f"Path: {session_dir}\n\n"
            "The session will be moved to a recoverable trash folder.\n"
            "You can restore it manually if needed.",
            confirm_variant="danger",
        ):
            return

        try:
            self.close_session()
            try:
                quarantine_dir = self._quarantine_session(session_dir)
            except FileNotFoundError:
                # Deletion is intentionally idempotent: a session may have
                # been removed by another review window or an earlier retry.
                quarantine_dir = None
                logger.warning("Session %s was already absent from %s", session.session_id, session_dir)

            if quarantine_dir is not None:
                logger.info("Quarantined session %s at %s", session_dir, quarantine_dir)
                show_message_dialog(
                    self._parent,
                    "Session Moved to Trash",
                    f"Session {session.session_id} was moved to:\n{quarantine_dir}\n\n"
                    "The files remain recoverable until the trash folder is cleared.",
                    tone="success",
                )
            else:
                show_message_dialog(
                    self._parent,
                    "Session Already Removed",
                    f"Session {session.session_id} was already absent from disk.\n\n"
                    "It will be removed from this review list.",
                    tone="warning",
                )

            if self._session_list:
                matching_index = next(
                    (
                        index
                        for index, path in enumerate(self._session_list)
                        if path.resolve() == session_dir.resolve()
                    ),
                    None,
                )
                if matching_index is not None:
                    self._session_list.pop(matching_index)
                    self._current_session_index = matching_index

                if self._session_list:
                    if self._current_session_index >= len(self._session_list):
                        self._current_session_index = len(self._session_list) - 1
                    self.load_session(self._session_list[self._current_session_index])
                else:
                    self._current_session_index = -1
                    self._status_bar.showMessage("No more sessions to review")

        except Exception as e:
            logger.exception(f"Failed to delete session: {e}")
            show_message_dialog(
                self._parent,
                "Delete Error",
                f"Failed to delete session:\n{str(e)}",
                tone="error",
            )

    @staticmethod
    def _quarantine_session(session_dir: Path) -> Path:
        """Move a session aside instead of irreversibly deleting recordings."""
        resolved_session = session_dir.resolve()
        if not resolved_session.is_dir():
            raise FileNotFoundError(f"Session directory not found: {resolved_session}")

        trash_root = resolved_session.parent / ".pitchtracker-trash"
        trash_root.mkdir(parents=False, exist_ok=True)
        quarantine_dir = trash_root / f"{resolved_session.name}-{time.time_ns()}"
        shutil.move(str(resolved_session), str(quarantine_dir))
        return quarantine_dir

    # ------------------------------------------------------------------
    # Navigation state helpers
    # ------------------------------------------------------------------

    def get_navigation_state(self) -> Optional[str]:
        """Return status string like 'Session 2/5' or None."""
        if self._session_list and self._current_session_index >= 0:
            total = len(self._session_list)
            current = self._current_session_index + 1
            return f"Session {current}/{total}"
        return None

    def can_go_previous(self) -> bool:
        return bool(self._session_list) and self._current_session_index > 0

    def can_go_next(self) -> bool:
        return bool(self._session_list) and self._current_session_index < len(self._session_list) - 1

"""Hosted page adapters preserve the existing controllers and owned operations."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from PySide6 import QtCore, QtWidgets

from app.services.orchestrator.runtime_status import RuntimeStatus
from app.services.setup_workflow.runtime_access import admission_status
from ui.themes import get_style_manager, show_message_dialog
from ui.setup.stereo_setup_window import StereoSetupWindow


class SetupPage(QtWidgets.QWidget):
    completed = QtCore.Signal()
    busy_changed = QtCore.Signal(bool)

    def __init__(self, config_path: Path, backend: str,
                 wizard_factory: Callable[[], StereoSetupWindow] | None = None):
        super().__init__()
        self._config_path, self._backend = config_path, backend
        self._factory = wizard_factory
        self._wizard: StereoSetupWindow | None = None
        self._runtime = RuntimeStatus()
        self._command_pending = False
        self._shutdown_complete = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self._notice = QtWidgets.QLabel()
        self._notice.setWordWrap(True)
        layout.addWidget(self._notice)
        self._open = QtWidgets.QPushButton("Open Guided Setup")
        self._open.setAccessibleName("Open guided rig setup")
        get_style_manager().style_button(self._open, "primary")
        self._open.clicked.connect(self.open_guided_setup)
        layout.addWidget(self._open)
        self._content = QtWidgets.QStackedWidget()
        self._content.setMinimumSize(0, 0)
        self._content.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
        summary = QtWidgets.QLabel(
            "Cameras → Image checks → Calibration → Field and regions → Ready\n\n"
            "Open guided setup to inspect or edit saved settings. Camera acquisition remains explicit.\n"
            "Passing checks permits research recording with estimated measurements."
        )
        summary.setWordWrap(True)
        self._content.addWidget(summary)
        layout.addWidget(self._content, 1)
        self.update_runtime(self._runtime)

    @property
    def wizard(self):
        return self._wizard

    def operation_busy(self) -> bool:
        return self._wizard is not None and self._wizard.operation_busy()

    def update_runtime(self, status: RuntimeStatus, *, command_pending: bool = False) -> None:
        self._runtime = status
        self._command_pending = command_pending
        blocked = command_pending or status.owns_capture or status.owns_recording or status.pending_operation is not None
        self._open.setEnabled(not blocked)
        self._open.setVisible(not blocked and self._wizard is None)
        if self._wizard is not None:
            self._wizard.setEnabled(not blocked)
        self._notice.setText(
            "Runtime capture owns the rig. Setup is view-only; stop preview explicitly in Live before editing."
            if blocked else "Valid edits save immediately. Recheck affected stages before recording."
        )

    def open_guided_setup(self) -> None:
        if self._command_pending or self._runtime.owns_capture or self._runtime.owns_recording or self._runtime.pending_operation:
            return
        if self._wizard is not None:
            self._content.setCurrentWidget(self._wizard)
            return
        try:
            if self._factory is None:
                from app.services.setup_workflow import SetupWorkflowService
                if not admission_status(Path("calibration/rigs")).permits_edit:
                    raise RuntimeError("Runtime capture still owns the rig")
                workflow = SetupWorkflowService(self._config_path, backend=self._backend,
                                                preserve_runtime_capture=True)
                wizard = StereoSetupWindow(workflow=workflow)
            else:
                wizard = self._factory()
            wizard.host_in_workspace(self)
            wizard.workspace_completed.connect(self.completed)
            wizard.operation_busy_changed.connect(self.busy_changed)
            self._wizard = wizard
            self._content.addWidget(wizard)
            self._content.setCurrentWidget(wizard)
            self._open.hide()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Workspace setup could not open")
            show_message_dialog(self, "Setup unavailable", str(exc), tone="warning")

    def shutdown_for_workspace(self) -> bool:
        if self._shutdown_complete:
            return True
        self._shutdown_complete = self._wizard is None or self._wizard.shutdown_for_workspace()
        return self._shutdown_complete


class SessionsPage(QtWidgets.QWidget):
    selection_changed = QtCore.Signal(object)
    exit_requested = QtCore.Signal()

    def __init__(self):
        super().__init__()
        from ui.review.review_window import ReviewWindow
        self._shutdown_complete = False
        self._selection_label = QtWidgets.QLabel("Historical selection is separate from the active session.")
        self._selection_label.setWordWrap(True)
        self._review = ReviewWindow()
        self._review.host_in_workspace(self)
        self._review.selection_changed.connect(self.selection_changed)
        self._review.exit_requested.connect(self.exit_requested)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._selection_label)
        layout.addWidget(self._review, 1)

    @property
    def review(self):
        return self._review

    def browse_player(self, player_name: str) -> None:
        # Filtering and attribution migration belong to UX-06; do not guess from names.
        self._selection_label.setText(f"Browsing player: {player_name}. Open a recorded session to review it.")

    def shutdown_for_workspace(self) -> bool:
        if not self._shutdown_complete:
            self._shutdown_complete = self._review.shutdown_for_workspace()
        return self._shutdown_complete


class PlayersPage(QtWidgets.QScrollArea):
    player_browsed = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        from ui.team.team_manager import TeamManager
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._roster = TeamManager(browse_only=True)
        self._roster.setParent(self, QtCore.Qt.WindowType.Widget)
        self._roster.setMinimumSize(0, 0)
        self._roster.pitcher_selected.connect(self.player_browsed)
        self.setWidget(self._roster)

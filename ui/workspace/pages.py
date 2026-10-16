"""Hosted page adapters preserve the existing controllers and owned operations."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from PySide6 import QtCore, QtWidgets

from app.services.orchestrator.runtime_status import RuntimeStatus
from app.services.setup_workflow.runtime_access import admission_status
from ui.themes import get_style_manager, show_message_dialog
from ui.setup.stereo_setup_window import StereoSetupWindow
from ui.workspace.sessions_page import SessionsPage as SessionsPage

__all__ = ["SetupPage", "SessionsPage", "PlayersPage"]


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
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        self._notice = QtWidgets.QLabel()
        self._notice.setWordWrap(True)
        layout.addWidget(self._notice)
        self._saved_status = QtWidgets.QLabel("Saved setup details appear when guided setup opens. Navigation does not publish a rig.")
        self._saved_status.setWordWrap(True)
        self._saved_status.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(self._saved_status)
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
            if blocked else "Edits save immediately. Recheck changed stages, then Finish to publish the rig."
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
            wizard.presentation_changed.connect(self._refresh_saved_status)
            self._wizard = wizard
            self._content.addWidget(wizard)
            self._content.setCurrentWidget(wizard)
            self._open.hide()
            self._refresh_saved_status()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Workspace setup could not open")
            show_message_dialog(self, "Setup unavailable", str(exc), tone="warning")

    def _refresh_saved_status(self) -> None:
        if self._wizard is not None:
            view = self._wizard.presentation()
            blockers = view.blockers[0] if view.blockers else ""
            if len(view.blockers) > 1:
                blockers += f" (+{len(view.blockers) - 1} checks)"
            self._saved_status.setText(f"{view.stage} · Saved revision {view.generation} · {view.readiness}"
                                       + (f" · Next: {blockers}" if blockers else " · Estimated research readiness only."))
            self._saved_status.setAccessibleDescription("; ".join(view.blockers))

    def shutdown_for_workspace(self) -> bool:
        if self._shutdown_complete:
            return True
        self._shutdown_complete = self._wizard is None or self._wizard.shutdown_for_workspace()
        return self._shutdown_complete


class PlayersPage(QtWidgets.QScrollArea):
    player_browsed = QtCore.Signal(str)
    active_pitcher_requested = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        from ui.team.team_manager import TeamManager
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._roster = TeamManager(browse_only=True)
        self._roster.setParent(self, QtCore.Qt.WindowType.Widget)
        self._roster.setMinimumSize(0, 0)
        self._roster.pitcher_selected.connect(self.player_browsed)
        self._roster.active_pitcher_requested.connect(self.active_pitcher_requested)
        self.setWidget(self._roster)

    def update_runtime(self, status: RuntimeStatus, *, command_pending: bool = False) -> None:
        self._roster.set_active_context(status.pitcher, permitted=not command_pending and not status.pending_operation
                                        and status.recording_phase != "finalizing")

"""Persistent application shell; pages own presentation and services own runtime state."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from collections.abc import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from launcher import LauncherWindow
from launcher_threads import StartupValidationThread
from app.qt_pipeline_service import QtPipelineService
from app.services.orchestrator.runtime_status import RuntimeStatus
from ui.coaching.coach_window import CoachWindow
from ui.setup.stereo_setup_window import StereoSetupWindow
from ui.themes import get_style_manager, show_choice_dialog, show_message_dialog
from ui.workspace.contracts import NavigationContext, ReviewSelection, SessionPreparation
from ui.workspace.pages import PlayersPage, SessionsPage, SetupPage
from ui.workspace.shutdown import PipelineShutdownThread
from ui.workspace.unavailable_live import UnavailableLivePage
from ui.workspace.session_presentation import session_presentation
from exceptions import ConfigError


class WorkspaceWindow(LauncherWindow):
    """Reuse startup/update ownership while replacing role-window hopping with pages."""

    def __init__(self, *, backend: str = "uvc", config_path: Path | None = None,
                 background_tasks: bool = True, validation_service=None,
                 pipeline: QtPipelineService | None = None,
                 setup_factory: Callable[[], StereoSetupWindow] | None = None):
        self._pipeline = pipeline
        self._setup_factory = setup_factory
        self._pages: dict[str, QtWidgets.QWidget] = {}
        self._context = NavigationContext()
        self._runtime = RuntimeStatus()
        self._preparation = SessionPreparation()
        self._exit_confirmed = False
        self._pipeline_closed = False
        self._shutdown_worker: PipelineShutdownThread | None = None
        self._exit_failure: str | None = None
        self._retry_scheduled = False
        self._primary_action = "prepare"
        super().__init__(backend=backend, config_path=config_path, background_tasks=background_tasks,
                         validation_service=validation_service)
        self.resize(1366, 768)

    @property
    def pipeline_service(self) -> QtPipelineService:
        assert self._pipeline is not None
        return self._pipeline

    @property
    def navigation_context(self) -> NavigationContext:
        return self._context

    def page(self, name: str) -> QtWidgets.QWidget | None:
        return self._pages.get(name)

    def _build_ui(self) -> None:
        self._close_retry_timer = QtCore.QTimer(self)
        self._close_retry_timer.setSingleShot(True)
        self._close_retry_timer.timeout.connect(self._retry_close)
        shell = QtWidgets.QWidget()
        shell.setObjectName("WorkspaceShell")
        row = QtWidgets.QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        rail = QtWidgets.QFrame()
        get_style_manager().style_panel(rail, "normal")
        rail.setFixedWidth(168)
        self._rail = rail
        nav = QtWidgets.QVBoxLayout(rail)
        brand = QtWidgets.QLabel("PitchTracker")
        get_style_manager().style_label(brand, "sectionTitle")
        nav.addWidget(brand)
        self._nav: dict[str, QtWidgets.QPushButton] = {}
        for name, label in (("live", "Live"), ("sessions", "Sessions"), ("players", "Players"), ("setup", "Setup")):
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.setAccessibleName(f"Navigate to {label}")
            button.setMinimumHeight(40)
            button.clicked.connect(lambda _checked=False, name=name: self.navigate(name))
            nav.addWidget(button)
            self._nav[name] = button
        # Existing launcher readiness callbacks use these aliases; they remain navigation.
        self._coach_button, self._review_button, self._setup_button = self._nav["live"], self._nav["sessions"], self._nav["setup"]
        nav.addStretch()
        settings = QtWidgets.QPushButton("Settings")
        settings.setAccessibleName("Workspace settings")
        settings.clicked.connect(self._show_settings)
        nav.addWidget(settings)
        help_button = QtWidgets.QPushButton("Help")
        help_button.setAccessibleName("Workspace help")
        help_button.clicked.connect(self._show_help)
        nav.addWidget(help_button)
        row.addWidget(rail)
        body = QtWidgets.QWidget()
        column = QtWidgets.QVBoxLayout(body)
        column.setContentsMargins(12, 12, 12, 12)
        self._header = QtWidgets.QFrame()
        get_style_manager().style_panel(self._header, "normal")
        header = QtWidgets.QVBoxLayout(self._header)
        identity = QtWidgets.QHBoxLayout()
        self._identity = QtWidgets.QLabel("No active session")
        self._identity.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._identity.setWordWrap(True)
        identity.addWidget(self._identity, 1)
        self._status = QtWidgets.QLabel("Idle")
        self._status.setWordWrap(True)
        identity.addWidget(self._status)
        header.addLayout(identity)
        actions = QtWidgets.QHBoxLayout()
        self._primary = QtWidgets.QPushButton("Prepare Session")
        self._primary.setAccessibleName("Primary session action")
        self._primary.setMinimumHeight(get_style_manager().theme.button_height_md)
        get_style_manager().style_button(self._primary, "primary")
        self._primary.clicked.connect(self._perform_primary_action)
        self._end = QtWidgets.QPushButton("End Session")
        self._end.setAccessibleName("End active workspace session")
        self._end.clicked.connect(lambda: self._perform_session_action("end"))
        self._stop_preview = QtWidgets.QPushButton("Stop Preview")
        self._stop_preview.setAccessibleName("Stop runtime preview explicitly")
        self._stop_preview.clicked.connect(lambda: self._perform_session_action("stop_preview"))
        self._new_session = QtWidgets.QPushButton("New Session")
        self._new_session.setAccessibleName("Prepare another workspace session")
        self._new_session.clicked.connect(lambda: self._perform_session_action("prepare"))
        self._return_live = QtWidgets.QPushButton("Return to Live")
        self._return_live.setAccessibleName("Return to active Live page")
        self._return_live.clicked.connect(lambda: self.navigate("live"))
        actions.addWidget(self._primary)
        actions.addWidget(self._end)
        actions.addWidget(self._stop_preview)
        actions.addWidget(self._new_session)
        actions.addStretch()
        actions.addWidget(self._return_live)
        header.addLayout(actions)
        self._detail = QtWidgets.QLabel()
        self._detail.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._detail.setWordWrap(True)
        header.addWidget(self._detail)
        self._progress = QtWidgets.QProgressBar()
        self._progress.setAccessibleName("Session operation in progress")
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setMaximumHeight(6)
        header.addWidget(self._progress)
        column.addWidget(self._header)
        column.addWidget(self._build_warning_banner())
        self._stack = QtWidgets.QStackedWidget()
        self._stack.setMinimumSize(0, 0)
        self._stack.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
        column.addWidget(self._stack, 1)
        row.addWidget(body, 1)
        self.setCentralWidget(shell)
        self._pipeline = self._pipeline or QtPipelineService(backend=self._backend, parent=self)
        self._pipeline.runtime_status_changed.connect(self._on_runtime_status)
        self._live: CoachWindow | UnavailableLivePage
        try:
            self._live = CoachWindow(backend=self._backend, config_path=self._config_path,
                                     service=self._pipeline, warm_cameras=False)
        except (ConfigError, OSError) as exc:
            import logging
            logging.getLogger(__name__).exception("Workspace Live configuration could not load")
            self._live = UnavailableLivePage(self._pipeline, str(exc))
        self._live.host_in_workspace(self._stack)
        self._live.preparation_changed.connect(self._on_preparation_changed)
        self._live.session_operation_changed.connect(self._on_session_operation_changed)
        self._live.review_requested.connect(self._review_finalized_session)
        self._live.setup_requested.connect(lambda: self.navigate("setup"))
        self._live.exit_requested.connect(self.close)
        self._pages["live"] = self._live
        self._stack.addWidget(self._live)
        self._on_runtime_status(self._pipeline.runtime_status())
        self.navigate("live")

    def _set_role_buttons_enabled(self, enabled: bool, *, review_enabled=None) -> None:
        # Pages stay inspectable while readiness checks run. Runtime commands remain gated.
        self._environment_ready = enabled
        if hasattr(self, "_primary"):
            self._render_status()

    def _start_environment_validation(self) -> None:
        if self._validation_thread is not None or self._close_requested:
            return
        # Launching the workspace alone does not authorize camera discovery/acquisition.
        self._validation_thread = StartupValidationThread(self._validation_service, check_cameras=False)
        self._validation_thread.validation_complete.connect(self._on_validation_complete)
        self._validation_thread.validation_failed.connect(self._on_validation_failed)
        self._validation_thread.finished.connect(self._on_validation_finished)
        self._validation_thread.start()

    def _on_validation_finished(self) -> None:
        thread = self._validation_thread
        if thread is not None:
            thread.wait()
            self._validation_thread = None
            thread.deleteLater()
        if self._close_requested and not self._exit_failure:
            self.close()

    def _on_updates_finished(self) -> None:
        if self._close_requested and not self._exit_failure:
            self.close()

    def navigate(self, name: str) -> bool:
        if name not in self._nav or self._exit_confirmed:
            return False
        setup = self._pages.get("setup")
        if self._context.page == "setup" and name != "setup" and isinstance(setup, SetupPage) and setup.operation_busy():
            self._detail.setText("Finish or explicitly cancel the setup operation before leaving Setup.")
            self._mark_navigation()
            return False
        if name not in self._pages:
            page: QtWidgets.QWidget
            if name == "sessions":
                root = self._live.recordings_directory() if isinstance(self._live, CoachWindow) else Path("recordings")
                page = SessionsPage(root)
                page.update_runtime(self._runtime)
                page.selection_changed.connect(self._on_review_selection)
                page.exit_requested.connect(self.close)
            elif name == "players":
                page = PlayersPage()
                page.player_browsed.connect(self._on_player_browsed)
            else:
                page = SetupPage(self._config_path or Path("configs/default.yaml"), self._backend, self._setup_factory)
                page.completed.connect(lambda: self.navigate("live"))
                page.busy_changed.connect(lambda _busy: self._render_status())
                page.update_runtime(self._runtime, command_pending=self._live.session_command_busy())
            self._pages[name] = page
            self._stack.addWidget(page)
        self._context = replace(self._context, page=name)
        self._stack.setCurrentWidget(self._pages[name])
        get_style_manager().set_mode("setup" if name == "setup" else "production")
        self._mark_navigation()
        return True

    def _mark_navigation(self) -> None:
        for name, button in self._nav.items():
            button.setChecked(name == self._context.page)
            get_style_manager().style_button(button, "primary" if name == self._context.page else "ghost")
        self._return_live.setVisible(self._context.page != "live")

    def _on_player_browsed(self, player: str) -> None:
        self._context = replace(self._context, browsed_player=player)
        if self.navigate("sessions"):
            sessions = self._pages["sessions"]
            assert isinstance(sessions, SessionsPage)
            sessions.browse_player(player)

    def _on_review_selection(self, selection: ReviewSelection) -> None:
        self._context = replace(self._context, review=selection)

    def _on_preparation_changed(self, preparation: SessionPreparation) -> None:
        self._preparation = preparation
        self._render_status()

    def _on_runtime_status(self, status: RuntimeStatus) -> None:
        if status.sequence < self._runtime.sequence:
            return
        self._runtime = status
        self._live.apply_runtime_status(status)
        self._on_session_operation_changed()

    def _on_session_operation_changed(self) -> None:
        sessions = self._pages.get("sessions")
        if isinstance(sessions, SessionsPage):
            sessions.update_runtime(self._runtime)
        setup = self._pages.get("setup")
        if isinstance(setup, SetupPage):
            setup.update_runtime(self._runtime, command_pending=self._live.session_command_busy())
        self._render_status()

    def _render_status(self) -> None:
        runtime = self._runtime
        presentation = session_presentation(runtime, self._preparation, self._live.session_operation())
        action = presentation.action
        self._status.setText(presentation.label)
        get_style_manager().style_status_indicator(self._status, presentation.tone)
        self._primary_action = action
        self._primary.setText(presentation.primary)
        if runtime.session_id:
            identity = f"Active: {runtime.session_id} · {self._preparation.pitcher_name}"
        elif self._preparation.prepared:
            identity = f"Prepared: {self._preparation.session_name} · {self._preparation.pitcher_name}"
        elif runtime.finalized_session:
            identity = f"Last completed: {runtime.finalized_session.session_id}"
        else:
            identity = "No active session"
        self._identity.setText(identity)
        self._detail.setText(presentation.detail)
        setup = self._pages.get("setup")
        setup_busy = isinstance(setup, SetupPage) and setup.operation_busy()
        ready = getattr(self, "_environment_ready", False)
        enabled = not presentation.pending and not setup_busy and not self._exit_confirmed
        self._primary.setEnabled(enabled and (ready or action in {"review", "end", "stop_preview", "pause", "resume"})
                                 and self._live.configuration_available)
        self._end.setVisible(runtime.owns_recording and action != "end")
        self._end.setEnabled(enabled)
        self._stop_preview.setVisible(runtime.owns_capture and not runtime.owns_recording and action != "stop_preview")
        self._stop_preview.setEnabled(enabled)
        self._new_session.setVisible(action == "review")
        self._new_session.setEnabled(enabled and ready and self._live.configuration_available)
        self._progress.setVisible(presentation.pending or self._exit_confirmed and not self._exit_failure)
        if self._exit_confirmed and not self._exit_failure:
            self._primary.setText("Exiting…")
            self._detail.setText("Waiting for admitted commands, accepted pitches and owned workers to finish.")
        if self._exit_failure:
            self._primary.setText("Retry Exit")
            self._primary.setEnabled(self._shutdown_worker is None)
            self._detail.setText(f"Shutdown incomplete; ownership retained. {self._exit_failure}")

    def _perform_primary_action(self) -> None:
        if self._exit_failure:
            self.close()
        elif self._primary_action == "review":
            self._review_finalized_session()
        else:
            self._perform_session_action(self._primary_action)

    def _review_finalized_session(self) -> None:
        completed = self._runtime.finalized_session
        if (completed is None or self._runtime.owns_recording or self._runtime.pending_operation
                or self._runtime.failure or self._live.session_command_busy()):
            return
        if self.navigate("sessions"):
            sessions = self._pages["sessions"]
            assert isinstance(sessions, SessionsPage)
            sessions.open_selection(ReviewSelection(completed.session_dir, completed.session_id))

    def _perform_session_action(self, action: str) -> None:
        setup = self._pages.get("setup")
        if (self._exit_confirmed or self._runtime.pending_operation or self._live.session_command_busy()
                or isinstance(setup, SetupPage) and setup.operation_busy()):
            return
        if action == "prepare" and not self.navigate("live"):
            return
        try:
            self._live.perform_session_action(action)
        except Exception as exc:
            show_message_dialog(self, "Session action failed", str(exc), tone="error")

    def _show_settings(self) -> None:
        # Rig settings stay in Setup; update preferences retain their existing persistence.
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Workspace settings")
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(self._build_footer())
        rig = QtWidgets.QPushButton("Open Rig Setup")
        rig.setAccessibleName("Open rig setup from settings")

        def open_setup() -> None:
            dialog.accept()
            self.navigate("setup")
        rig.clicked.connect(open_setup)
        layout.addWidget(rig)
        close = QtWidgets.QPushButton("Close")
        close.setAccessibleName("Close workspace settings")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _show_help(self) -> None:
        show_message_dialog(self, "Workspace help",
                            "Live: explicitly prepare and record a session.\n"
                            "Sessions: open completed local recordings. Players: browse the roster.\n"
                            "Setup: stop preview before editing the rig; camera actions are explicit.\n"
                            "Operator guide: docs/OPERATOR_RUNBOOK.md", tone="info")

    def may_install_update(self) -> bool:
        # A persistent workspace is visible even when a workflow owns resources.
        setup = self._pages.get("setup")
        sessions = self._pages.get("sessions")
        return (not self._runtime.owns_capture and not self._runtime.owns_recording
                and self._runtime.pending_operation is None and self._validation_thread is None
                and not self._live.session_command_busy()
                and not self._exit_confirmed and self._context.page == "live"
                and not (isinstance(setup, SetupPage) and setup.operation_busy())
                and not (isinstance(sessions, SessionsPage) and sessions.review.selection().session_dir is not None))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        if hasattr(self, "_rail"):
            self._rail.setFixedWidth(136 if event.size().width() <= 1024 else 168)
        super().resizeEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._exit_confirmed:
            if self._runtime.owns_recording:
                choice = show_choice_dialog(
                    self, "Session active", "End the session and exit?",
                    choices=(("end", "End Session and Exit", "primary", QtWidgets.QMessageBox.ButtonRole.AcceptRole),
                             ("cancel", "Cancel", "ghost", QtWidgets.QMessageBox.ButtonRole.RejectRole)), default_choice="cancel")
                if choice != "end":
                    event.ignore()
                    return
            self._exit_confirmed = True
            self._live.stop_updates()
        self._close_requested = True
        for button in self._nav.values():
            button.setEnabled(False)
        updates_done = self._update_controller.begin_shutdown()
        if self._validation_thread is not None:
            self._validation_thread.cancel()
        pages_done = True
        for name in ("setup", "sessions"):
            page = self._pages.get(name)
            if isinstance(page, (SetupPage, SessionsPage)) and not page.shutdown_for_workspace():
                pages_done = False
        commands_done = self._live.begin_session_shutdown()
        if commands_done and not self._pipeline_closed and self._shutdown_worker is None:
            self._exit_failure = None
            self._shutdown_worker = PipelineShutdownThread(self.pipeline_service, self)
            self._shutdown_worker.finished.connect(self._on_pipeline_shutdown_finished)
            self._shutdown_worker.start()
        self._render_status()
        if not commands_done or not self._pipeline_closed or not pages_done or self._validation_thread is not None or not updates_done:
            event.ignore()
            if not self._exit_failure and not self._retry_scheduled:
                self._retry_scheduled = True
                self._close_retry_timer.start(100)
            return
        event.accept()

    def _retry_close(self) -> None:
        self._retry_scheduled = False
        if not self._exit_failure:
            self.close()

    def _on_pipeline_shutdown_finished(self) -> None:
        worker = self._shutdown_worker
        assert worker is not None
        worker.wait()
        self._exit_failure = worker.error
        self._pipeline_closed = worker.error is None
        self._shutdown_worker = None
        worker.deleteLater()
        self._render_status()
        if self._pipeline_closed:
            self.close()

    def _launch_stereo_setup(self):
        self.navigate("setup")

    def _launch_coaching(self):
        self.navigate("live")

    def _launch_review(self):
        self.navigate("sessions")

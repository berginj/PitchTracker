"""Coaching window for day-to-day pitching sessions."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.qt_pipeline_service import QtPipelineService
from configs.app_state import load_state, save_state
from configs.settings import load_config
from ui.coaching.dialogs import SessionStartDialog
from ui.coaching.game_state_manager import GameStateManager
from ui.coaching.session_history_tracker import SessionHistoryTracker
from ui.coaching.widgets import CompactFatigueIndicator
from ui.coaching.widgets.mode_widgets import (
    BroadcastViewWidget,
    GameModeWidget,
    SessionProgressionWidget,
)
from ui.themes import ask_confirmation, get_style_manager, show_choice_dialog, show_message_dialog

logger = logging.getLogger(__name__)


class CoachWindow(QtWidgets.QMainWindow):
    """Coaching dashboard for fast pitching session management.

    Designed for coaches to:
    - Start sessions quickly (<10 seconds)
    - Track pitches in real-time
    - View live metrics and visualizations
    - Review session summaries
    - Export for player review
    """

    def __init__(
        self,
        backend: str = "uvc",
        config_path: Optional[Path] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("PitchTracker - Coaching Session")
        self.resize(1400, 900)
        self._style_manager = get_style_manager()

        # Load configuration
        if config_path is None:
            config_path = Path("configs/default.yaml")
        self._config_path = config_path
        self._config = load_config(config_path)

        # Initialize Qt-safe pipeline service (handles thread-safe callbacks)
        self._service = QtPipelineService(backend=backend, parent=self)

        # Session state
        self._session_active = False
        self._pitch_count = 0
        self._session_name = ""
        self._pitcher_name = ""

        # Camera settings (load from saved state or use defaults)
        state = load_state()
        self._camera_width = state.get("coaching_width", 640)
        self._camera_height = state.get("coaching_height", 480)
        self._camera_fps = state.get("coaching_fps", 30)
        self._camera_color_mode = state.get("coaching_color_mode", True)

        # Build UI
        self._build_ui()

        # Preview timer
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start(33)  # ~30 FPS

        # Metrics update timer
        self._metrics_timer = QtCore.QTimer()
        self._metrics_timer.timeout.connect(self._update_metrics)
        self._metrics_timer.start(100)  # 10 Hz

        # Last known pitch count
        self._last_pitch_count = 0

        # Connect pitch detection signals (thread-safe communication from worker threads)
        self._service.pitch_started.connect(self._on_pitch_started)
        self._service.pitch_ended.connect(self._on_pitch_ended)

        # Proactively warm camera cache in background for faster dialog opening
        self._warm_camera_cache_async()

    def _build_ui(self) -> None:
        """Build coaching dashboard UI."""
        # Session info bar at top
        session_bar = self._build_session_bar()

        # Main content: camera views + metrics
        main_content = self._build_main_content()

        # Control buttons at bottom
        controls = self._build_controls()

        # Status bar
        self._status_label = QtWidgets.QLabel("Ready. Click 'Start Session' to begin.")
        self._style_manager.style_status_indicator(self._status_label, "info")

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(session_bar)
        layout.addWidget(main_content, 1)  # Takes most space
        layout.addWidget(controls)
        layout.addWidget(self._status_label)

        container = QtWidgets.QWidget()
        container.setObjectName("CoachShell")
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _build_session_bar(self) -> QtWidgets.QWidget:
        """Build session information bar."""
        # Session name
        self._session_label = QtWidgets.QLabel("Session: <not started>")
        self._style_manager.style_label(self._session_label, "pageTitle")

        # Pitcher name
        self._pitcher_label = QtWidgets.QLabel("Pitcher: <not selected>")
        self._style_manager.style_label(self._pitcher_label, "muted")

        # Pitch count
        self._pitch_count_label = QtWidgets.QLabel("Pitches: 0")
        self._style_manager.style_label(self._pitch_count_label, "metricAccent")

        # Fatigue indicator (compact version for header)
        self._fatigue_indicator = CompactFatigueIndicator()
        self._fatigue_indicator.setToolTip("Fatigue Monitor - Score and status")

        # Recording indicator
        self._recording_indicator = QtWidgets.QLabel("● Recording")
        self._recording_indicator.setText("Recording")
        self._style_manager.style_status_indicator(self._recording_indicator, "error")
        self._recording_indicator.hide()

        # Separator labels (also need black color)
        sep1 = QtWidgets.QLabel("|")
        self._style_manager.style_label(sep1, "muted")
        sep2 = QtWidgets.QLabel("|")
        self._style_manager.style_label(sep2, "muted")
        sep3 = QtWidgets.QLabel("|")
        self._style_manager.style_label(sep3, "muted")

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(self._session_label)
        layout.addWidget(sep1)
        layout.addWidget(self._pitcher_label)
        layout.addWidget(sep2)
        layout.addWidget(self._pitch_count_label)
        layout.addWidget(sep3)
        layout.addWidget(self._fatigue_indicator)
        layout.addStretch()
        layout.addWidget(self._recording_indicator)

        widget = QtWidgets.QWidget()
        widget.setProperty("surface", "card")
        self._style_manager.polish(widget)
        widget.setLayout(layout)
        return widget

    def _build_main_content(self) -> QtWidgets.QWidget:
        """Build main content area with mode switching."""
        # Mode selector toolbar
        mode_toolbar = QtWidgets.QFrame()
        self._style_manager.style_panel(mode_toolbar, "subtle")
        mode_toolbar_layout = QtWidgets.QHBoxLayout()
        mode_toolbar_layout.setContentsMargins(18, 14, 18, 14)
        mode_toolbar_layout.setSpacing(12)

        mode_label = QtWidgets.QLabel("View Mode:")
        self._style_manager.style_label(mode_label, "eyebrow")
        mode_toolbar_layout.addWidget(mode_label)

        self._mode_selector = QtWidgets.QComboBox()
        self._style_manager.style_input(self._mode_selector)
        self._mode_selector.addItems([
            "Broadcast View",
            "Session Progression",
            "Game Mode"
        ])
        self._mode_selector.currentIndexChanged.connect(self._on_mode_changed)
        mode_toolbar_layout.addWidget(self._mode_selector)

        mode_toolbar_layout.addStretch()
        mode_toolbar.setLayout(mode_toolbar_layout)

        # Initialize session history tracker
        self._session_tracker = SessionHistoryTracker()

        # Initialize game state manager
        self._game_state_mgr = GameStateManager()

        # Create mode stack
        self._mode_stack = QtWidgets.QStackedWidget()

        # Create all 3 modes
        self._broadcast_mode = BroadcastViewWidget()
        self._progression_mode = SessionProgressionWidget(self._session_tracker)
        self._game_mode = GameModeWidget(self._game_state_mgr)

        self._mode_stack.addWidget(self._broadcast_mode)
        self._mode_stack.addWidget(self._progression_mode)
        self._mode_stack.addWidget(self._game_mode)

        # Load last mode from settings
        state = load_state()
        last_mode = state.get("last_coaching_mode", 0)
        self._mode_selector.setCurrentIndex(int(last_mode))

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(mode_toolbar)
        layout.addWidget(self._mode_stack, 1)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget

    def _on_mode_changed(self, index: int) -> None:
        """Handle mode selection change.

        Args:
            index: Selected mode index (0=Broadcast, 1=Progression, 2=Game)
        """
        # Preserve camera selection across modes
        current_mode = self._mode_stack.currentWidget()
        camera = current_mode.get_current_camera_selection()

        # Switch mode
        self._mode_stack.setCurrentIndex(index)

        # Restore camera selection in new mode
        new_mode = self._mode_stack.currentWidget()
        new_mode.set_camera_selection(camera)

        # Save preference to settings
        state = load_state()
        state["last_coaching_mode"] = index
        save_state(state)

        mode_names = ["Broadcast View", "Session Progression", "Game Mode"]
        logger.debug(f"Switched to {mode_names[index]}")

    def _build_controls(self) -> QtWidgets.QWidget:
        """Build control buttons."""
        self._setup_button = QtWidgets.QPushButton("Start Session")
        self._setup_button.setMinimumHeight(50)
        self._style_manager.style_button(self._setup_button, "primary")
        self._setup_button.clicked.connect(self._setup_session)

        self._start_recording_button = QtWidgets.QPushButton("▶ Start Recording")
        self._start_recording_button.setMinimumHeight(50)
        self._start_recording_button.setText("Start Recording")
        self._style_manager.style_button(self._start_recording_button, "success")
        self._start_recording_button.setEnabled(False)
        self._start_recording_button.clicked.connect(self._start_recording)

        self._pause_button = QtWidgets.QPushButton("⏸ Pause")
        self._pause_button.setMinimumHeight(50)
        self._pause_button.setText("Pause")
        self._style_manager.style_button(self._pause_button, "default")
        self._pause_button.setEnabled(False)
        self._pause_button.clicked.connect(self._pause_session)

        self._end_button = QtWidgets.QPushButton("⏹ End Session")
        self._end_button.setMinimumHeight(50)
        self._end_button.setText("End Session")
        self._style_manager.style_button(self._end_button, "danger")
        self._end_button.setEnabled(False)
        self._end_button.clicked.connect(self._end_session)

        self._settings_button = QtWidgets.QPushButton("⚙ Settings")
        self._settings_button.setMinimumHeight(50)
        self._settings_button.setText("Settings")
        self._style_manager.style_button(self._settings_button, "ghost")
        self._settings_button.clicked.connect(self._show_settings)

        self._lane_button = QtWidgets.QPushButton("📐 Adjust Lane")
        self._lane_button.setMinimumHeight(50)
        self._lane_button.setText("Adjust Lane")
        self._style_manager.style_button(self._lane_button, "default")
        self._lane_button.clicked.connect(self._adjust_lane)
        self._lane_button.setToolTip("Adjust the lane ROI (region where ball tracking occurs)")

        self._review_button = QtWidgets.QPushButton("🎬 Review Session")
        self._review_button.setMinimumHeight(50)
        self._review_button.setText("Review Session")
        self._style_manager.style_button(self._review_button, "default")
        self._review_button.clicked.connect(self._open_review_mode)
        self._review_button.setToolTip("Review and analyze previous sessions")

        self._help_button = QtWidgets.QPushButton("❓ Help")
        self._help_button.setMinimumHeight(50)
        self._help_button.setText("Help")
        self._style_manager.style_button(self._help_button, "ghost")

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self._setup_button, 2)
        layout.addWidget(self._start_recording_button, 2)
        layout.addWidget(self._pause_button, 1)
        layout.addWidget(self._end_button, 2)
        layout.addStretch()
        layout.addWidget(self._review_button)
        layout.addWidget(self._lane_button)
        layout.addWidget(self._settings_button)
        layout.addWidget(self._help_button)

        widget = QtWidgets.QFrame()
        self._style_manager.style_panel(widget, "normal")
        widget.setLayout(layout)
        return widget

    def _set_status_message(self, message: str, tone: str = "info") -> None:
        """Update the footer status indicator with a semantic tone."""
        self._status_label.setText(message)
        self._style_manager.style_status_indicator(self._status_label, tone)

    def _warm_camera_cache_async(self) -> None:
        """Proactively warm camera cache in background thread.

        This makes the session start dialog open instantly since the cache
        will already be warm by the time the user clicks "Setup Session".
        """
        def _warm_cache():
            try:
                from ui.device_utils import probe_uvc_devices, probe_opencv_indices

                logger.debug("Background: Warming camera cache...")

                # Warm UVC device cache (2-4 seconds on first run)
                probe_uvc_devices(use_cache=True)

                # Warm OpenCV indices cache (3-6 seconds on first run, checks 10 cameras)
                probe_opencv_indices(max_index=10, use_cache=True)

                logger.info("Background: Camera cache warmed successfully")

            except Exception as e:
                # Don't crash if cache warming fails - dialog will just probe on-demand
                logger.warning(f"Background: Camera cache warming failed: {e}")

        # Start background thread (daemon so it doesn't block app shutdown)
        thread = threading.Thread(target=_warm_cache, daemon=True, name="CameraCache")
        thread.start()

    def _setup_session(self) -> None:
        """Setup coaching session (cameras and configuration only, no recording yet)."""
        # Show session start dialog
        dialog = SessionStartDialog(self._config, parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        # Get values from dialog
        self._session_name = dialog.session_name
        self._pitcher_name = dialog.pitcher_name
        self._pitch_count = 0
        self._last_pitch_count = 0

        # Update configuration from dialog
        if dialog.batter_height_in != self._config.strike_zone.batter_height_in:
            self._service.set_batter_height_in(dialog.batter_height_in)

        if dialog.ball_type != self._config.ball.type:
            self._service.set_ball_type(dialog.ball_type)

        # Get camera serials from dialog
        left_serial = dialog.left_serial
        right_serial = dialog.right_serial

        # Start capture (if not already running)
        try:
            if not self._service.is_capturing():
                logger.info(f"Starting capture with left={left_serial}, right={right_serial}")
                self._set_status_message("Starting cameras...", "info")
                QtWidgets.QApplication.processEvents()

                # Use configurable resolution for coaching app
                # Create modified config with user-selected camera settings
                from configs.settings import CameraConfig
                coaching_camera_config = CameraConfig(
                    width=self._camera_width,
                    height=self._camera_height,
                    fps=self._camera_fps,
                    pixfmt=self._config.camera.pixfmt,
                    exposure_us=self._config.camera.exposure_us,
                    gain=self._config.camera.gain,
                    wb_mode=self._config.camera.wb_mode,
                    wb=self._config.camera.wb,
                    queue_depth=self._config.camera.queue_depth,
                    color_mode=self._camera_color_mode,
                )

                coaching_config = self._config.__class__(
                    camera=coaching_camera_config,
                    stereo=self._config.stereo,
                    tracking=self._config.tracking,
                    metrics=self._config.metrics,
                    recording=self._config.recording,
                    ui=self._config.ui,
                    telemetry=self._config.telemetry,
                    detector=self._config.detector,
                    strike_zone=self._config.strike_zone,
                    ball=self._config.ball,
                    upload=self._config.upload,
                )

                self._service.start_capture(
                    coaching_config,
                    left_serial,
                    right_serial,
                    str(self._config_path),
                )
                logger.info(f"Capture started successfully with {self._camera_width}x{self._camera_height}@{self._camera_fps}fps")
            else:
                logger.info("Capture already running, skipping camera start")

            # Save camera serials to app state for next time
            state = load_state()
            state["last_left_camera"] = left_serial
            state["last_right_camera"] = right_serial
            save_state(state)
            logger.info(f"Saved camera selections: left={left_serial}, right={right_serial}")

        except Exception as e:
            logger.error(f"Failed to setup session: {e}", exc_info=True)
            show_message_dialog(
                self,
                "Session Setup Error",
                f"Failed to setup session:\n{str(e)}",
                tone="error",
            )
            return

        # Update UI - session is ready but not recording yet
        self._session_label.setText(f"Session: {self._session_name}")
        self._pitcher_label.setText(f"Pitcher: {self._pitcher_name}")
        self._pitch_count_label.setText("Pitches: 0")

        # Clear visualizations in current mode
        current_mode = self._mode_stack.currentWidget()
        current_mode.clear()

        # Clear session tracker
        self._session_tracker.clear()

        # Update buttons - enable Start Recording, disable Setup
        self._setup_button.setEnabled(False)
        self._start_recording_button.setEnabled(True)
        self._end_button.setEnabled(True)

        # Update status
        self._set_status_message("Session ready. Click 'Start Recording' when ready to pitch.", "warning")

    def _start_recording(self) -> None:
        """Start recording pitches."""
        if not self._service.is_capturing():
            show_message_dialog(
                self,
                "No Cameras",
                "Cameras are not running. Please setup the session first.",
                tone="warning",
            )
            return

        try:
            logger.info(f"Starting recording for session: {self._session_name}")
            self._set_status_message("Starting recording...", "info")
            QtWidgets.QApplication.processEvents()

            disk_warning = self._service.start_recording(
                pitch_id="session",
                session_name=self._session_name,
                mode="session",
            )
            logger.info("Recording started successfully")

            # Show disk space warning if present (non-blocking)
            if disk_warning:
                show_message_dialog(
                    self,
                    "Disk Space Warning",
                    disk_warning + "\n\nYou can continue, but recording may fail if disk fills up.",
                    tone="warning",
                )

        except Exception as e:
            logger.error(f"Failed to start recording: {e}", exc_info=True)
            show_message_dialog(
                self,
                "Recording Start Error",
                f"Failed to start recording:\n{str(e)}",
                tone="error",
            )
            return

        # Update UI - now recording
        self._recording_indicator.show()

        # Update buttons
        self._start_recording_button.setEnabled(False)
        self._pause_button.setEnabled(True)

        # Update status
        self._set_status_message("Recording in progress. Ready to track pitches.", "success")
        self._style_manager.style_status_indicator(self._status_label, "success")

        self._session_active = True

    def _pause_session(self) -> None:
        """Pause current session."""
        # TODO: Implement pause logic
        self._set_status_message("Session paused. Click 'Start Session' to resume.", "warning")
        self._style_manager.style_status_indicator(self._status_label, "warning")

    def _end_session(self) -> None:
        """End current session and show summary."""
        if not ask_confirmation(
            self,
            "End Session",
            f"End session '{self._session_name}' with {self._pitch_count} pitches?\n\n"
            "Session summary will be displayed.",
            confirm_variant="danger",
        ):
            return

        # Stop recording
        try:
            self._set_status_message("Stopping recording...", "info")
            QtWidgets.QApplication.processEvents()

            # Get session summary before stopping
            summary = self._service.get_session_summary()

            # Stop recording
            self._service.stop_recording()

            # Show summary
            if summary:
                show_message_dialog(
                    self,
                    "Session Complete",
                    f"Session: {self._session_name}\n"
                    f"Pitcher: {self._pitcher_name}\n"
                    f"Pitches: {summary.pitch_count}\n"
                    f"Strikes: {summary.strikes}\n"
                    f"Balls: {summary.balls}\n\n"
                    f"Session data saved.",
                    tone="success",
                )

        except Exception as e:
            show_message_dialog(
                self,
                "Session End Error",
                f"Error stopping session:\n{str(e)}",
                tone="warning",
            )

        # Reset UI
        self._session_label.setText("Session: <not started>")
        self._pitcher_label.setText("Pitcher: <not selected>")
        self._pitch_count_label.setText("Pitches: 0")
        self._recording_indicator.hide()

        # Update buttons - reset to initial state
        self._setup_button.setEnabled(True)
        self._start_recording_button.setEnabled(False)
        self._pause_button.setEnabled(False)
        self._end_button.setEnabled(False)

        # Update status
        self._set_status_message("Session ended. Ready for the next session.", "info")

        self._session_active = False

    def _show_settings(self) -> None:
        """Show settings dialog."""
        # Don't allow settings changes during active session
        if self._session_active:
            show_message_dialog(
                self,
                "Session Active",
                "Cannot change settings during an active session.\n"
                "Please end the current session first.",
                tone="warning",
            )
            return

        from ui.coaching.dialogs.settings_dialog import SettingsDialog

        # Get current camera assignments and settings from app state
        from configs.app_state import load_state
        state = load_state()
        current_left = state.get("last_left_camera", "0")
        current_right = state.get("last_right_camera", "1")
        current_mound_distance = state.get("mound_distance_ft", self._config.metrics.release_plane_z_ft)

        dialog = SettingsDialog(
            current_width=self._camera_width,
            current_height=self._camera_height,
            current_fps=self._camera_fps,
            current_left_camera=current_left,
            current_right_camera=current_right,
            current_mound_distance=current_mound_distance,
            current_ball_type=self._config.ball.type,
            current_color_mode=self._camera_color_mode,
            parent=self,
        )

        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        # Apply settings if they changed
        if dialog.settings_changed:
            # Update stored settings
            self._camera_width = dialog.width
            self._camera_height = dialog.height
            self._camera_fps = dialog.fps
            self._camera_color_mode = dialog.color_mode

            # Update mound distance if changed
            if dialog.mound_distance_ft != current_mound_distance:
                self._service.update_mound_distance(dialog.mound_distance_ft)
                logger.info(f"Updated mound distance to {dialog.mound_distance_ft:.1f} ft")

            # Restart capture if it's running
            if self._service.is_capturing():
                self._set_status_message("Applying settings...", "info")
                QtWidgets.QApplication.processEvents()

                try:
                    # Stop current capture
                    self._service.stop_capture()

                    # Clear current mode
                    current_mode = self._mode_stack.currentWidget()
                    current_mode.clear()
                    QtWidgets.QApplication.processEvents()

                    # Create new camera config with updated settings
                    from configs.settings import CameraConfig
                    coaching_camera_config = CameraConfig(
                        width=self._camera_width,
                        height=self._camera_height,
                        fps=self._camera_fps,
                        pixfmt=self._config.camera.pixfmt,
                        exposure_us=self._config.camera.exposure_us,
                        gain=self._config.camera.gain,
                        wb_mode=self._config.camera.wb_mode,
                        wb=self._config.camera.wb,
                        queue_depth=self._config.camera.queue_depth,
                        color_mode=self._camera_color_mode,
                    )

                    coaching_config = self._config.__class__(
                        camera=coaching_camera_config,
                        stereo=self._config.stereo,
                        tracking=self._config.tracking,
                        metrics=self._config.metrics,
                        recording=self._config.recording,
                        ui=self._config.ui,
                        telemetry=self._config.telemetry,
                        detector=self._config.detector,
                        strike_zone=self._config.strike_zone,
                        ball=self._config.ball,
                        upload=self._config.upload,
                    )

                    # Start capture with new settings
                    self._service.start_capture(
                        coaching_config,
                        dialog.left_camera,
                        dialog.right_camera,
                        str(self._config_path),
                    )

                    self._set_status_message(
                        f"Settings applied: {self._camera_width}x{self._camera_height}@{self._camera_fps}fps",
                        "success",
                    )
                    logger.info(f"Settings applied: {self._camera_width}x{self._camera_height}@{self._camera_fps}fps")

                except Exception as e:
                    show_message_dialog(
                        self,
                        "Settings Error",
                        f"Failed to apply settings:\n{e}\n\nYou may need to restart the application.",
                        tone="error",
                    )
                    logger.exception("Failed to apply settings")
                    self._set_status_message("Error applying settings", "error")
            else:
                # Just show confirmation, settings will apply on next session start
                show_message_dialog(
                    self,
                    "Settings Saved",
                    f"Settings saved successfully.\n\n"
                    f"Resolution: {self._camera_width}x{self._camera_height}@{self._camera_fps}fps\n"
                    f"Settings will apply when you start the next session.",
                    tone="success",
                )

    def _adjust_lane(self) -> None:
        """Show lane ROI adjustment dialog."""
        # Need cameras to be running to show preview
        if not self._service.is_capturing():
            show_message_dialog(
                self,
                "Cameras Not Running",
                "Please start a session first to view the camera feed.\n\n"
                "The lane ROI adjustment requires a live camera preview.",
                tone="warning",
            )
            return

        from ui.coaching.dialogs.lane_adjust_dialog import LaneAdjustDialog

        dialog = LaneAdjustDialog(
            camera_service=self._service,
            parent=self,
        )

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            show_message_dialog(
                self,
                "Lane ROI Updated",
                "Lane ROI has been updated.\n\n"
                "Changes will take effect for new pitches tracked during this session.",
                tone="success",
            )

    def _open_review_mode(self) -> None:
        """Open review mode window for analyzing previous sessions."""
        from ui.review import ReviewWindow

        review_window = ReviewWindow(parent=self)
        review_window.show()
        logger.info("Opened review mode window")

    def closeEvent(self, event) -> None:
        """Handle window close event - stop capture and recording."""
        # Stop timers
        self._preview_timer.stop()
        self._metrics_timer.stop()

        if self._session_active:
            reply = show_choice_dialog(
                self,
                "Session Active",
                "A session is currently active. End session before closing?",
                choices=(
                    ("end", "End Session", "primary", QtWidgets.QMessageBox.ButtonRole.AcceptRole),
                    ("close", "Close Without Ending", "ghost", QtWidgets.QMessageBox.ButtonRole.DestructiveRole),
                    ("cancel", "Cancel", "ghost", QtWidgets.QMessageBox.ButtonRole.RejectRole),
                ),
                default_choice="cancel",
            )

            if reply == "cancel":
                event.ignore()
                # Restart timers if user cancels
                self._preview_timer.start(33)
                self._metrics_timer.start(100)
                return
            elif reply == "end":
                try:
                    self._service.stop_recording()
                except Exception:
                    pass

        # Stop capture
        try:
            if self._service.is_capturing():
                self._service.stop_capture()
        except Exception:
            pass

        event.accept()

    def _update_preview(self) -> None:
        """Update camera preview frames."""
        if not self._service.is_capturing():
            return

        try:
            # Get preview frames
            left_frame, right_frame = self._service.get_preview_frames()

            # Forward to current mode
            current_mode = self._mode_stack.currentWidget()
            current_mode.update_camera_frames(left_frame, right_frame)

        except Exception as e:
            # Log preview errors for debugging
            logger.error(f"Preview update failed: {e}", exc_info=True)

    def _on_pitch_started(self, pitch_index: int, pitch_data) -> None:
        """Handle pitch started signal (runs on main Qt thread).

        This is called via Qt signal when a pitch is detected in a worker thread.
        Safe to update UI elements here.

        Args:
            pitch_index: Pitch index (1-based)
            pitch_data: PitchData object
        """
        logger.info(f"Pitch {pitch_index} started (main thread)")
        # Update status
        self._set_status_message(f"Pitch {pitch_index} detected.", "info")
        # The metrics will be updated by the regular polling timer

    def _on_pitch_ended(self, pitch_data) -> None:
        """Handle pitch ended signal (runs on main Qt thread).

        This is called via Qt signal when a pitch finishes in a worker thread.
        Safe to update UI elements here.

        Args:
            pitch_data: PitchData object
        """
        logger.info("Pitch ended (main thread)")
        # Metrics will be updated by the regular polling timer
        # Just update status
        if self._session_active:
            self._set_status_message("Recording in progress. Ready to track pitches.", "success")

    def _update_metrics(self) -> None:
        """Update pitch metrics display."""
        if not self._session_active:
            return

        try:
            # Get recent pitches from service
            recent_pitches = self._service.get_recent_pitches()

            # Check if new pitches detected
            if len(recent_pitches) > self._last_pitch_count:
                # Update pitch count
                self._pitch_count = len(recent_pitches)
                self._pitch_count_label.setText(f"Pitches: {self._pitch_count}")
                self._last_pitch_count = self._pitch_count

                # Add new pitches to session tracker
                for pitch in recent_pitches[self._last_pitch_count - 1:]:
                    self._session_tracker.add_pitch(pitch)

            # Forward all recent pitches to current mode
            if recent_pitches:
                current_mode = self._mode_stack.currentWidget()
                current_mode.update_pitch_data(recent_pitches)

                # Update fatigue indicator
                self._fatigue_indicator.update_pitches(recent_pitches)

        except Exception as e:
            # Log metrics errors for debugging
            logger.error(f"Metrics update failed: {e}", exc_info=True)

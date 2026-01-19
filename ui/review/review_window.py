"""Review window for analyzing recorded sessions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.review import PitchScore, ReviewService
from ui.review.widgets import ParameterPanel, PitchListWidget, PlaybackControls, TimelineWidget, VideoDisplayWidget

logger = logging.getLogger(__name__)


class ReviewWindow(QtWidgets.QMainWindow):
    """Main window for review and training mode.

    Allows users to:
    - Load previously recorded sessions
    - Replay videos with playback controls
    - Adjust detection parameters
    - Annotate and score pitches
    - Export tuned configurations

    Example:
        >>> window = ReviewWindow()
        >>> window.show()
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize review window.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("PitchTracker - Review Mode")
        self.resize(1600, 1000)

        # Review service backend
        self._service = ReviewService()

        # Playback timer
        self._playback_timer = QtCore.QTimer()
        self._playback_timer.timeout.connect(self._on_playback_tick)
        self._is_playing = False

        # Session navigation
        self._session_list: list[Path] = []
        self._current_session_index = -1

        # Build UI
        self._build_ui()
        self._update_ui_state()

        logger.info("ReviewWindow initialized")

    def _build_ui(self) -> None:
        """Build the main UI layout."""
        # Create menu bar
        self._create_menu_bar()

        # Main content area
        content = self._build_content_area()

        # Status bar
        self._status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready. Open a session to begin.")

        # Set central widget
        self.setCentralWidget(content)

    def _create_menu_bar(self) -> None:
        """Create menu bar with File, Playback, Tools, Export menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QtGui.QAction("&Open Session...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_session)
        file_menu.addAction(open_action)

        review_all_action = QtGui.QAction("Review &All Sessions", self)
        review_all_action.setShortcut("Ctrl+Shift+O")
        review_all_action.triggered.connect(self._review_all_sessions)
        file_menu.addAction(review_all_action)

        file_menu.addSeparator()

        prev_session_action = QtGui.QAction("&Previous Session", self)
        prev_session_action.setShortcut("Ctrl+PgUp")
        prev_session_action.triggered.connect(self._previous_session)
        file_menu.addAction(prev_session_action)
        self._prev_session_action = prev_session_action

        next_session_action = QtGui.QAction("&Next Session", self)
        next_session_action.setShortcut("Ctrl+PgDown")
        next_session_action.triggered.connect(self._next_session)
        file_menu.addAction(next_session_action)
        self._next_session_action = next_session_action

        file_menu.addSeparator()

        delete_session_action = QtGui.QAction("&Delete Current Session...", self)
        delete_session_action.setShortcut("Ctrl+D")
        delete_session_action.triggered.connect(self._delete_current_session)
        file_menu.addAction(delete_session_action)
        self._delete_session_action = delete_session_action

        file_menu.addSeparator()

        close_action = QtGui.QAction("&Close Session", self)
        close_action.setShortcut("Ctrl+W")
        close_action.triggered.connect(self._close_session)
        file_menu.addAction(close_action)

        file_menu.addSeparator()

        exit_action = QtGui.QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Playback menu
        playback_menu = menubar.addMenu("&Playback")

        play_pause_action = QtGui.QAction("Play/Pause", self)
        play_pause_action.setShortcut("Space")
        play_pause_action.triggered.connect(self._toggle_playback)
        playback_menu.addAction(play_pause_action)

        step_forward_action = QtGui.QAction("Step Forward", self)
        step_forward_action.setShortcut("Right")
        step_forward_action.triggered.connect(self._step_forward)
        playback_menu.addAction(step_forward_action)

        step_back_action = QtGui.QAction("Step Backward", self)
        step_back_action.setShortcut("Left")
        step_back_action.triggered.connect(self._step_backward)
        playback_menu.addAction(step_back_action)

        playback_menu.addSeparator()

        seek_start_action = QtGui.QAction("Seek to Start", self)
        seek_start_action.setShortcut("Home")
        seek_start_action.triggered.connect(self._seek_to_start)
        playback_menu.addAction(seek_start_action)

        seek_end_action = QtGui.QAction("Seek to End", self)
        seek_end_action.setShortcut("End")
        seek_end_action.triggered.connect(self._seek_to_end)
        playback_menu.addAction(seek_end_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        annotation_action = QtGui.QAction("Toggle Annotation Mode", self)
        annotation_action.setShortcut("A")
        annotation_action.setCheckable(True)
        annotation_action.triggered.connect(self._toggle_annotation_mode)
        tools_menu.addAction(annotation_action)
        self._annotation_action = annotation_action

        clear_annotations_action = QtGui.QAction("Clear Annotations", self)
        clear_annotations_action.triggered.connect(self._clear_annotations)
        tools_menu.addAction(clear_annotations_action)

        # Export menu
        export_menu = menubar.addMenu("&Export")

        export_config_action = QtGui.QAction("Export &Config...", self)
        export_config_action.triggered.connect(self._export_config)
        export_menu.addAction(export_config_action)

        export_annotations_action = QtGui.QAction("Export &Annotations...", self)
        export_annotations_action.triggered.connect(self._export_annotations)
        export_menu.addAction(export_annotations_action)

    def _build_content_area(self) -> QtWidgets.QWidget:
        """Build main content area with video displays and controls.

        Returns:
            Widget containing the main UI layout
        """
        # Left section: Videos + timeline + controls
        left_section = self._build_video_and_controls_section()

        # Right section: Parameter panel + pitch list
        right_section = self._build_right_panel()

        # Main horizontal layout
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addWidget(left_section, 1)  # Video section takes most space
        main_layout.addWidget(right_section)  # Right panel

        container = QtWidgets.QWidget()
        container.setLayout(main_layout)
        return container

    def _build_right_panel(self) -> QtWidgets.QWidget:
        """Build right panel with parameters and pitch list.

        Returns:
            Widget with right panel layout
        """
        # Parameter tuning panel
        self._parameter_panel = ParameterPanel()
        self._parameter_panel.parameter_changed.connect(self._on_parameters_changed)

        # Pitch list widget
        self._pitch_list = PitchListWidget()
        self._pitch_list.pitch_selected.connect(self._on_pitch_selected)
        self._pitch_list.pitch_scored.connect(self._on_pitch_scored)

        # Vertical layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._parameter_panel)
        layout.addWidget(self._pitch_list)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        return container

    def _build_video_and_controls_section(self) -> QtWidgets.QWidget:
        """Build video displays, timeline, and playback controls.

        Returns:
            Widget with video section layout
        """
        # Top: Dual video displays
        video_section = self._build_video_section()

        # Middle: Timeline
        self._timeline = TimelineWidget()
        self._timeline.seek_requested.connect(self._on_timeline_seek)

        # Bottom: Playback controls
        self._controls = PlaybackControls()
        self._controls.play_pause_clicked.connect(self._toggle_playback)
        self._controls.step_forward_clicked.connect(self._step_forward)
        self._controls.step_backward_clicked.connect(self._step_backward)
        self._controls.seek_start_clicked.connect(self._seek_to_start)
        self._controls.seek_end_clicked.connect(self._seek_to_end)
        self._controls.speed_changed.connect(self._on_speed_changed)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(video_section, 1)  # Takes most space
        layout.addWidget(self._timeline)
        layout.addWidget(self._controls)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        return container

    def _build_video_section(self) -> QtWidgets.QWidget:
        """Build dual video display section.

        Returns:
            Widget with left and right video displays
        """
        # Left camera display
        left_group = QtWidgets.QGroupBox("Left Camera")
        self._left_display = VideoDisplayWidget()
        self._left_display.annotation_added.connect(lambda x, y: self._on_annotation_added("left", x, y))
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._left_display)
        left_group.setLayout(left_layout)

        # Right camera display
        right_group = QtWidgets.QGroupBox("Right Camera")
        self._right_display = VideoDisplayWidget()
        self._right_display.annotation_added.connect(lambda x, y: self._on_annotation_added("right", x, y))
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self._right_display)
        right_group.setLayout(right_layout)

        # Horizontal layout for side-by-side
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(left_group)
        layout.addWidget(right_group)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        return container

    def _open_session(self) -> None:
        """Show dialog to select and open a session."""
        # Browse for session directory
        recordings_dir = Path("recordings")
        if not recordings_dir.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Recordings Not Found",
                f"Recordings directory not found: {recordings_dir}\n\n"
                "Please record at least one session before using Review Mode.",
            )
            return

        session_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Session Directory",
            str(recordings_dir),
            QtWidgets.QFileDialog.Option.ShowDirsOnly,
        )

        if not session_dir:
            return  # User cancelled

        self._load_session(Path(session_dir))

    def _load_session(self, session_dir: Path) -> None:
        """Load a session for review.

        Args:
            session_dir: Path to session directory
        """
        try:
            logger.info(f"Loading session: {session_dir}")
            self._status_bar.showMessage(f"Loading session: {session_dir.name}...")
            QtWidgets.QApplication.processEvents()

            # Load session via service
            session = self._service.load_session(session_dir)

            # Update window title
            self.setWindowTitle(f"PitchTracker - Review Mode - {session.session_id}")

            # Update timeline
            self._timeline.set_total_frames(self._service.total_frames)
            self._timeline.set_fps(self._service.video_reader.fps)

            # Load detector config into parameter panel
            if self._service.detector_config:
                cfg = self._service.detector_config
                from detect.config import Mode
                self._parameter_panel.load_parameters(
                    mode=Mode(cfg.mode),
                    frame_diff_threshold=cfg.frame_diff_threshold,
                    bg_diff_threshold=cfg.bg_diff_threshold,
                    min_area=cfg.filters.min_area,
                    max_area=cfg.filters.max_area or 500,
                    min_circularity=cfg.filters.min_circularity,
                )

            # Load pitches into pitch list
            pitch_scores = self._service._pitch_scores
            self._pitch_list.load_pitches(session.pitches, pitch_scores)

            # Load and display first frame
            self._update_video_displays()

            # Update status
            self._status_bar.showMessage(
                f"Loaded session: {session.session_id} "
                f"({len(session.pitches)} pitches, {self._service.total_frames} frames)"
            )

            # Update UI state
            self._update_ui_state()

            logger.info(f"Session loaded successfully: {session.session_id}")

        except Exception as e:
            logger.exception(f"Failed to load session: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load session:\n{str(e)}",
            )
            self._status_bar.showMessage("Failed to load session")

    def _close_session(self) -> None:
        """Close current session."""
        if self._is_playing:
            self._toggle_playback()  # Stop playback

        self._service.close()
        self._left_display.clear()
        self._right_display.clear()
        self._timeline.reset()
        self._pitch_list.clear()

        self.setWindowTitle("PitchTracker - Review Mode")
        self._status_bar.showMessage("Session closed. Open a session to begin.")
        self._update_ui_state()

        logger.info("Session closed")

    def _review_all_sessions(self) -> None:
        """Load all sessions in recordings directory for sequential review."""
        recordings_dir = Path("recordings")
        if not recordings_dir.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Recordings Not Found",
                f"Recordings directory not found: {recordings_dir}\n\n"
                "Please record at least one session before using Review Mode.",
            )
            return

        # Get all session directories (sorted by name)
        from app.review import SessionLoader
        self._session_list = SessionLoader.get_available_sessions()

        if not self._session_list:
            QtWidgets.QMessageBox.information(
                self,
                "No Sessions Found",
                "No recorded sessions found in the recordings directory.",
            )
            return

        # Load first session
        self._current_session_index = 0
        self._load_session(self._session_list[0])
        self._update_session_navigation_ui()

        logger.info(f"Loaded {len(self._session_list)} sessions for review")

    def _next_session(self) -> None:
        """Load next session in the list."""
        if not self._session_list or self._current_session_index < 0:
            QtWidgets.QMessageBox.information(
                self, "No Sessions", "Use 'Review All Sessions' first."
            )
            return

        if self._current_session_index >= len(self._session_list) - 1:
            QtWidgets.QMessageBox.information(
                self, "Last Session", "This is the last session in the list."
            )
            return

        self._current_session_index += 1
        self._load_session(self._session_list[self._current_session_index])
        self._update_session_navigation_ui()

    def _previous_session(self) -> None:
        """Load previous session in the list."""
        if not self._session_list or self._current_session_index < 0:
            QtWidgets.QMessageBox.information(
                self, "No Sessions", "Use 'Review All Sessions' first."
            )
            return

        if self._current_session_index <= 0:
            QtWidgets.QMessageBox.information(
                self, "First Session", "This is the first session in the list."
            )
            return

        self._current_session_index -= 1
        self._load_session(self._session_list[self._current_session_index])
        self._update_session_navigation_ui()

    def _delete_current_session(self) -> None:
        """Delete the currently loaded session from disk."""
        if not self._service.session:
            QtWidgets.QMessageBox.warning(
                self, "No Session", "No session is currently loaded."
            )
            return

        session = self._service.session
        session_dir = session.session_dir

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Session",
            f"Are you sure you want to delete this session?\n\n"
            f"Session: {session.session_id}\n"
            f"Path: {session_dir}\n\n"
            f"This will permanently delete all files in this session directory.\n"
            f"This action cannot be undone!",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        try:
            # Close the session first
            self._close_session()

            # Delete the directory
            import shutil
            shutil.rmtree(session_dir)

            logger.info(f"Deleted session: {session_dir}")
            QtWidgets.QMessageBox.information(
                self,
                "Session Deleted",
                f"Session {session.session_id} has been deleted.",
            )

            # If we're in "review all" mode, update the list and load next session
            if self._session_list:
                # Remove deleted session from list
                if self._current_session_index < len(self._session_list):
                    self._session_list.pop(self._current_session_index)

                # Load next session if available
                if self._session_list:
                    # Adjust index if we were at the end
                    if self._current_session_index >= len(self._session_list):
                        self._current_session_index = len(self._session_list) - 1

                    self._load_session(self._session_list[self._current_session_index])
                    self._update_session_navigation_ui()
                else:
                    # No more sessions
                    self._current_session_index = -1
                    self._status_bar.showMessage("No more sessions to review")

        except Exception as e:
            logger.exception(f"Failed to delete session: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Delete Error",
                f"Failed to delete session:\n{str(e)}",
            )

    def _update_session_navigation_ui(self) -> None:
        """Update UI elements related to session navigation."""
        if self._session_list and self._current_session_index >= 0:
            total = len(self._session_list)
            current = self._current_session_index + 1
            session_info = f"Session {current}/{total}"

            # Update status bar with session counter
            current_message = self._status_bar.currentMessage()
            if " | " in current_message:
                # Preserve existing status, add session info
                base_message = current_message.split(" | ")[0]
                self._status_bar.showMessage(f"{base_message} | {session_info}")
            else:
                self._status_bar.showMessage(f"Ready | {session_info}")

            # Enable/disable navigation actions
            self._prev_session_action.setEnabled(self._current_session_index > 0)
            self._next_session_action.setEnabled(self._current_session_index < total - 1)
            self._delete_session_action.setEnabled(True)
        else:
            # Disable navigation if not in "review all" mode
            self._prev_session_action.setEnabled(False)
            self._next_session_action.setEnabled(False)
            self._delete_session_action.setEnabled(self._service.session is not None)

    def _toggle_playback(self) -> None:
        """Toggle between play and pause."""
        if not self._service.session:
            return

        if self._is_playing:
            # Pause
            self._playback_timer.stop()
            self._is_playing = False
            self._controls.set_playing(False)
            self._status_bar.showMessage("Paused")
            logger.debug("Playback paused")
        else:
            # Play
            # Calculate timer interval based on FPS and playback speed
            fps = self._service.video_reader.fps
            speed = self._service.playback_speed
            interval_ms = int(1000.0 / (fps * speed))

            self._playback_timer.start(interval_ms)
            self._is_playing = True
            self._controls.set_playing(True)
            self._status_bar.showMessage(f"Playing (Speed: {speed:.1f}x)")
            logger.debug(f"Playback started at {speed:.1f}x speed")

    def _on_playback_tick(self) -> None:
        """Called on each playback timer tick to advance frame."""
        # Advance to next frame
        if not self._service.step_forward():
            # Reached end of video
            self._toggle_playback()  # Stop
            self._status_bar.showMessage("Reached end of video")
            return

        # Update displays
        self._update_video_displays()
        self._timeline.set_current_frame(self._service.current_frame_index)

    def _step_forward(self) -> None:
        """Step forward one frame."""
        if not self._service.session:
            return

        if self._service.step_forward():
            self._update_video_displays()
            self._timeline.set_current_frame(self._service.current_frame_index)
            self._status_bar.showMessage(
                f"Frame {self._service.current_frame_index + 1}/{self._service.total_frames}"
            )

    def _step_backward(self) -> None:
        """Step backward one frame."""
        if not self._service.session:
            return

        if self._service.step_backward():
            self._update_video_displays()
            self._timeline.set_current_frame(self._service.current_frame_index)
            self._status_bar.showMessage(
                f"Frame {self._service.current_frame_index + 1}/{self._service.total_frames}"
            )

    def _seek_to_start(self) -> None:
        """Seek to start of video."""
        if not self._service.session:
            return

        self._service.seek_to_start()
        self._update_video_displays()
        self._timeline.set_current_frame(0)
        self._status_bar.showMessage("Seeked to start")

    def _seek_to_end(self) -> None:
        """Seek to end of video."""
        if not self._service.session:
            return

        self._service.seek_to_end()
        self._update_video_displays()
        self._timeline.set_current_frame(self._service.current_frame_index)
        self._status_bar.showMessage("Seeked to end")

    def _on_timeline_seek(self, frame_index: int) -> None:
        """Handle seek request from timeline widget.

        Args:
            frame_index: Frame to seek to
        """
        if not self._service.session:
            return

        self._service.seek_to_frame(frame_index)
        self._update_video_displays()
        self._status_bar.showMessage(
            f"Seeked to frame {frame_index + 1}/{self._service.total_frames}"
        )

    def _on_speed_changed(self, speed: float) -> None:
        """Handle playback speed change.

        Args:
            speed: New playback speed multiplier
        """
        self._service.playback_speed = speed

        # If playing, restart timer with new interval
        if self._is_playing:
            self._playback_timer.stop()
            fps = self._service.video_reader.fps
            interval_ms = int(1000.0 / (fps * speed))
            self._playback_timer.start(interval_ms)

        self._status_bar.showMessage(f"Playback speed: {speed:.1f}x")

    def _on_pitch_selected(self, pitch_index: int) -> None:
        """Handle pitch selection from list.

        Args:
            pitch_index: Index of selected pitch
        """
        if not self._service.session:
            return

        # Seek to pitch
        self._service.seek_to_pitch(pitch_index)
        self._update_video_displays()
        self._timeline.set_current_frame(self._service.current_frame_index)

        pitch = self._service.session.pitches[pitch_index]
        self._status_bar.showMessage(f"Navigated to pitch: {pitch.pitch_id}")

    def _on_pitch_scored(self, pitch_id: str, score: PitchScore) -> None:
        """Handle pitch scoring.

        Args:
            pitch_id: Pitch identifier
            score: Pitch score
        """
        # Update service
        self._service.score_pitch(pitch_id, score)

        self._status_bar.showMessage(f"Scored {pitch_id}: {score.value}")
        logger.info(f"Pitch scored: {pitch_id} = {score.value}")

    def _on_parameters_changed(self) -> None:
        """Handle parameter changes - update detector config and re-run detection."""
        if not self._service.session:
            return

        # Update detector config in service
        self._service.update_detector_config(
            frame_diff_threshold=self._parameter_panel.frame_diff_threshold,
            bg_diff_threshold=self._parameter_panel.bg_diff_threshold,
            min_area=self._parameter_panel.min_area,
            max_area=self._parameter_panel.max_area,
            min_circularity=self._parameter_panel.min_circularity,
            mode=self._parameter_panel.mode,
        )

        # Update displays with new detections
        self._update_video_displays()

        self._status_bar.showMessage("Detection parameters updated")

    def _update_video_displays(self) -> None:
        """Update video displays with current frames and detections."""
        left_frame, right_frame = self._service.get_current_frames()

        if left_frame is None or right_frame is None:
            return

        # Run detection on current frame
        try:
            left_detections, right_detections = self._service.run_detection_on_current_frame()

            # Update displays with frames and detections
            self._left_display.set_frame(left_frame, left_detections)
            self._right_display.set_frame(right_frame, right_detections)

            # Update status with detection count
            self._status_bar.showMessage(
                f"Frame {self._service.current_frame_index + 1}/{self._service.total_frames} "
                f"| Detections: L={len(left_detections)}, R={len(right_detections)}"
            )

        except Exception as e:
            logger.exception(f"Detection failed: {e}")
            # Still show frames even if detection fails
            self._left_display.set_frame(left_frame)
            self._right_display.set_frame(right_frame)

    def _export_config(self) -> None:
        """Export tuned detector configuration."""
        if not self._service.session:
            QtWidgets.QMessageBox.warning(
                self, "No Session", "Please load a session first."
            )
            return

        # Get save file path
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Detector Config",
            "config_tuned.json",
            "JSON Files (*.json);;All Files (*)",
        )

        if not file_path:
            return

        try:
            self._service.export_config(Path(file_path))
            QtWidgets.QMessageBox.information(
                self,
                "Export Successful",
                f"Detector configuration exported to:\n{file_path}",
            )
            logger.info(f"Exported config to {file_path}")
        except Exception as e:
            logger.exception(f"Failed to export config: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Export Error", f"Failed to export config:\n{str(e)}"
            )

    def _export_annotations(self) -> None:
        """Export annotations to JSON file."""
        if not self._service.session:
            QtWidgets.QMessageBox.warning(
                self, "No Session", "Please load a session first."
            )
            return

        # Sync pitch scores from pitch list to service
        pitch_scores = self._pitch_list.get_pitch_scores()
        for pitch_id, score in pitch_scores.items():
            self._service.score_pitch(pitch_id, score)

        # Get save file path
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Annotations",
            "annotations.json",
            "JSON Files (*.json);;All Files (*)",
        )

        if not file_path:
            return

        try:
            self._service.export_annotations(Path(file_path))

            # Show statistics in message
            summary = self._service.get_pitch_score_summary()
            stats_text = (
                f"Annotations exported to:\n{file_path}\n\n"
                f"Statistics:\n"
                f"Good: {summary['good']}\n"
                f"Partial: {summary['partial']}\n"
                f"Missed: {summary['missed']}\n"
                f"Unscored: {summary['unscored']}"
            )

            QtWidgets.QMessageBox.information(
                self,
                "Export Successful",
                stats_text,
            )
            logger.info(f"Exported annotations to {file_path}")
        except Exception as e:
            logger.exception(f"Failed to export annotations: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Export Error", f"Failed to export annotations:\n{str(e)}"
            )

    def _update_ui_state(self) -> None:
        """Update UI element enabled/disabled state based on session loaded."""
        has_session = self._service.session is not None

        # Update session navigation states
        if self._session_list and self._current_session_index >= 0:
            # In "review all" mode
            total = len(self._session_list)
            self._prev_session_action.setEnabled(self._current_session_index > 0)
            self._next_session_action.setEnabled(self._current_session_index < total - 1)
        else:
            # Not in "review all" mode
            self._prev_session_action.setEnabled(False)
            self._next_session_action.setEnabled(False)

        # Delete is enabled if any session is loaded
        self._delete_session_action.setEnabled(has_session)

    def _toggle_annotation_mode(self, checked: bool) -> None:
        """Toggle annotation mode on/off.

        Args:
            checked: True to enable annotation mode, False to disable
        """
        self._left_display.set_annotation_mode(checked)
        self._right_display.set_annotation_mode(checked)

        mode_str = "ON" if checked else "OFF"
        self._status_bar.showMessage(f"Annotation mode: {mode_str}")
        logger.info(f"Annotation mode: {mode_str}")

    def _clear_annotations(self) -> None:
        """Clear all manual annotations from both displays."""
        self._left_display.clear_annotations()
        self._right_display.clear_annotations()

        self._status_bar.showMessage("Annotations cleared")
        logger.info("Annotations cleared")

    def _on_annotation_added(self, camera: str, x: float, y: float) -> None:
        """Handle annotation added to video display.

        Args:
            camera: "left" or "right"
            x: X coordinate in frame coordinates
            y: Y coordinate in frame coordinates
        """
        frame_index = self._service.current_frame_index
        self._service.add_annotation(frame_index, camera, x, y)

        self._status_bar.showMessage(
            f"Added annotation: {camera} camera at ({x:.1f}, {y:.1f}) frame {frame_index}"
        )
        logger.info(f"Annotation added: {camera} ({x:.1f}, {y:.1f}) at frame {frame_index}")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle window close event.

        Args:
            event: Close event
        """
        # Stop playback if active
        if self._is_playing:
            self._playback_timer.stop()

        # Close service
        self._service.close()

        event.accept()
        logger.info("ReviewWindow closed")

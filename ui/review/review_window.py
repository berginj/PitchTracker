"""Review window for analyzing recorded sessions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.review import PitchScore, ReviewService
from ui.review.widgets import ParameterPanel, PlaybackControls, TimelineWidget, VideoDisplayWidget

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

        # Right section: Parameter tuning panel
        self._parameter_panel = ParameterPanel()
        self._parameter_panel.parameter_changed.connect(self._on_parameters_changed)

        # Main horizontal layout
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addWidget(left_section, 1)  # Video section takes most space
        main_layout.addWidget(self._parameter_panel)  # Parameter panel on right

        container = QtWidgets.QWidget()
        container.setLayout(main_layout)
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
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._left_display)
        left_group.setLayout(left_layout)

        # Right camera display
        right_group = QtWidgets.QGroupBox("Right Camera")
        self._right_display = VideoDisplayWidget()
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

        self.setWindowTitle("PitchTracker - Review Mode")
        self._status_bar.showMessage("Session closed. Open a session to begin.")
        self._update_ui_state()

        logger.info("Session closed")

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
            QtWidgets.QMessageBox.information(
                self,
                "Export Successful",
                f"Annotations exported to:\n{file_path}",
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
        # Can add more UI state updates here as needed

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

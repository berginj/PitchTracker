"""Coaching window for day-to-day pitching sessions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.pipeline_service import InProcessPipelineService
from configs.app_state import load_state, save_state
from configs.settings import load_config
from ui.coaching.dialogs import SessionStartDialog
from ui.coaching.widgets import HeatMapWidget, StrikeZoneOverlay, TrajectoryWidget

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

        # Load configuration
        if config_path is None:
            config_path = Path("configs/default.yaml")
        self._config_path = config_path
        self._config = load_config(config_path)

        # Initialize pipeline service
        self._service = InProcessPipelineService(backend=backend)

        # Session state
        self._session_active = False
        self._pitch_count = 0
        self._session_name = ""
        self._pitcher_name = ""

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
        self._status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0;")

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(session_bar)
        layout.addWidget(main_content, 1)  # Takes most space
        layout.addWidget(controls)
        layout.addWidget(self._status_label)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _build_session_bar(self) -> QtWidgets.QWidget:
        """Build session information bar."""
        # Session name
        self._session_label = QtWidgets.QLabel("Session: <not started>")
        self._session_label.setStyleSheet("font-size: 14pt; font-weight: bold;")

        # Pitcher name
        self._pitcher_label = QtWidgets.QLabel("Pitcher: <not selected>")
        self._pitcher_label.setStyleSheet("font-size: 12pt;")

        # Pitch count
        self._pitch_count_label = QtWidgets.QLabel("Pitches: 0")
        self._pitch_count_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2196F3;")

        # Recording indicator
        self._recording_indicator = QtWidgets.QLabel("● Recording")
        self._recording_indicator.setStyleSheet("font-size: 12pt; color: red; font-weight: bold;")
        self._recording_indicator.hide()

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._session_label)
        layout.addWidget(QtWidgets.QLabel("|"))
        layout.addWidget(self._pitcher_label)
        layout.addWidget(QtWidgets.QLabel("|"))
        layout.addWidget(self._pitch_count_label)
        layout.addStretch()
        layout.addWidget(self._recording_indicator)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        widget.setStyleSheet("background-color: #e3f2fd; padding: 10px;")
        return widget

    def _build_main_content(self) -> QtWidgets.QWidget:
        """Build main content area with cameras and metrics."""
        # Left camera view with strike zone overlay
        left_group = QtWidgets.QGroupBox("Left Camera")
        self._left_view = QtWidgets.QLabel("Camera Preview")
        self._left_view.setMinimumSize(500, 375)
        self._left_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._left_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._left_view.setStyleSheet("background-color: #f5f5f5;")

        # Create overlay for strike zone
        self._left_overlay = StrikeZoneOverlay(self._left_view)
        self._left_overlay.setGeometry(self._left_view.geometry())

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._left_view)
        left_group.setLayout(left_layout)

        # Trajectory visualization
        trajectory_group = QtWidgets.QGroupBox("Pitch Trajectory (Side View)")
        self._trajectory = TrajectoryWidget()
        trajectory_layout = QtWidgets.QVBoxLayout()
        trajectory_layout.addWidget(self._trajectory)
        trajectory_group.setLayout(trajectory_layout)

        # Latest pitch metrics
        metrics_group = QtWidgets.QGroupBox("Latest Pitch")
        self._metrics_display = self._build_metrics_display()
        metrics_layout = QtWidgets.QVBoxLayout()
        metrics_layout.addWidget(self._metrics_display)
        metrics_group.setLayout(metrics_layout)

        # Right camera view with strike zone overlay
        right_group = QtWidgets.QGroupBox("Right Camera")
        self._right_view = QtWidgets.QLabel("Camera Preview")
        self._right_view.setMinimumSize(400, 300)
        self._right_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._right_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._right_view.setStyleSheet("background-color: #f5f5f5;")

        # Create overlay for strike zone
        self._right_overlay = StrikeZoneOverlay(self._right_view)
        self._right_overlay.setGeometry(self._right_view.geometry())

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self._right_view)
        right_group.setLayout(right_layout)

        # Heat map
        heat_map_group = QtWidgets.QGroupBox("Location Heat Map")
        self._heat_map = self._build_heat_map_widget()
        heat_map_layout = QtWidgets.QVBoxLayout()
        heat_map_layout.addWidget(self._heat_map)
        heat_map_group.setLayout(heat_map_layout)

        # Recent pitches
        recent_group = QtWidgets.QGroupBox("Recent Pitches")
        self._recent_list = QtWidgets.QListWidget()
        self._recent_list.setMaximumHeight(200)
        recent_layout = QtWidgets.QVBoxLayout()
        recent_layout.addWidget(self._recent_list)
        recent_group.setLayout(recent_layout)

        # Layout: 2 rows
        # Top row: [Left Camera] [Trajectory + Metrics] [Right Camera]
        # Bottom row: [Heat Map] [Recent Pitches]
        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(left_group, 3)

        middle_column = QtWidgets.QVBoxLayout()
        middle_column.addWidget(trajectory_group)
        middle_column.addWidget(metrics_group)
        middle_widget = QtWidgets.QWidget()
        middle_widget.setLayout(middle_column)
        top_row.addWidget(middle_widget, 2)

        top_row.addWidget(right_group, 2)

        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.addWidget(heat_map_group, 1)
        bottom_row.addWidget(recent_group, 1)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(top_row, 3)
        layout.addLayout(bottom_row, 1)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget

    def _build_metrics_display(self) -> QtWidgets.QWidget:
        """Build latest pitch metrics display."""
        self._speed_label = QtWidgets.QLabel("Speed: -- mph")
        self._speed_label.setStyleSheet("font-size: 18pt; font-weight: bold;")

        self._hbreak_label = QtWidgets.QLabel("H-Break: -- in")
        self._vbreak_label = QtWidgets.QLabel("V-Break: -- in")
        self._result_label = QtWidgets.QLabel("Result: --")
        self._result_label.setStyleSheet("font-size: 14pt; font-weight: bold;")

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._speed_label)
        layout.addWidget(self._hbreak_label)
        layout.addWidget(self._vbreak_label)
        layout.addWidget(self._result_label)
        layout.addStretch()

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget

    def _build_heat_map_widget(self) -> HeatMapWidget:
        """Build heat map widget (counts per zone)."""
        heat_map = HeatMapWidget()
        heat_map.setMinimumSize(200, 150)
        return heat_map

    def _build_controls(self) -> QtWidgets.QWidget:
        """Build control buttons."""
        self._start_button = QtWidgets.QPushButton("Start Session")
        self._start_button.setMinimumHeight(50)
        self._start_button.setStyleSheet("font-size: 14pt; background-color: #4CAF50; color: white;")
        self._start_button.clicked.connect(self._start_session)

        self._pause_button = QtWidgets.QPushButton("⏸ Pause")
        self._pause_button.setMinimumHeight(50)
        self._pause_button.setEnabled(False)
        self._pause_button.clicked.connect(self._pause_session)

        self._end_button = QtWidgets.QPushButton("⏹ End Session")
        self._end_button.setMinimumHeight(50)
        self._end_button.setStyleSheet("font-size: 14pt; background-color: #f44336; color: white;")
        self._end_button.setEnabled(False)
        self._end_button.clicked.connect(self._end_session)

        self._settings_button = QtWidgets.QPushButton("⚙ Settings")
        self._settings_button.setMinimumHeight(50)

        self._help_button = QtWidgets.QPushButton("❓ Help")
        self._help_button.setMinimumHeight(50)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._start_button, 2)
        layout.addWidget(self._pause_button, 1)
        layout.addWidget(self._end_button, 2)
        layout.addStretch()
        layout.addWidget(self._settings_button)
        layout.addWidget(self._help_button)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget

    def _start_session(self) -> None:
        """Start new coaching session."""
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
                self._status_label.setText("Starting cameras...")
                QtWidgets.QApplication.processEvents()

                # Use lower resolution for coaching app to avoid memory allocation errors
                # Create modified config with conservative camera settings
                from configs.settings import CameraConfig
                coaching_camera_config = CameraConfig(
                    width=640,
                    height=480,
                    fps=30,
                    pixfmt=self._config.camera.pixfmt,
                    exposure_us=self._config.camera.exposure_us,
                    gain=self._config.camera.gain,
                    wb_mode=self._config.camera.wb_mode,
                    wb=self._config.camera.wb,
                    queue_depth=self._config.camera.queue_depth,
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
                logger.info("Capture started successfully with 640x480@30fps")
            else:
                logger.info("Capture already running, skipping camera start")

            # Start recording
            logger.info(f"Starting recording for session: {self._session_name}")
            self._status_label.setText("Starting recording...")
            QtWidgets.QApplication.processEvents()

            self._service.start_recording(
                pitch_id="session",
                session_name=self._session_name,
                mode="session",
            )
            logger.info("Recording started successfully")

            # Save camera serials to app state for next time
            state = load_state()
            state["last_left_camera"] = left_serial
            state["last_right_camera"] = right_serial
            save_state(state)
            logger.info(f"Saved camera selections: left={left_serial}, right={right_serial}")

        except Exception as e:
            logger.error(f"Failed to start session: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Session Start Error",
                f"Failed to start session:\n{str(e)}",
            )
            return

        # Update UI
        self._session_label.setText(f"Session: {self._session_name}")
        self._pitcher_label.setText(f"Pitcher: {self._pitcher_name}")
        self._pitch_count_label.setText("Pitches: 0")
        self._recording_indicator.show()

        # Clear visualizations
        self._heat_map.clear()
        self._left_overlay.clear_latest_pitch()
        self._right_overlay.clear_latest_pitch()
        self._trajectory.clear()

        # Update buttons
        self._start_button.setEnabled(False)
        self._pause_button.setEnabled(True)
        self._end_button.setEnabled(True)

        # Update status
        self._status_label.setText("● Recording in progress... Ready to track pitches.")
        self._status_label.setStyleSheet("padding: 5px; background-color: #c8e6c9; color: #2e7d32; font-weight: bold;")

        self._session_active = True

    def _pause_session(self) -> None:
        """Pause current session."""
        # TODO: Implement pause logic
        self._status_label.setText("⏸ Session paused. Click 'Start Session' to resume.")
        self._status_label.setStyleSheet("padding: 5px; background-color: #fff9c4;")

    def _end_session(self) -> None:
        """End current session and show summary."""
        reply = QtWidgets.QMessageBox.question(
            self,
            "End Session",
            f"End session '{self._session_name}' with {self._pitch_count} pitches?\n\n"
            "Session summary will be displayed.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Stop recording
            try:
                self._status_label.setText("Stopping recording...")
                QtWidgets.QApplication.processEvents()

                summary = self._service.stop_recording()

                # Show summary
                if summary:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Session Complete",
                        f"Session: {self._session_name}\n"
                        f"Pitcher: {self._pitcher_name}\n"
                        f"Pitches: {summary.pitch_count}\n"
                        f"Strikes: {summary.strike_count}\n"
                        f"Balls: {summary.ball_count}\n\n"
                        f"Session data saved.",
                    )

            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Session End Error",
                    f"Error stopping session:\n{str(e)}",
                )

            # Reset UI
            self._session_label.setText("Session: <not started>")
            self._pitcher_label.setText("Pitcher: <not selected>")
            self._pitch_count_label.setText("Pitches: 0")
            self._recording_indicator.hide()

            # Update buttons
            self._start_button.setEnabled(True)
            self._pause_button.setEnabled(False)
            self._end_button.setEnabled(False)

            # Update status
            self._status_label.setText("Session ended. Ready for next session.")
            self._status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0;")

            self._session_active = False

    def closeEvent(self, event) -> None:
        """Handle window close event - stop capture and recording."""
        # Stop timers
        self._preview_timer.stop()
        self._metrics_timer.stop()

        if self._session_active:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Session Active",
                "A session is currently active. End session before closing?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No
                | QtWidgets.QMessageBox.StandardButton.Cancel,
            )

            if reply == QtWidgets.QMessageBox.StandardButton.Cancel:
                event.ignore()
                # Restart timers if user cancels
                self._preview_timer.start(33)
                self._metrics_timer.start(100)
                return
            elif reply == QtWidgets.QMessageBox.StandardButton.Yes:
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

            # Update left view
            if left_frame is not None:
                pixmap = self._frame_to_pixmap(left_frame.image)
                if pixmap:
                    scaled = pixmap.scaled(
                        self._left_view.size(),
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                    self._left_view.setPixmap(scaled)

            # Update right view
            if right_frame is not None:
                pixmap = self._frame_to_pixmap(right_frame.image)
                if pixmap:
                    scaled = pixmap.scaled(
                        self._right_view.size(),
                        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                        QtCore.Qt.TransformationMode.SmoothTransformation,
                    )
                    self._right_view.setPixmap(scaled)

            # Update overlay sizes to match camera views
            self._left_overlay.setGeometry(self._left_view.geometry())
            self._right_overlay.setGeometry(self._right_view.geometry())

        except Exception as e:
            # Log preview errors for debugging
            logger.error(f"Preview update failed: {e}", exc_info=True)

    def _frame_to_pixmap(self, image) -> Optional[QtGui.QPixmap]:
        """Convert numpy image to QPixmap."""
        try:
            import numpy as np

            # Ensure image is uint8
            if image.dtype != np.uint8:
                image = image.astype(np.uint8)

            # Convert BGR to RGB if needed
            if len(image.shape) == 3 and image.shape[2] == 3:
                import cv2
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Create QImage
            height, width = image.shape[:2]
            if len(image.shape) == 3:
                bytes_per_line = 3 * width
                q_image = QtGui.QImage(
                    image.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_RGB888,
                )
            else:
                bytes_per_line = width
                q_image = QtGui.QImage(
                    image.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_Grayscale8,
                )

            return QtGui.QPixmap.fromImage(q_image)

        except Exception as e:
            logger.warning(f"Failed to convert frame to pixmap: {e}")
            return None

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

                # Get latest pitch
                if recent_pitches:
                    latest = recent_pitches[-1]

                    # Update metrics display
                    speed_mph = latest.measured_speed_mph or 0.0
                    self._speed_label.setText(f"Speed: {speed_mph:.1f} mph")

                    # Update break and track location
                    if latest.plate_x_in is not None and latest.plate_z_in is not None:
                        self._hbreak_label.setText(f"H-Break: {latest.plate_x_in:+.1f} in")
                        self._vbreak_label.setText(f"V-Break: {latest.plate_z_in:+.1f} in")

                        # Calculate strike zone and update visualizations
                        self._update_pitch_location(latest.plate_x_in, latest.plate_z_in)

                        # Update trajectory visualization
                        self._update_trajectory(latest)

                    # Update result
                    result = "STRIKE" if latest.is_strike else "BALL"
                    result_color = "#4CAF50" if latest.is_strike else "#FF5722"
                    self._result_label.setText(f"Result: {result}")
                    self._result_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {result_color};")

                    # Update recent pitches list
                    self._update_recent_pitches_list(recent_pitches)

        except Exception:
            # Silently ignore metrics errors
            pass

    def _update_trajectory(self, pitch_summary) -> None:
        """Update trajectory visualization with pitch path.

        Args:
            pitch_summary: PitchSummary with trajectory data
        """
        # Get plate crossing point (convert inches to feet)
        plate_y = 0.0  # Plate position
        plate_z = pitch_summary.plate_z_in / 12.0 if pitch_summary.plate_z_in is not None else 2.5

        # Estimate release point (typical values)
        # Pitchers release around 54-56 feet from plate, 5-7 feet high
        release_y = 55.0  # feet from plate
        release_z = 6.0  # feet above ground

        # Create simple parabolic trajectory
        # Use 20 points from release to plate
        num_points = 20
        y_positions = []
        z_positions = []

        for i in range(num_points):
            t = i / (num_points - 1)  # 0.0 to 1.0

            # Linear interpolation for Y (distance)
            y = release_y * (1 - t) + plate_y * t

            # Parabolic arc for Z (height) - simple quadratic
            # z = at^2 + bt + c
            # At t=0: z = release_z
            # At t=1: z = plate_z
            # Peak somewhere in middle (use simple parabola)
            a = release_z - 2 * release_z + plate_z  # Coefficient for parabola
            b = 2 * (release_z - plate_z) - a
            c = release_z

            z = a * t * t + b * t + c

            y_positions.append(y)
            z_positions.append(z)

        # Add trajectory to widget
        self._trajectory.add_trajectory(y_positions, z_positions)

    def _update_pitch_location(self, plate_x_in: float, plate_z_in: float) -> None:
        """Update heat map and strike zone overlays with pitch location.

        Args:
            plate_x_in: Horizontal position in inches from plate center (- is left, + is right)
            plate_z_in: Vertical position in inches from ground
        """
        # Get strike zone dimensions from config
        sz_config = self._config.strike_zone

        # Strike zone boundaries (in inches)
        zone_width = 17.0  # Home plate width
        zone_height = sz_config.height_in
        zone_left = -zone_width / 2
        zone_right = zone_width / 2
        zone_bottom = sz_config.bottom_in
        zone_top = zone_bottom + zone_height

        # Calculate normalized position (0.0 = left/bottom, 1.0 = right/top)
        # Add some margin around strike zone for visualization
        margin_x = zone_width * 0.5  # 50% margin on each side
        margin_z = zone_height * 0.3  # 30% margin top/bottom

        viz_left = zone_left - margin_x
        viz_right = zone_right + margin_x
        viz_bottom = zone_bottom - margin_z
        viz_top = zone_top + margin_z

        # Normalize to 0.0-1.0
        norm_x = (plate_x_in - viz_left) / (viz_right - viz_left)
        norm_z = 1.0 - ((plate_z_in - viz_bottom) / (viz_top - viz_bottom))  # Invert Y (screen coords)

        # Clamp to visible range
        norm_x = max(0.0, min(1.0, norm_x))
        norm_z = max(0.0, min(1.0, norm_z))

        # Update strike zone overlays
        self._left_overlay.set_latest_pitch(norm_x, norm_z)
        self._right_overlay.set_latest_pitch(norm_x, norm_z)

        # Calculate which zone (0-2, 0-2) the pitch landed in for heat map
        # Only count if inside actual strike zone
        if zone_left <= plate_x_in <= zone_right and zone_bottom <= plate_z_in <= zone_top:
            zone_x = int((plate_x_in - zone_left) / zone_width * 3)
            zone_z = int((plate_z_in - zone_bottom) / zone_height * 3)

            # Clamp to 0-2 range
            zone_x = max(0, min(2, zone_x))
            zone_z = max(0, min(2, zone_z))

            # Add to heat map (note: zone_z is already in correct coordinates for grid)
            self._heat_map.add_pitch(zone_x, zone_z)

    def _update_recent_pitches_list(self, pitches) -> None:
        """Update recent pitches list widget."""
        self._recent_list.clear()

        # Show last 10 pitches (most recent first)
        for i, pitch in enumerate(reversed(pitches[-10:])):
            speed_mph = pitch.measured_speed_mph or 0.0
            result = "STRIKE" if pitch.is_strike else "BALL"
            color = "#4CAF50" if pitch.is_strike else "#FF5722"

            item_text = f"{len(pitches) - i}. {speed_mph:.1f} mph - {result}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setForeground(QtGui.QColor(color))
            self._recent_list.addItem(item)

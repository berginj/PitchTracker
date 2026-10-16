"""Review window for analyzing recorded sessions.

This module is the thin facade/shell. Domain controllers live in sibling modules:
- _session_controller: session load/nav/delete
- _playback_controller: timer, speed, stepping
- _export_controller: config/annotation export
- _trajectory_controller: overlay rendering & diagnostics
- _menu_bar: menu construction
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.review import PitchScore, ReviewService
from ui.review._export_controller import ExportController
from ui.review._menu_bar import initialize_review_menu
from ui.review._playback_controller import PlaybackController
from ui.review._session_controller import SessionController
from ui.review._trajectory_controller import TrajectoryController
from ui.review.widgets import (
    ParameterPanel,
    PitchListWidget,
    PlaybackControls,
    TimelineWidget,
    TrajectoryDiagnosticsPanel,
    VideoDisplayWidget,
)
from ui.themes import apply_standard_layout, get_style_manager
from ui.workspace.contracts import ReviewSelection
from ui.review.workspace_host import ReviewWorkspaceHost
from ui.review.pitch_feedback import PitchFeedback

logger = logging.getLogger(__name__)


class ReviewWindow(ReviewWorkspaceHost):
    """Main window for review and training mode.

    Allows users to:
    - Load previously recorded sessions
    - Replay videos with playback controls
    - Adjust detection parameters
    - Annotate and score pitches
    - Export tuned configurations

    """

    closed = QtCore.Signal()
    selection_changed = QtCore.Signal(object)
    exit_requested = QtCore.Signal()
    _feedback: PitchFeedback
    _parameter_panel: ParameterPanel
    _trajectory_diagnostics_panel: TrajectoryDiagnosticsPanel
    _pitch_list: PitchListWidget

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize review window.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("PitchTracker - Review Mode")
        self.resize(1600, 1000)
        self._style_manager = get_style_manager()

        # Review service backend
        self._service = ReviewService()
        self._measurement_dialog: QtWidgets.QDialog | None = None
        self._close_after_measurement = False
        self._selected_pitch_id: str | None = None
        self._workspace_hosted = False
        self._workspace_shutdown = False
        self._pitch_video_available = True

        # Status bar (needed by controllers)
        self._status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready. Open a session to begin.")

        # Controllers
        self._session_ctrl = SessionController(
            self._service,
            parent_widget=self,
            on_session_loaded=self._on_session_loaded,
            on_session_closed=self._on_session_closed,
            status_bar=self._status_bar,
        )
        self._playback_ctrl = PlaybackController(
            self._service,
            status_bar=self._status_bar,
            on_frame_changed=self._update_video_displays,
            get_timeline_updater=self._timeline_set_frame,
        )
        self._trajectory_ctrl = TrajectoryController(self._service)

        # Build UI (creates widgets needed by export controller)
        self._build_ui()

        self._export_ctrl = ExportController(
            self._service,
            parent_widget=self,
            get_pitch_scores=self._pitch_list.get_pitch_scores,
        )

        self._update_ui_state()
        logger.info("ReviewWindow initialized")

    # Timeline helper (needed before _build_ui runs)

    def _timeline_set_frame(self, frame_index: int) -> None:
        """Proxy for timeline widget frame update."""
        self._timeline.set_current_frame(frame_index)

    # UI Construction

    def _build_ui(self) -> None:
        """Build the main UI layout."""
        self._create_menu_bar()
        content = self._build_content_area()
        self.setCentralWidget(content)

    def _create_menu_bar(self) -> None:
        """Create menu bar with File, Playback, Tools, Export menus."""
        actions = initialize_review_menu(self)
        self._menu_actions = actions
        self._prev_session_action = actions.prev_session
        self._next_session_action = actions.next_session
        self._delete_session_action = actions.delete_session
        self._trajectory_action = actions.trajectory

    def _build_content_area(self) -> QtWidgets.QWidget:
        """Build main content area with video displays and controls."""
        left_section = self._build_video_and_controls_section()
        right_section = self._build_right_panel()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(left_section)
        splitter.addWidget(right_section)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setAccessibleName("Review layout splitter")

        main_layout = QtWidgets.QHBoxLayout()
        apply_standard_layout(main_layout)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addWidget(splitter)

        container = QtWidgets.QWidget()
        container.setObjectName("ReviewShell")
        container.setLayout(main_layout)
        return container

    def _build_right_panel(self) -> QtWidgets.QWidget:
        from ui.review.experience_layout import build_pitch_panel
        return build_pitch_panel(self)

    def _build_video_and_controls_section(self) -> QtWidgets.QWidget:
        """Build video displays, timeline, and playback controls."""
        video_section = self._build_video_section()

        self._timeline = TimelineWidget()
        self._timeline.seek_requested.connect(
            lambda idx: self._playback_ctrl.seek_to_frame(idx)
        )

        self._controls = PlaybackControls()
        self._controls.play_pause_clicked.connect(self._playback_ctrl.toggle_playback)
        self._controls.step_forward_clicked.connect(self._playback_ctrl.step_forward)
        self._controls.step_backward_clicked.connect(self._playback_ctrl.step_backward)
        self._controls.seek_start_clicked.connect(self._playback_ctrl.seek_to_start)
        self._controls.seek_end_clicked.connect(self._playback_ctrl.seek_to_end)
        self._controls.speed_changed.connect(self._playback_ctrl.on_speed_changed)
        self._controls.loop_toggled.connect(self._playback_ctrl.on_loop_toggled)
        self._controls.prev_pitch_clicked.connect(self._prev_pitch)
        self._controls.next_pitch_clicked.connect(self._next_pitch)

        self._playback_ctrl.set_controls_widget(self._controls)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(video_section, 1)
        layout.addWidget(self._timeline)
        layout.addWidget(self._controls)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        return container

    def _build_video_section(self) -> QtWidgets.QWidget:
        """Build dual video display section."""
        self._left_display = VideoDisplayWidget()
        self._left_display.annotation_added.connect(
            lambda x, y: self._on_annotation_added("left", x, y)
        )
        self._right_display = VideoDisplayWidget()
        self._right_display.annotation_added.connect(
            lambda x, y: self._on_annotation_added("right", x, y)
        )
        cameras = QtWidgets.QTabWidget()
        cameras.setAccessibleName("Recorded camera view")
        cameras.addTab(self._left_display, "Left Camera")
        cameras.addTab(self._right_display, "Right Camera")
        return cameras

    # Session lifecycle callbacks

    def _on_session_loaded(self) -> None:
        """Called by SessionController after successful load."""
        session = self._service.session
        if session is None:
            return
        self._playback_ctrl.stop_playback()
        self._trajectory_ctrl.clear()
        self._trajectory_action.setChecked(False)
        self._pitch_video_available = True
        self._selected_pitch_id = None
        self.setWindowTitle(f"PitchTracker - Review Mode - {session.session_id}")

        self._timeline.set_total_frames(self._service.total_frames)
        self._timeline.set_fps(self._service.video_reader.fps)

        if self._service.detector_config:
            cfg = self._service.detector_config
            from detect.config import Mode

            parameter_blocker = QtCore.QSignalBlocker(self._parameter_panel)
            self._parameter_panel.load_parameters(
                mode=Mode(cfg.mode),
                frame_diff_threshold=cfg.frame_diff_threshold,
                bg_diff_threshold=cfg.bg_diff_threshold,
                min_area=cfg.filters.min_area,
                max_area=cfg.filters.max_area or 500,
                min_circularity=cfg.filters.min_circularity,
            )
            parameter_blocker.unblock()

        pitch_scores = self._service.pitch_scores
        self._pitch_list.load_pitches(session.pitches, pitch_scores)
        if session.pitches:
            self._trajectory_diagnostics_panel.load_pitch(session.pitches[0])
        else:
            self._trajectory_diagnostics_panel.clear()

        self._trajectory_ctrl.init_renderers()
        if session.pitches:
            self._trajectory_ctrl.load_trajectory_for_pitch(0)

        if session.pitches:
            self._navigate_to_pitch(0)
        else:
            self._feedback.clear()
            self._feedback.labels["identity"].setText("This session has no recorded pitches")
            self._feedback.labels["playback"].setText(self._service.playback_issue or "Full session video has no pitch association.")
            self._update_video_displays()
            self.selection_changed.emit(self.selection())
        self._update_ui_state()

    def _on_session_closed(self) -> None:
        """Called by SessionController before service.close()."""
        self._playback_ctrl.stop_playback()
        self._selected_pitch_id = None
        self.selection_changed.emit(ReviewSelection())
        self._left_display.clear()
        self._right_display.clear()
        self._timeline.reset()
        self._pitch_list.clear()
        self._trajectory_diagnostics_panel.clear()
        self._feedback.clear()
        self._controls.setEnabled(False)
        self._trajectory_ctrl.clear()
        self._trajectory_action.setChecked(False)
        self.setWindowTitle("PitchTracker - Review Mode")
        self._update_ui_state()

    # Pitch navigation

    def _prev_pitch(self) -> None:
        """Navigate to previous pitch in session."""
        self._relative_pitch(-1)

    def _next_pitch(self) -> None:
        """Navigate to next pitch in session."""
        self._relative_pitch(1)

    def _relative_pitch(self, step: int) -> None:
        session = self._service.session
        if session and session.pitches:
            index = next((i for i, p in enumerate(session.pitches) if p.pitch_id == self._selected_pitch_id), 0)
            self._navigate_to_pitch(max(0, min(len(session.pitches) - 1, index + step)))

    def _navigate_to_pitch(self, pitch_index: int) -> None:
        """Seek to pitch and update trajectory/diagnostics."""
        session = self._service.session
        if session is None or not 0 <= pitch_index < len(session.pitches):
            return
        self._playback_ctrl.stop_playback()
        self._selected_pitch_id = session.pitches[pitch_index].pitch_id
        self._pitch_list.select_pitch(pitch_index)
        self._left_display.clear_annotations()
        self._right_display.clear_annotations()
        self._trajectory_ctrl.load_trajectory_for_pitch(pitch_index)
        self._trajectory_diagnostics_panel.load_pitch(
            session.pitches[pitch_index]
        )
        self._pitch_video_available = bool(self._service.seek_to_pitch(pitch_index))
        mapping = self._service.playback_for_pitch(pitch_index)
        self._feedback.load_pitch(session.pitches[pitch_index], str(mapping.reason) if not self._pitch_video_available else "")
        self._controls.setEnabled(self._pitch_video_available)
        self._timeline.setEnabled(self._pitch_video_available)
        self._timeline.set_current_frame(self._service.current_frame_index)
        self._update_video_displays()
        self.selection_changed.emit(self.selection())
        pitches = session.pitches
        self._status_bar.showMessage(
            f"Jumped to pitch {pitch_index + 1}/{len(pitches)}"
        )

    def _on_pitch_highlighted(self, pitch_index: int) -> None:
        """Preview diagnostics for highlighted pitch row."""
        self._navigate_to_pitch(pitch_index)

    def _on_pitch_selected(self, pitch_index: int) -> None:
        """Handle pitch selection from list."""
        self._navigate_to_pitch(pitch_index)

    def _show_trajectory_diagnostics(self, pitch_index: int) -> None:
        """Load diagnostics panel for a pitch index."""
        session = self._service.session
        if session is None:
            self._trajectory_diagnostics_panel.clear()
            return
        pitches = session.pitches
        if pitch_index < 0 or pitch_index >= len(pitches):
            self._trajectory_diagnostics_panel.clear()
            return
        self._trajectory_diagnostics_panel.load_pitch(pitches[pitch_index])

    def _on_pitch_scored(self, pitch_id: str, score: PitchScore) -> None:
        """Handle pitch scoring."""
        self._service.score_pitch(pitch_id, score)
        self._status_bar.showMessage(f"Scored {pitch_id}: {score.value}")
        logger.info(f"Pitch scored: {pitch_id} = {score.value}")

    # Detection parameters

    def _on_parameters_changed(self) -> None:
        """Handle parameter changes - update detector and refresh."""
        if not self._service.session:
            return
        self._service.update_detector_config(
            frame_diff_threshold=self._parameter_panel.frame_diff_threshold,
            bg_diff_threshold=self._parameter_panel.bg_diff_threshold,
            min_area=self._parameter_panel.min_area,
            max_area=self._parameter_panel.max_area,
            min_circularity=self._parameter_panel.min_circularity,
            mode=self._parameter_panel.mode,
        )
        self._update_video_displays()
        self._status_bar.showMessage("Detection parameters updated")

    # Video display

    def _update_video_displays(self) -> None:
        """Update video displays with current frames and detections."""
        if not self._pitch_video_available:
            self._left_display.clear()
            self._right_display.clear()
            return
        left_frame, right_frame = self._service.get_current_frames()
        if left_frame is None or right_frame is None:
            self._left_display.clear()
            self._right_display.clear()
            return

        try:
            left_det: list = []
            right_det: list = []

            if self._trajectory_ctrl.overlay_enabled and self._trajectory_ctrl.current_observations:
                left_frame = self._trajectory_ctrl.apply_overlay(left_frame, "left")
                right_frame = self._trajectory_ctrl.apply_overlay(right_frame, "right")

            self._left_display.set_frame(left_frame, left_det)
            self._right_display.set_frame(right_frame, right_det)

            self._status_bar.showMessage(
                f"Frame {self._service.current_frame_index + 1}/{self._service.total_frames} "
                f"| Detections: L={len(left_det)}, R={len(right_det)}"
            )
        except Exception as e:
            logger.exception(f"Detection failed: {e}")
            self._left_display.set_frame(left_frame)
            self._right_display.set_frame(right_frame)

    # Annotations & tools

    def _run_frame_detection(self) -> None:
        from ui.review.experience_layout import run_frame_detection
        run_frame_detection(self)

    def _toggle_annotation_mode(self, checked: bool) -> None:
        """Toggle annotation mode on/off."""
        self._left_display.set_annotation_mode(checked)
        self._right_display.set_annotation_mode(checked)
        mode_str = "ON" if checked else "OFF"
        self._status_bar.showMessage(f"Annotation mode: {mode_str}")
        logger.info(f"Annotation mode: {mode_str}")

    def _toggle_trajectory_overlay(self, checked: bool) -> None:
        """Toggle trajectory overlay on/off."""
        if checked and not self._trajectory_ctrl.overlay_available:
            self._trajectory_action.setChecked(False)
            self._status_bar.showMessage("Trajectory overlay unavailable: recorded calibration is missing or invalid.")
            return
        self._trajectory_ctrl.overlay_enabled = checked
        mode_str = "ON" if checked else "OFF"
        self._status_bar.showMessage(f"Trajectory overlay: {mode_str}")
        logger.info(f"Trajectory overlay: {mode_str}")
        if self._service.session:
            self._update_video_displays()

    def _clear_annotations(self) -> None:
        """Clear all manual annotations."""
        self._left_display.clear_annotations()
        self._right_display.clear_annotations()
        self._status_bar.showMessage("Annotations cleared")
        logger.info("Annotations cleared")

    def _on_annotation_added(self, camera: str, x: float, y: float) -> None:
        """Handle annotation added to video display."""
        frame_index = self._service.current_frame_index
        self._service.add_annotation(frame_index, camera, x, y)
        self._status_bar.showMessage(
            f"Added annotation: {camera} camera at ({x:.1f}, {y:.1f}) frame {frame_index}"
        )
        logger.info(f"Annotation added: {camera} ({x:.1f}, {y:.1f}) at frame {frame_index}")

    # UI state

    def _update_ui_state(self) -> None:
        """Update navigation action enabled states."""
        has_session = self._service.session is not None
        self._controls.setEnabled(has_session and self._pitch_video_available and self._service.playback_available)
        self._timeline.setEnabled(self._controls.isEnabled())
        self._prev_session_action.setEnabled(self._session_ctrl.can_go_previous())
        self._next_session_action.setEnabled(self._session_ctrl.can_go_next())
        self._delete_session_action.setEnabled(has_session)

        nav_state = self._session_ctrl.get_navigation_state()
        if nav_state:
            current = self._status_bar.currentMessage()
            if " | " in current:
                base = current.split(" | ")[0]
                self._status_bar.showMessage(f"{base} | {nav_state}")
            else:
                self._status_bar.showMessage(f"Ready | {nav_state}")

    def _load_session(self, session_dir: Path) -> None:
        """Compatibility: delegates to session controller."""
        self._session_ctrl.load_session(session_dir)

    def _close_session(self) -> None:
        """Compatibility: delegates to session controller."""
        self._session_ctrl.close_session()

    def _show_trajectory_diagnostics_for_pitch(self, pitch_index: int) -> None:
        """Compatibility: delegates to _show_trajectory_diagnostics."""
        self._show_trajectory_diagnostics(pitch_index)

    def _open_measurement_validation(self) -> None:
        from ui.review.measurement_validation import open_measurement_validation
        session = self._service.session
        open_measurement_validation(self, session.session_dir if session else None)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle window close event."""
        if self._workspace_hosted and not self._workspace_shutdown:
            event.ignore()
            self.exit_requested.emit()
            return
        if self._measurement_dialog is not None:
            self._close_after_measurement = True
            self._measurement_dialog.reject()
            event.ignore()
            return
        self._playback_ctrl.teardown()
        self._service.close()
        self.closed.emit()
        event.accept()
        logger.info("ReviewWindow closed")

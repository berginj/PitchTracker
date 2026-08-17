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
from collections.abc import Callable
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.review import PitchScore, ReviewService
from ui.review._export_controller import ExportController
from ui.review._menu_bar import build_menu_bar
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

    closed = QtCore.Signal()

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
        handlers: dict[str, Callable[..., object]] = {
            "open_session": self._session_ctrl.open_session_dialog,
            "review_all": self._session_ctrl.review_all_sessions,
            "prev_session": self._session_ctrl.previous_session,
            "next_session": self._session_ctrl.next_session,
            "delete_session": self._session_ctrl.delete_current_session,
            "close_session": self._session_ctrl.close_session,
            "play_pause": self._playback_ctrl.toggle_playback,
            "step_forward": self._playback_ctrl.step_forward,
            "step_backward": self._playback_ctrl.step_backward,
            "seek_start": self._playback_ctrl.seek_to_start,
            "seek_end": self._playback_ctrl.seek_to_end,
            "toggle_annotation": self._toggle_annotation_mode,
            "clear_annotations": self._clear_annotations,
            "toggle_trajectory": self._toggle_trajectory_overlay,
            "export_config": lambda: self._export_ctrl.export_config(),
            "export_annotations": lambda: self._export_ctrl.export_annotations(),
        }
        actions = build_menu_bar(self, handlers)
        self._prev_session_action = actions.prev_session
        self._next_session_action = actions.next_session
        self._delete_session_action = actions.delete_session
        self._annotation_action = actions.annotation
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
        main_layout.addWidget(splitter)

        container = QtWidgets.QWidget()
        container.setObjectName("ReviewShell")
        container.setLayout(main_layout)
        return container

    def _build_right_panel(self) -> QtWidgets.QWidget:
        """Build right panel with parameters, diagnostics, and pitch list."""
        self._parameter_panel = ParameterPanel()
        self._parameter_panel.parameter_changed.connect(self._on_parameters_changed)

        self._trajectory_diagnostics_panel = TrajectoryDiagnosticsPanel()

        self._pitch_list = PitchListWidget()
        self._pitch_list.pitch_highlighted.connect(self._on_pitch_highlighted)
        self._pitch_list.pitch_selected.connect(self._on_pitch_selected)
        self._pitch_list.pitch_scored.connect(self._on_pitch_scored)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._parameter_panel)
        layout.addWidget(self._trajectory_diagnostics_panel)
        layout.addWidget(self._pitch_list, 1)

        inner = QtWidgets.QWidget()
        inner.setLayout(layout)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(280)
        scroll.setWidget(inner)
        return scroll

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
        left_group = QtWidgets.QGroupBox("Left Camera")
        self._left_display = VideoDisplayWidget()
        self._left_display.annotation_added.connect(
            lambda x, y: self._on_annotation_added("left", x, y)
        )
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self._left_display)
        left_group.setLayout(left_layout)

        right_group = QtWidgets.QGroupBox("Right Camera")
        self._right_display = VideoDisplayWidget()
        self._right_display.annotation_added.connect(
            lambda x, y: self._on_annotation_added("right", x, y)
        )
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self._right_display)
        right_group.setLayout(right_layout)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(left_group)
        layout.addWidget(right_group)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        return container

    # Session lifecycle callbacks

    def _on_session_loaded(self) -> None:
        """Called by SessionController after successful load."""
        session = self._service.session
        if session is None:
            return
        self.setWindowTitle(f"PitchTracker - Review Mode - {session.session_id}")

        self._timeline.set_total_frames(self._service.total_frames)
        self._timeline.set_fps(self._service.video_reader.fps)

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

        pitch_scores = self._service._pitch_scores
        self._pitch_list.load_pitches(session.pitches, pitch_scores)
        if session.pitches:
            self._trajectory_diagnostics_panel.load_pitch(session.pitches[0])
        else:
            self._trajectory_diagnostics_panel.clear()

        self._trajectory_ctrl.init_renderers()
        if session.pitches:
            self._trajectory_ctrl.load_trajectory_for_pitch(0)

        self._update_video_displays()
        self._update_ui_state()

    def _on_session_closed(self) -> None:
        """Called by SessionController before service.close()."""
        self._playback_ctrl.stop_playback()
        self._left_display.clear()
        self._right_display.clear()
        self._timeline.reset()
        self._pitch_list.clear()
        self._trajectory_diagnostics_panel.clear()
        self._trajectory_ctrl.clear()
        self._trajectory_action.setChecked(False)
        self.setWindowTitle("PitchTracker - Review Mode")
        self._update_ui_state()

    # Pitch navigation

    def _prev_pitch(self) -> None:
        """Navigate to previous pitch in session."""
        target_idx = self._playback_ctrl.prev_pitch()
        if target_idx is not None:
            self._navigate_to_pitch(target_idx)

    def _next_pitch(self) -> None:
        """Navigate to next pitch in session."""
        target_idx = self._playback_ctrl.next_pitch()
        if target_idx is not None:
            self._navigate_to_pitch(target_idx)

    def _navigate_to_pitch(self, pitch_index: int) -> None:
        """Seek to pitch and update trajectory/diagnostics."""
        session = self._service.session
        if session is None:
            return
        self._trajectory_ctrl.load_trajectory_for_pitch(pitch_index)
        self._trajectory_diagnostics_panel.load_pitch(
            session.pitches[pitch_index]
        )
        self._playback_ctrl.seek_to_pitch(pitch_index)
        pitches = session.pitches
        self._status_bar.showMessage(
            f"Jumped to pitch {pitch_index + 1}/{len(pitches)}"
        )

    def _on_pitch_highlighted(self, pitch_index: int) -> None:
        """Preview diagnostics for highlighted pitch row."""
        self._show_trajectory_diagnostics(pitch_index)

    def _on_pitch_selected(self, pitch_index: int) -> None:
        """Handle pitch selection from list."""
        session = self._service.session
        if session is None:
            return
        self._trajectory_ctrl.load_trajectory_for_pitch(pitch_index)
        self._show_trajectory_diagnostics(pitch_index)
        self._playback_ctrl.seek_to_pitch(pitch_index)
        pitch = session.pitches[pitch_index]
        self._status_bar.showMessage(f"Navigated to pitch: {pitch.pitch_id}")

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
        left_frame, right_frame = self._service.get_current_frames()
        if left_frame is None or right_frame is None:
            return

        try:
            left_det, right_det = self._service.run_detection_on_current_frame()

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

    def _toggle_annotation_mode(self, checked: bool) -> None:
        """Toggle annotation mode on/off."""
        self._left_display.set_annotation_mode(checked)
        self._right_display.set_annotation_mode(checked)
        mode_str = "ON" if checked else "OFF"
        self._status_bar.showMessage(f"Annotation mode: {mode_str}")
        logger.info(f"Annotation mode: {mode_str}")

    def _toggle_trajectory_overlay(self, checked: bool) -> None:
        """Toggle trajectory overlay on/off."""
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

    # Compatibility shims for existing tests

    def _load_session(self, session_dir: Path) -> None:
        """Compatibility: delegates to session controller."""
        self._session_ctrl.load_session(session_dir)

    def _close_session(self) -> None:
        """Compatibility: delegates to session controller."""
        self._session_ctrl.close_session()

    def _show_trajectory_diagnostics_for_pitch(self, pitch_index: int) -> None:
        """Compatibility: delegates to _show_trajectory_diagnostics."""
        self._show_trajectory_diagnostics(pitch_index)

    # Lifecycle

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle window close event."""
        self._playback_ctrl.teardown()
        self._service.close()
        self.closed.emit()
        event.accept()
        logger.info("ReviewWindow closed")

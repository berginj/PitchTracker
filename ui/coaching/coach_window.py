"""Coaching window facade — shell/layout only, delegates to focused modules.

This module is the public entry point for the coaching UI. Session lifecycle
logic lives in ``session_controller``, mode switching in ``mode_composition``,
and pitch/metrics presentation in ``pitch_display``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from app.qt_pipeline_service import QtPipelineService
from app.services.rig_profile import RigProfileService
from configs.settings import load_config
from ui.coaching.mode_composition import build_mode_content, on_mode_changed
from ui.coaching.pitch_display import PitchDisplay
from ui.coaching.session_controller import SessionController
from ui.coaching.strike_zone_mapping import StrikeZoneOverlayConfig
from ui.coaching.widgets import CompactFatigueIndicator
from ui.themes import apply_standard_layout, get_style_manager

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
        self._backend = backend

        # Load configuration
        if config_path is None:
            config_path = Path("configs/default.yaml")
        self._config_path = config_path
        self._config = load_config(config_path)
        active_profile = RigProfileService(config_path=config_path).load_active()
        if active_profile is not None:
            self._config = RigProfileService(config_path=config_path).apply_profile_to_config(
                self._config, active_profile, preserve_camera_mode=False
            )

        # Pipeline service
        self._service = QtPipelineService(backend=backend, parent=self)

        # Session state
        self._session_active = False
        self._session_paused = False
        self._pitch_count = 0
        self._session_name = ""
        self._pitcher_name = ""
        self._last_pitch_count = 0
        self._processed_pitch_ids: set[str] = set()
        self._pitch_snapshot: list = []
        self._strike_zone_overlay_config = StrikeZoneOverlayConfig.from_app_config(self._config)

        # Camera config from active rig profile
        self._camera_width = self._config.camera.width
        self._camera_height = self._config.camera.height
        self._camera_fps = self._config.camera.fps
        self._camera_color_mode = self._config.camera.color_mode

        # Delegates
        self._session_ctrl = SessionController(self)
        self._pitch_display = PitchDisplay(self)

        # Build UI
        self._build_ui()

        # Timers
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start(33)

        self._metrics_timer = QtCore.QTimer()
        self._metrics_timer.timeout.connect(self._update_metrics)
        self._metrics_timer.start(100)

        # Signals
        self._service.pitch_started.connect(self._on_pitch_started)
        self._service.pitch_ended.connect(self._on_pitch_ended)

        # Warm camera cache
        self._session_ctrl.warm_camera_cache_async()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build coaching dashboard UI."""
        session_bar = self._build_session_bar()
        main_content = self._build_main_content()
        controls = self._build_controls()

        self._status_label = QtWidgets.QLabel("Ready. Click 'Start Session' to begin.")
        self._style_manager.style_status_indicator(self._status_label, "info")

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addWidget(session_bar)
        layout.addWidget(main_content, 1)
        layout.addWidget(controls)
        layout.addWidget(self._status_label)

        container = QtWidgets.QWidget()
        container.setObjectName("CoachShell")
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _build_session_bar(self) -> QtWidgets.QWidget:
        """Build session information bar."""
        self._session_label = QtWidgets.QLabel("Session: <not started>")
        self._style_manager.style_label(self._session_label, "pageTitle")

        self._pitcher_label = QtWidgets.QLabel("Pitcher: <not selected>")
        self._style_manager.style_label(self._pitcher_label, "muted")

        self._switch_pitcher_btn = QtWidgets.QPushButton("Switch")
        self._switch_pitcher_btn.setMaximumWidth(60)
        self._switch_pitcher_btn.setMaximumHeight(24)
        self._switch_pitcher_btn.setToolTip("Switch to a different pitcher")
        self._style_manager.style_button(self._switch_pitcher_btn, "ghost")
        self._switch_pitcher_btn.clicked.connect(self._switch_pitcher)

        self._pitch_count_label = QtWidgets.QLabel("Pitches: 0")
        self._style_manager.style_label(self._pitch_count_label, "metricAccent")

        self._fatigue_indicator = CompactFatigueIndicator()
        self._fatigue_indicator.setToolTip("Fatigue Monitor - Score and status")

        self._recording_indicator = QtWidgets.QLabel("● Recording")
        self._recording_indicator.setText("Recording")
        self._style_manager.style_status_indicator(self._recording_indicator, "error")
        self._recording_indicator.hide()

        self._quality_indicator = QtWidgets.QLabel("Quality: waiting")
        self._style_manager.style_status_indicator(self._quality_indicator, "info")
        self._diagnostics_button = QtWidgets.QPushButton("Diagnostics")
        self._diagnostics_button.setToolTip(
            "Open detailed capture, tracking, and correction evidence"
        )
        self._style_manager.style_button(self._diagnostics_button, "ghost")
        self._diagnostics_button.clicked.connect(self._show_quality_diagnostics)

        sep1 = QtWidgets.QLabel("|")
        self._style_manager.style_label(sep1, "muted")
        sep2 = QtWidgets.QLabel("|")
        self._style_manager.style_label(sep2, "muted")
        sep3 = QtWidgets.QLabel("|")
        self._style_manager.style_label(sep3, "muted")

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(self._session_label)
        layout.addWidget(sep1)
        layout.addWidget(self._pitcher_label)
        layout.addWidget(self._switch_pitcher_btn)
        layout.addWidget(sep2)
        layout.addWidget(self._pitch_count_label)
        layout.addWidget(sep3)
        layout.addWidget(self._fatigue_indicator)
        layout.addStretch()
        layout.addWidget(self._quality_indicator)
        layout.addWidget(self._diagnostics_button)
        layout.addWidget(self._recording_indicator)

        widget = QtWidgets.QWidget()
        widget.setProperty("surface", "card")
        self._style_manager.polish(widget)
        widget.setLayout(layout)
        return widget

    def _build_main_content(self) -> QtWidgets.QWidget:
        """Build main content area with mode switching."""
        (
            widget,
            self._mode_selector,
            self._mode_stack,
            self._session_tracker,
            self._game_state_mgr,
            self._broadcast_mode,
            self._progression_mode,
            self._game_mode,
        ) = build_mode_content(self._config, self._strike_zone_overlay_config)

        self._mode_selector.currentIndexChanged.connect(self._on_mode_changed)
        return widget

    def _on_mode_changed(self, index: int) -> None:
        """Handle mode selection change."""
        on_mode_changed(index, self._mode_stack, self._pitch_snapshot)

    def _build_controls(self) -> QtWidgets.QWidget:
        """Build control buttons."""
        sm = self._style_manager
        height = sm.theme.button_height_lg

        self._setup_button = QtWidgets.QPushButton("Start Session")
        self._setup_button.setAccessibleName("Start Session")
        self._setup_button.setMinimumHeight(height)
        sm.style_button(self._setup_button, "primary")
        self._setup_button.clicked.connect(self._setup_session)

        self._start_recording_button = QtWidgets.QPushButton("Start Recording")
        self._start_recording_button.setAccessibleName("Start Recording")
        self._start_recording_button.setMinimumHeight(height)
        sm.style_button(self._start_recording_button, "success")
        self._start_recording_button.setEnabled(False)
        self._start_recording_button.clicked.connect(self._start_recording)

        self._pause_button = QtWidgets.QPushButton("Pause")
        self._pause_button.setAccessibleName("Pause Session")
        self._pause_button.setMinimumHeight(height)
        sm.style_button(self._pause_button, "default")
        self._pause_button.setEnabled(False)
        self._pause_button.clicked.connect(self._pause_session)

        self._end_button = QtWidgets.QPushButton("End Session")
        self._end_button.setAccessibleName("End Session")
        self._end_button.setMinimumHeight(height)
        sm.style_button(self._end_button, "danger")
        self._end_button.setEnabled(False)
        self._end_button.clicked.connect(self._end_session)

        self._settings_button = QtWidgets.QPushButton("Settings")
        self._settings_button.setAccessibleName("Settings")
        self._settings_button.setMinimumHeight(height)
        sm.style_button(self._settings_button, "ghost")
        self._settings_button.clicked.connect(self._show_settings)

        self._lane_button = QtWidgets.QPushButton("Adjust Lane")
        self._lane_button.setAccessibleName("Adjust Lane")
        self._lane_button.setMinimumHeight(height)
        sm.style_button(self._lane_button, "default")
        self._lane_button.clicked.connect(self._adjust_lane)
        self._lane_button.setToolTip("Adjust the lane ROI (region where ball tracking occurs)")

        self._review_button = QtWidgets.QPushButton("Review Session")
        self._review_button.setAccessibleName("Review Session")
        self._review_button.setMinimumHeight(height)
        sm.style_button(self._review_button, "default")
        self._review_button.clicked.connect(self._open_review_mode)
        self._review_button.setToolTip("Review and analyze previous sessions")

        self._help_button = QtWidgets.QPushButton("Help")
        self._help_button.setAccessibleName("Help")
        self._help_button.setMinimumHeight(height)
        sm.style_button(self._help_button, "ghost")

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(18, 16, 18, 16)
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
        sm.style_panel(widget, "normal")
        widget.setLayout(layout)
        return widget

    # ------------------------------------------------------------------
    # Status helper
    # ------------------------------------------------------------------

    def _set_status_message(self, message: str, tone: str = "info") -> None:
        """Update the footer status indicator with a semantic tone."""
        self._status_label.setText(message)
        self._style_manager.style_status_indicator(self._status_label, tone)

    # ------------------------------------------------------------------
    # Delegated action slots
    # ------------------------------------------------------------------

    def _setup_session(self) -> None:
        self._session_ctrl.setup_session()

    def _start_recording(self) -> None:
        self._session_ctrl.start_recording()

    def _pause_session(self) -> None:
        self._session_ctrl.pause_session()

    def _end_session(self) -> None:
        self._session_ctrl.end_session()

    def _show_settings(self) -> None:
        self._session_ctrl.show_settings()

    def _adjust_lane(self) -> None:
        self._session_ctrl.adjust_lane()

    def _open_review_mode(self) -> None:
        self._session_ctrl.open_review_mode()

    def _switch_pitcher(self) -> None:
        self._session_ctrl.switch_pitcher()

    def _show_quality_diagnostics(self) -> None:
        self._pitch_display.show_quality_diagnostics()

    # ------------------------------------------------------------------
    # Delegated timer/signal callbacks
    # ------------------------------------------------------------------

    def _update_preview(self) -> None:
        self._pitch_display.update_preview()

    def _on_pitch_started(self, pitch_index: int, pitch_data) -> None:
        self._pitch_display.on_pitch_started(pitch_index, pitch_data)

    def _on_pitch_ended(self, pitch_data) -> None:
        self._pitch_display.on_pitch_ended(pitch_data)

    def _update_metrics(self) -> None:
        self._pitch_display.update_metrics()

    def _update_quality_health(self) -> None:
        self._pitch_display.update_quality_health()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        self._session_ctrl.handle_close_event(event)

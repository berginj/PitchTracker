"""Playback-first layout and expandable research controls for session review."""

from typing import TYPE_CHECKING
import logging

from PySide6 import QtWidgets

from ui.review.pitch_feedback import PitchFeedback
from ui.review.widgets import ParameterPanel, PitchListWidget, TrajectoryDiagnosticsPanel
from ui.themes import get_style_manager

if TYPE_CHECKING:
    from ui.review.review_window import ReviewWindow


def build_pitch_panel(host: "ReviewWindow") -> QtWidgets.QWidget:
    host._feedback = PitchFeedback()
    host._parameter_panel = ParameterPanel()
    host._parameter_panel.parameter_changed.connect(host._on_parameters_changed)
    host._trajectory_diagnostics_panel = TrajectoryDiagnosticsPanel()
    host._pitch_list = PitchListWidget()
    host._pitch_list.pitch_highlighted.connect(host._on_pitch_highlighted)
    host._pitch_list.pitch_selected.connect(host._on_pitch_selected)
    host._pitch_list.pitch_scored.connect(host._on_pitch_scored)
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(host._feedback)
    layout.addWidget(host._pitch_list, 1)
    advanced = QtWidgets.QPushButton("Advanced research tools")
    advanced.setCheckable(True)
    advanced.setAccessibleName("Expand review research tools")
    get_style_manager().style_button(advanced, "ghost")
    layout.addWidget(advanced)
    research = QtWidgets.QWidget()
    tools = QtWidgets.QVBoxLayout(research)
    tools.setContentsMargins(0, 0, 0, 0)
    tools.addWidget(host._parameter_panel)
    detect = QtWidgets.QPushButton("Run detection on this frame")
    detect.setAccessibleName("Run review detection explicitly")
    detect.clicked.connect(host._run_frame_detection)
    tools.addWidget(detect)
    tools.addWidget(host._trajectory_diagnostics_panel)
    notice = QtWidgets.QLabel(
        "Annotations, comparisons and explicit exports are available in Tools and Export. "
        "Trajectory overlay requires recorded calibration. Detection requires stopped runtime capture."
    )
    notice.setWordWrap(True)
    tools.addWidget(notice)
    research.hide()
    advanced.toggled.connect(research.setVisible)
    advanced.toggled.connect(host._pitch_list.set_research_visible)
    layout.addWidget(research)
    inner = QtWidgets.QWidget()
    inner.setLayout(layout)
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    scroll.setMinimumWidth(280)
    scroll.setAccessibleName("Selected pitch feedback and research tools")
    scroll.setWidget(inner)
    return scroll


def run_frame_detection(host: "ReviewWindow") -> None:
    if not host._pitch_video_available:
        return
    try:
        left, right = host._service.run_detection_on_current_frame()
        frames = host._service.get_current_frames()
        for display, frame, detections in zip((host._left_display, host._right_display), frames, (left, right)):
            if frame is not None:
                display.set_frame(frame, detections)
    except Exception as exc:
        logging.getLogger(__name__).exception("Explicit review detection failed")
        host._feedback.labels["playback"].setText(str(exc))


def browse_session_video(host: "ReviewWindow") -> None:
    host._playback_ctrl.stop_playback()
    host._selected_pitch_id = None
    host._pitch_list.select_pitch(-1)
    host._trajectory_ctrl.clear()
    host._feedback.clear()
    host._feedback.labels["identity"].setText("Full session video · no pitch association")
    host._pitch_video_available = host._service.browse_session_video()
    host._controls.setEnabled(host._pitch_video_available)
    host._timeline.setEnabled(host._pitch_video_available)
    host._update_video_displays()
    host.selection_changed.emit(host.selection())

"""Characterization tests for the refactored ReviewWindow facade.

Covers construction, session load success/failure, pitch selection/playback,
export routing, diagnostics panel, and teardown — all with mocked service.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ui.review.review_window import ReviewWindow


@pytest.fixture
def mock_review_service():
    """Provide a fully mocked ReviewService."""
    with patch("ui.review.review_window.ReviewService") as MockSvc:
        svc = MockSvc.return_value
        svc.session = None
        svc.total_frames = 0
        svc.current_frame_index = 0
        svc.playback_speed = 1.0
        svc._pitch_scores = {}
        svc.video_reader = MagicMock(fps=30.0)
        svc.detector_config = None
        svc.get_current_frames.return_value = (None, None)
        svc.run_detection_on_current_frame.return_value = ([], [])
        yield svc


@pytest.fixture
def review_window(qtbot, mock_review_service):
    """Construct ReviewWindow under test."""
    window = ReviewWindow()
    qtbot.addWidget(window)
    return window


class TestConstruction:
    """Window shell and controller wiring."""

    def test_creates_at_default_size(self, review_window):
        assert review_window.width() >= 800
        assert review_window.height() >= 600

    def test_creates_at_target_sizes(self, qtbot, mock_review_service):
        window = ReviewWindow()
        qtbot.addWidget(window)
        window.resize(1024, 768)
        assert window.size().width() == 1024

    def test_has_splitter_with_accessible_name(self, review_window):
        from PySide6 import QtWidgets

        splitter = review_window.centralWidget().findChild(QtWidgets.QSplitter)
        assert splitter is not None
        assert splitter.accessibleName() == "Review layout splitter"

    def test_has_status_bar(self, review_window):
        assert review_window.statusBar() is not None

    def test_controllers_initialized(self, review_window):
        assert review_window._session_ctrl is not None
        assert review_window._playback_ctrl is not None
        assert review_window._trajectory_ctrl is not None
        assert review_window._export_ctrl is not None


class TestSessionLoading:
    """Session load success and failure paths."""

    def test_load_success_updates_title(self, review_window, mock_review_service):
        session = MagicMock()
        session.session_id = "test-session-001"
        session.pitches = []
        session.calibration = None
        mock_review_service.session = session
        mock_review_service.load_session.return_value = session
        mock_review_service.total_frames = 100

        review_window._session_ctrl.load_session(Path("fake/session"))

        assert "test-session-001" in review_window.windowTitle()

    def test_load_failure_shows_error(self, review_window, mock_review_service):
        mock_review_service.load_session.side_effect = RuntimeError("corrupt")

        with patch("ui.review._session_controller.show_message_dialog") as mock_dlg:
            review_window._session_ctrl.load_session(Path("bad/session"))
            mock_dlg.assert_called_once()
            assert "error" in mock_dlg.call_args[1].get("tone", "")

    def test_delete_manual_session_preserves_review_list(
        self, review_window, mock_review_service, tmp_path
    ):
        controller = review_window._session_ctrl
        listed_sessions = [tmp_path / "listed-a", tmp_path / "listed-b"]
        manual_session = tmp_path / "manual"
        controller._session_list = listed_sessions.copy()
        controller._current_session_index = 0
        mock_review_service.session = MagicMock(
            session_id="manual",
            session_dir=manual_session,
        )

        with (
            patch("ui.review._session_controller.ask_confirmation", return_value=True),
            patch("ui.review._session_controller.show_message_dialog"),
            patch("ui.review._session_controller.shutil.rmtree"),
            patch.object(controller, "load_session") as load_session,
        ):
            controller.delete_current_session()

        assert controller.session_list == listed_sessions
        load_session.assert_called_once_with(listed_sessions[0])


class TestPitchSelection:
    """Pitch selection and navigation."""

    def test_on_pitch_selected_seeks(self, review_window, mock_review_service):
        session = MagicMock()
        session.session_id = "s1"
        session.pitches = [MagicMock(pitch_id="p1", original_observations=[], t_start_ns=0)]
        session.calibration = None
        mock_review_service.session = session

        review_window._on_pitch_selected(0)
        mock_review_service.seek_to_pitch.assert_called_with(0)

    def test_prev_next_pitch_navigate(self, review_window, mock_review_service):
        session = MagicMock()
        session.pitches = [
            MagicMock(pitch_id="p1", t_start_ns=0, original_observations=[]),
            MagicMock(pitch_id="p2", t_start_ns=100, original_observations=[]),
        ]
        session.calibration = None
        mock_review_service.session = session
        mock_review_service.current_frame_index = 0
        mock_review_service.get_frame_for_timestamp.return_value = 0

        review_window._next_pitch()
        mock_review_service.seek_to_pitch.assert_called()


class TestPlayback:
    """Playback state management."""

    def test_toggle_playback_starts_and_stops(self, review_window, mock_review_service):
        session = MagicMock()
        session.session_id = "s1"
        mock_review_service.session = session

        review_window._playback_ctrl.toggle_playback()
        assert review_window._playback_ctrl.is_playing

        review_window._playback_ctrl.toggle_playback()
        assert not review_window._playback_ctrl.is_playing

    def test_stop_playback_on_close(self, review_window, mock_review_service):
        session = MagicMock()
        mock_review_service.session = session

        review_window._playback_ctrl.toggle_playback()
        review_window._playback_ctrl.teardown()
        assert not review_window._playback_ctrl.is_playing


class TestExportRouting:
    """Export controller delegation."""

    def test_export_config_no_session_shows_warning(self, review_window, mock_review_service):
        mock_review_service.session = None
        with patch("ui.review._export_controller.show_message_dialog") as mock_dlg:
            review_window._export_ctrl.export_config()
            mock_dlg.assert_called_once()

    def test_export_annotations_no_session_shows_warning(self, review_window, mock_review_service):
        mock_review_service.session = None
        with patch("ui.review._export_controller.show_message_dialog") as mock_dlg:
            review_window._export_ctrl.export_annotations()
            mock_dlg.assert_called_once()


class TestTrajectoryDiagnostics:
    """Trajectory controller and diagnostics panel."""

    def test_overlay_toggle(self, review_window):
        review_window._trajectory_ctrl.overlay_enabled = True
        assert review_window._trajectory_ctrl.overlay_enabled

    def test_load_trajectory_no_session(self, review_window, mock_review_service):
        mock_review_service.session = None
        review_window._trajectory_ctrl.load_trajectory_for_pitch(0)
        assert review_window._trajectory_ctrl.current_observations == []

    def test_clear_resets_state(self, review_window):
        review_window._trajectory_ctrl._current_observations = [1, 2, 3]
        review_window._trajectory_ctrl.clear()
        assert review_window._trajectory_ctrl.current_observations == []
        assert not review_window._trajectory_ctrl.overlay_enabled


class TestTeardown:
    """Window close and cleanup."""

    def test_close_event_stops_timer(self, review_window, mock_review_service):
        session = MagicMock()
        mock_review_service.session = session
        review_window._playback_ctrl.toggle_playback()

        review_window.close()
        assert not review_window._playback_ctrl._playback_timer.isActive()
        mock_review_service.close.assert_called()

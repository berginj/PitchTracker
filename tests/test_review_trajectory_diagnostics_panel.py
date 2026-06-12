from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from PySide6 import QtWidgets

from app.review import PitchScore

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

from ui.review.widgets.trajectory_diagnostics_panel import TrajectoryDiagnosticsPanel


HAS_PYTEST_QT = importlib.util.find_spec("pytestqt") is not None

requires_pytest_qt = pytest.mark.skipif(
    not HAS_PYTEST_QT,
    reason="pytest-qt not installed",
)


@requires_pytest_qt
def test_trajectory_diagnostics_panel_shows_nested_manifest_data(qtbot: QtBot) -> None:
    panel = TrajectoryDiagnosticsPanel()
    qtbot.addWidget(panel)
    pitch = SimpleNamespace(
        manifest={
            "trajectory": {
                "mode": "stereo_3d",
                "ray_rmse_px": 1.234,
                "estimated_camera_time_offset_ms": -3.456,
                "comparison": {
                    "ray_reprojection": {
                        "fallback_used": "stereo_3d",
                        "diagnostics": {
                            "failure_codes": ["CAMERA_MODEL_MISSING"],
                        },
                    },
                    "stereo_3d": {
                        "diagnostics": {
                            "failure_codes": [],
                        },
                    },
                },
            },
        },
    )

    panel.load_pitch(pitch)

    assert panel._mode_label.text() == "Mode: stereo_3d"
    assert panel._fallback_label.text() == "Fallback: Yes, used stereo_3d"
    assert panel._ray_rmse_label.text() == "Ray RMSE: 1.23 px"
    assert panel._time_offset_label.text() == "Camera offset: -3.46 ms"
    assert "ray_reprojection: CAMERA_MODEL_MISSING" in panel._failure_codes_label.text()
    assert "stereo_3d: OK" in panel._failure_codes_label.text()


@requires_pytest_qt
def test_trajectory_diagnostics_panel_supports_top_level_comparison(qtbot: QtBot) -> None:
    panel = TrajectoryDiagnosticsPanel()
    qtbot.addWidget(panel)
    pitch = SimpleNamespace(
        manifest={
            "trajectory_mode": "ray_graph",
            "ray_rmse_px": 0.5,
            "estimated_camera_time_offset_ms": 7.0,
            "trajectory_comparison": {
                "ray_graph": {
                    "diagnostics": {
                        "failure_codes": ["INSUFFICIENT_RAYS", "OPT_DID_NOT_CONVERGE"],
                    },
                },
            },
        },
    )

    panel.load_pitch(pitch)

    assert panel._mode_label.text() == "Mode: ray_graph"
    assert panel._fallback_label.text() == "Fallback: No"
    assert panel._ray_rmse_label.text() == "Ray RMSE: 0.50 px"
    assert panel._time_offset_label.text() == "Camera offset: 7.00 ms"
    assert "ray_graph: INSUFFICIENT_RAYS, OPT_DID_NOT_CONVERGE" in (
        panel._failure_codes_label.text()
    )


@requires_pytest_qt
def test_trajectory_diagnostics_panel_handles_missing_manifest_data(qtbot: QtBot) -> None:
    panel = TrajectoryDiagnosticsPanel()
    qtbot.addWidget(panel)

    panel.load_pitch(SimpleNamespace(manifest={}))

    assert panel._mode_label.text() == "Mode: -"
    assert panel._fallback_label.text() == "Fallback: -"
    assert panel._ray_rmse_label.text() == "Ray RMSE: -"
    assert panel._time_offset_label.text() == "Camera offset: -"
    assert panel._failure_codes_label.text() == "Mode failures: -"


@requires_pytest_qt
def test_trajectory_diagnostics_panel_ignores_non_dict_manifest(qtbot: QtBot) -> None:
    panel = TrajectoryDiagnosticsPanel()
    qtbot.addWidget(panel)

    panel.load_pitch(SimpleNamespace(manifest=[]))

    assert panel._mode_label.text() == "Mode: -"
    assert panel._fallback_label.text() == "Fallback: -"
    assert panel._failure_codes_label.text() == "Mode failures: -"


@requires_pytest_qt
def test_trajectory_diagnostics_panel_clears_when_no_pitch_selected(qtbot: QtBot) -> None:
    panel = TrajectoryDiagnosticsPanel()
    qtbot.addWidget(panel)

    panel.clear()

    assert panel._mode_label.text() == "Mode: -"
    assert panel._fallback_label.text() == "Fallback: -"
    assert panel._failure_codes_label.text() == "Mode failures: -"


@requires_pytest_qt
def test_pitch_list_emits_highlight_signal_on_row_selection(qtbot: QtBot) -> None:
    from ui.review.widgets import PitchListWidget

    widget = PitchListWidget()
    qtbot.addWidget(widget)
    widget.load_pitches(
        [
            SimpleNamespace(
                pitch_id="pitch_001",
                manifest={"pitch_id": "pitch_001", "measured_speed_mph": 80.0},
            ),
            SimpleNamespace(
                pitch_id="pitch_002",
                manifest={"pitch_id": "pitch_002", "measured_speed_mph": 81.0},
            ),
        ],
        {"pitch_001": PitchScore.UNSCORED, "pitch_002": PitchScore.UNSCORED},
    )

    rows = widget.findChild(QtWidgets.QListWidget)
    assert rows is not None

    with qtbot.waitSignal(widget.pitch_highlighted, timeout=1000) as blocker:
        rows.setCurrentRow(1)

    assert blocker.args == [1]


class _FakeVideoReader:
    fps = 30.0


class _FakeReviewService:
    def __init__(self, session):
        self.session = None
        self._loaded_session = session
        self._pitch_scores = {}
        self.total_frames = 120
        self.current_frame_index = 0
        self.video_reader = _FakeVideoReader()
        self.detector_config = None

    def load_session(self, _session_dir: Path):
        self.session = self._loaded_session
        self._pitch_scores = {
            pitch.pitch_id: PitchScore.UNSCORED for pitch in self.session.pitches
        }
        return self.session

    def close(self) -> None:
        self.session = None

    def get_current_frames(self):
        return None, None

    def seek_to_pitch(self, pitch_index: int) -> bool:
        self.current_frame_index = pitch_index * 100
        return True

    def get_frame_for_timestamp(self, timestamp_ns: int) -> int:
        return timestamp_ns // 1_000_000_000


def _review_pitch(pitch_id: str, mode: str, t_start_ns: int):
    return SimpleNamespace(
        pitch_id=pitch_id,
        t_start_ns=t_start_ns,
        original_observations=[],
        manifest={
            "pitch_id": pitch_id,
            "measured_speed_mph": 82.0,
            "trajectory": {
                "mode": mode,
                "ray_rmse_px": 2.5,
                "estimated_camera_time_offset_ms": 4.0,
                "comparison": {
                    "ray_reprojection": {
                        "diagnostics": {"failure_codes": []},
                    },
                },
            },
        },
    )


def _review_session():
    return SimpleNamespace(
        session_id="session_001",
        pitches=[
            _review_pitch("pitch_001", "stereo_3d", 0),
            _review_pitch("pitch_002", "ray_graph", 1_000_000_000),
        ],
        calibration=None,
    )


@requires_pytest_qt
def test_review_window_loads_first_pitch_diagnostics(qtbot: QtBot, monkeypatch) -> None:
    from ui.review import review_window

    fake_service = _FakeReviewService(_review_session())
    monkeypatch.setattr(review_window, "ReviewService", lambda: fake_service)

    window = review_window.ReviewWindow()
    qtbot.addWidget(window)

    window._load_session(Path("unused"))

    panel = window._trajectory_diagnostics_panel
    assert panel._mode_label.text() == "Mode: stereo_3d"
    assert panel._ray_rmse_label.text() == "Ray RMSE: 2.50 px"


@requires_pytest_qt
def test_review_window_highlighted_pitch_updates_diagnostics(qtbot: QtBot, monkeypatch) -> None:
    from ui.review import review_window

    fake_service = _FakeReviewService(_review_session())
    monkeypatch.setattr(review_window, "ReviewService", lambda: fake_service)

    window = review_window.ReviewWindow()
    qtbot.addWidget(window)
    window._load_session(Path("unused"))

    rows = window._pitch_list.findChild(QtWidgets.QListWidget)
    assert rows is not None
    rows.setCurrentRow(1)

    assert window._trajectory_diagnostics_panel._mode_label.text() == "Mode: ray_graph"


@requires_pytest_qt
def test_review_window_close_session_clears_diagnostics(qtbot: QtBot, monkeypatch) -> None:
    from ui.review import review_window

    fake_service = _FakeReviewService(_review_session())
    monkeypatch.setattr(review_window, "ReviewService", lambda: fake_service)

    window = review_window.ReviewWindow()
    qtbot.addWidget(window)
    window._load_session(Path("unused"))

    window._close_session()

    panel = window._trajectory_diagnostics_panel
    assert panel._mode_label.text() == "Mode: -"
    assert panel._fallback_label.text() == "Fallback: -"

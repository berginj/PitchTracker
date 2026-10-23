"""UX-08: whole-workspace journeys, service boundaries and recovery reachability."""

import pytest
from PySide6 import QtCore, QtWidgets

from app.services.orchestrator.runtime_status import FinalizedSession, RuntimeFailure
from tests.test_workspace_navigation import workspace  # noqa: F401
from ui.themes import get_style_manager
from ui.workspace.contracts import SessionPreparation


@pytest.mark.parametrize("size", [(1366, 768), (1024, 768), (800, 600)])
@pytest.mark.parametrize("phase", ["recording", "paused", "finalizing", "completed"])
def test_recovery_actions_remain_reachable_with_long_failure(request, qtbot, size, phase):
    window, pipeline = request.getfixturevalue("workspace")
    get_style_manager().apply_to_app(QtWidgets.QApplication.instance())
    window._on_preparation_changed(SessionPreparation("Synthetic session", "Example Pitcher", phase != "completed"))
    pipeline.set_status(
        capture_phase="live", recording_phase=phase,
        session_id="synthetic" if phase != "completed" else None,
        finalized_session=FinalizedSession("synthetic", window._config_path.parent / "completed"),
        failure=RuntimeFailure("stop_recording", "Synthetic writer failure with a long diagnostic. " * 40),
    )
    assert window.navigate("sessions")
    window.resize(*size)
    qtbot.wait(10)
    assert (window.width(), window.height()) == size
    assert window._primary.isVisible() and window._return_live.isVisible()
    assert window._primary.accessibleName() == window._primary.text()
    if phase == "completed":
        assert window._new_session.isVisible() and window._stop_preview.isVisible()
    if phase in {"recording", "paused"}:
        # A failed End command promotes its retry to the primary action.
        assert window._primary_action == "end"
        assert window._primary.text() == "Retry End Session"
        assert window._end.isHidden()
    for button in (window._primary, window._end, window._stop_preview, window._return_live, window._new_session):
        if button.isVisibleTo(window):
            rect = QtCore.QRect(button.mapTo(window, QtCore.QPoint()), button.size())
            assert window.rect().contains(rect), button.text()

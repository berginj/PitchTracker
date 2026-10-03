"""Coaching and Qt shutdown retain worker ownership until a retry completes."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6 import QtGui

from app.events.event_types import PitchEndEvent, PitchStartEvent
from app.qt_pipeline_service import QtPipelineService
from exceptions import CameraConnectionError
from ui.coaching.session_controller import SessionController


def _controller():
    host = SimpleNamespace(
        _preview_timer=Mock(),
        _metrics_timer=Mock(),
        _session_active=True,
        _service=Mock(),
        _status_label=Mock(),
        close=Mock(),
    )
    controller = SessionController.__new__(SessionController)
    controller._host = host
    controller._close_pending = False
    return controller, host


def test_close_retains_owner_and_retries_without_repeating_session_dialog(monkeypatch):
    controller, host = _controller()
    host._service.shutdown.side_effect = [CameraConnectionError("read still pending"), None]
    dialog = Mock(return_value="close")
    retry = Mock()
    monkeypatch.setattr("ui.coaching.session_controller.show_choice_dialog", dialog)
    monkeypatch.setattr("ui.coaching.session_controller.QtCore.QTimer.singleShot", retry)

    event = QtGui.QCloseEvent()
    controller.handle_close_event(event)

    assert not event.isAccepted()
    assert controller._close_pending
    assert controller._host._service is host._service
    retry.assert_called_once_with(250, host.close)
    host._status_label.setText.assert_called_once()
    host._preview_timer.start.assert_not_called()

    event = QtGui.QCloseEvent()
    controller.handle_close_event(event)

    assert event.isAccepted()
    assert not controller._close_pending
    assert host._service.shutdown.call_count == 2
    dialog.assert_called_once()


def test_cancel_close_resumes_timers_without_stopping_service(monkeypatch):
    controller, host = _controller()
    monkeypatch.setattr(
        "ui.coaching.session_controller.show_choice_dialog", Mock(return_value="cancel")
    )
    event = QtGui.QCloseEvent()
    controller.handle_close_event(event)

    assert not event.isAccepted()
    assert not controller._close_pending
    host._service.shutdown.assert_not_called()
    host._preview_timer.start.assert_called_once_with(33)
    host._metrics_timer.start.assert_called_once_with(100)


def test_recording_stop_failure_still_attempts_owned_shutdown(monkeypatch):
    controller, host = _controller()
    host._service.stop_recording.side_effect = OSError("writer still pending")
    monkeypatch.setattr(
        "ui.coaching.session_controller.show_choice_dialog", Mock(return_value="end")
    )
    event = QtGui.QCloseEvent()
    controller.handle_close_event(event)

    assert event.isAccepted()
    host._service.stop_recording.assert_called_once()
    host._service.shutdown.assert_called_once()


def test_qt_wrapper_retains_event_subscriptions_until_terminal_shutdown():
    service = Mock()
    service.shutdown.side_effect = [CameraConnectionError("reader still pending"), None]
    wrapper = SimpleNamespace(
        _service=service, _on_pitch_start_event=Mock(), _on_pitch_end_event=Mock()
    )
    with pytest.raises(CameraConnectionError, match="pending"):
        QtPipelineService.shutdown(wrapper)
    service.unsubscribe_event.assert_not_called()

    QtPipelineService.shutdown(wrapper)

    assert service.unsubscribe_event.call_count == 2
    service.unsubscribe_event.assert_any_call(PitchStartEvent, wrapper._on_pitch_start_event)
    service.unsubscribe_event.assert_any_call(PitchEndEvent, wrapper._on_pitch_end_event)

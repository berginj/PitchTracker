"""Persistent-worker frame flow, explicit stop and hard native-stall boundaries."""

from dataclasses import replace
import sys
import time

import pytest

from app.services.capture.focus_preview import FocusPreviewService
from contracts.setup_capture import SetupCaptureFailureCode, SetupCapturePurpose, SetupCaptureState
from tests.test_guided_setup_workflow import _new_workflow


def request_for(tmp_path):
    workflow = _new_workflow(tmp_path)
    workflow.assign("sim-left", "sim-right")
    return workflow, workflow.build_capture_request(SetupCapturePurpose.FOCUS)


def test_live_frames_share_one_worker_and_stop_cleanly(tmp_path):
    workflow, request = request_for(tmp_path)
    service = FocusPreviewService()
    try:
        service.start(request)
        deadline = time.monotonic() + 20
        while set(service.latest()) != {"left", "right"} and not service.done and time.monotonic() < deadline:
            time.sleep(0.02)
        frames = service.latest()
        assert set(frames) == {"left", "right"}, service.terminal
        first = frames["left"].frame_index
        pid = service._process.pid
        while service.latest()["left"].frame_index <= first and time.monotonic() < deadline:
            time.sleep(0.02)
        assert service.latest()["left"].frame_index > first
        assert service._process.pid == pid
        assert set(service.latest()) == {"left", "right"}
    finally:
        service.stop()
        assert service._done.wait(6)
        workflow.release_capture()
    assert service._process.poll() is not None
    assert service.terminal.state == SetupCaptureState.CANCELLED


def test_startup_stall_is_killed_and_reported(tmp_path, monkeypatch):
    workflow, request = request_for(tmp_path)
    request = replace(request, overall_deadline_ms=100)
    monkeypatch.setattr("app.services.capture.focus_preview.worker_command", lambda _task: [
        sys.executable, "-u", "-c", "import sys,time;sys.stdin.readline();time.sleep(60)",
    ])
    service = FocusPreviewService()
    try:
        service.start(request)
        assert service._done.wait(6)
        assert service.terminal.failure_code == SetupCaptureFailureCode.DEADLINE_EXCEEDED
        assert service.terminal.force_killed
        assert service._process.poll() is not None
    finally:
        service.stop()
        workflow.release_capture()


def test_wrong_camera_or_schema_cannot_replace_the_display_frame(tmp_path):
    workflow, request = request_for(tmp_path)
    service = FocusPreviewService()
    try:
        with pytest.raises(ValueError, match="schema"):
            service._accept({"schema_version": "unknown"}, request)
        with pytest.raises(ValueError, match="different camera"):
            service._accept({"schema_version": "focus_preview.v1", "kind": "frame",
                             "side": "left", "camera_id": "wrong"}, request)
        assert service.latest() == {}
    finally:
        workflow.release_capture()

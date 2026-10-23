from __future__ import annotations

from typing import Any, cast
from unittest.mock import patch

import cv2
import pytest

from capture.uvc_backend import UvcCamera
from capture.uvc_probe import ProbeEvidence
from contracts.capability_observation import (
    CONTROL_EXPOSURE,
    CONTROL_FOCUS,
    CONTROL_FPS,
    CONTROL_RESOLUTION,
    ControlQueryStatus,
    ControlQueryResult,
)


class _FakeCapture:
    def __init__(self) -> None:
        self.released = False
        self.exposure_flags = 1
        self.values = {
            cv2.CAP_PROP_AUTO_EXPOSURE: -1.0,
            cv2.CAP_PROP_AUTO_WB: 0.0,
            cv2.CAP_PROP_AUTOFOCUS: 2.0,
            cv2.CAP_PROP_WHITE_BALANCE_BLUE_U: 0.0,
        }

    def set(self, prop, value):
        if prop == cv2.CAP_PROP_AUTO_EXPOSURE:
            self.exposure_flags = 1 if round(value) == 1 else 2
            return True  # DirectShow 4.10 has no getter for this property.
        if prop == cv2.CAP_PROP_AUTOFOCUS:
            self.values[prop] = 1 if round(value) == 1 else 2
            return True
        self.values[prop] = value
        return True

    def get(self, prop):
        return self.values.get(prop, 0.0)

    def release(self) -> None:
        self.released = True


def _attach_capture(camera: UvcCamera, capture: _FakeCapture) -> None:
    camera._capture = cast(cv2.VideoCapture, capture)


def _read_controls(camera: UvcCamera) -> dict[str, Any]:
    capture = cast(_FakeCapture, camera._capture)
    evidence = ProbeEvidence(provider="native_directshow", results={
        CONTROL_EXPOSURE: ControlQueryResult(CONTROL_EXPOSURE, ControlQueryStatus.SUPPORTED,
                                             observed_value={"current_flags": capture.exposure_flags})})
    with patch("capture.uvc_backend.refresh_native_controls", return_value=evidence):
        controls = camera.get_controls()
    assert controls is not None
    return controls


def test_directshow_controls_are_converted_and_verified_from_readback() -> None:
    camera = UvcCamera()
    capture = _FakeCapture()
    _attach_capture(camera, capture)
    camera.set_controls(2000, 2.0, None, None)

    controls = _read_controls(camera)

    assert controls["exposure_backend_raw"] == -9
    assert controls["exposure_readback_us"] == pytest.approx(1953.125)
    assert controls["autofocus_disabled"] is True
    assert capture.values[cv2.CAP_PROP_AUTOFOCUS] == 2
    assert controls["actual_exposure_us"] == pytest.approx(1953.125)
    assert controls["actual_gain"] == pytest.approx(2.0)
    assert controls["readback_verified"] is True


def test_color_controls_fail_when_auto_white_balance_sample_is_zero() -> None:
    camera = UvcCamera()
    _attach_capture(camera, _FakeCapture())
    camera._pixfmt = "YUYV"

    camera.set_controls(2000, 2.0, None, None)
    controls = _read_controls(camera)

    assert controls["actual_wb"] is None
    assert controls["resolved_wb"] is None
    assert controls["wb_source"] == "auto_sample_unavailable"
    assert controls["color_white_balance_verified"] is False
    assert controls["readback_verified"] is False


def test_color_controls_auto_sample_then_lock_white_balance() -> None:
    camera = UvcCamera()
    capture = _FakeCapture()
    capture.values[cv2.CAP_PROP_AUTO_WB] = 1.0
    capture.values[cv2.CAP_PROP_WHITE_BALANCE_BLUE_U] = 4750.0
    _attach_capture(camera, capture)
    camera._pixfmt = "YUYV"

    camera.set_controls(2000, 2.0, None, None)
    controls = _read_controls(camera)

    assert capture.values[cv2.CAP_PROP_AUTO_WB] == 0
    assert capture.values[cv2.CAP_PROP_WHITE_BALANCE_BLUE_U] == pytest.approx(4750.0)
    assert controls["resolved_wb"] == pytest.approx(4750.0)
    assert controls["actual_wb"] == pytest.approx(4750.0)
    assert controls["wb_source"] == "auto_sampled_then_locked"
    assert controls["auto_wb_sampled_while_enabled"] is True
    assert controls["readback_verified"] is True


def test_color_controls_verify_explicit_white_balance() -> None:
    camera = UvcCamera()
    _attach_capture(camera, _FakeCapture())
    camera._pixfmt = "YUYV"

    camera.set_controls(2000, 2.0, None, 4600)
    controls = _read_controls(camera)

    assert controls["actual_wb"] == pytest.approx(4600.0)
    assert controls["color_white_balance_verified"] is True
    assert controls["readback_verified"] is True


def test_uvc_jitter_is_interval_deviation_not_frame_period() -> None:
    camera = UvcCamera()
    camera._deltas_ns.extend([16_666_667] * 20)

    stats = camera.get_stats()

    assert stats.jitter_p95_ms == pytest.approx(0.0)


def test_uvc_jitter_reports_cadence_outlier() -> None:
    camera = UvcCamera()
    camera._deltas_ns.extend([16_666_667] * 18 + [25_000_000] * 2)

    stats = camera.get_stats()

    assert stats.jitter_p95_ms > 0.0


def test_capability_observation_keeps_requested_and_negotiated_modes() -> None:
    camera = UvcCamera()
    capture = _FakeCapture()
    capture.values.update(
        {
            cv2.CAP_PROP_FRAME_WIDTH: 1280,
            cv2.CAP_PROP_FRAME_HEIGHT: 720,
            cv2.CAP_PROP_FPS: 60,
            cv2.CAP_PROP_FOURCC: int.from_bytes(b"MJPG", "little"),
        }
    )
    _attach_capture(camera, capture)
    camera._serial = "private-camera-id"
    camera._width = 1920
    camera._height = 1080
    camera._fps = 120
    camera._pixfmt = "MJPG"
    camera.set_controls(2000, 2.0, None, 4600)

    observation = camera.get_capability_observation()

    assert observation is not None
    assert observation.requested_mode["width"] == 1920
    assert observation.requested_mode["fps"] == 120
    assert observation.negotiated_mode["width"] == 1280
    assert observation.negotiated_mode["fps"] == 60
    assert observation.results[CONTROL_RESOLUTION].requested_value == "1920x1080"
    assert observation.results[CONTROL_FPS].observed_value == 60
    assert observation.results[CONTROL_FPS].status == ControlQueryStatus.SUPPORTED
    assert "OpenCV DirectShow properties" in observation.provenance_note
    assert "native DirectShow probe" in observation.provenance_note


def test_close_releases_capture_and_remains_idempotent(monkeypatch) -> None:
    camera = UvcCamera()
    capture = _FakeCapture()
    _attach_capture(camera, capture)
    monkeypatch.setattr("capture.uvc_backend.time.sleep", lambda _seconds: None)

    camera.close()
    camera.close()

    assert capture.released is True
    assert camera._capture is None


def test_fps_rebuild_does_not_leave_the_requested_mjpeg_stream_in_yuy2():
    class ResetOnFps(_FakeCapture):
        def set(self, prop, value):
            result = super().set(prop, value)
            if prop == cv2.CAP_PROP_FPS:
                self.values[cv2.CAP_PROP_FOURCC] = int.from_bytes(b"YUY2", "little")
            return result

    capture = ResetOnFps()
    camera = UvcCamera()
    _attach_capture(camera, capture)
    camera.set_mode(1280, 720, 60, "MJPG")
    assert camera.get_mode() == {"width": 1280, "height": 720, "fps": 60.0, "pixfmt": "MJPG"}


def test_missing_native_exposure_flags_keep_setup_unverified():
    camera = UvcCamera()
    _attach_capture(camera, _FakeCapture())
    camera.set_controls(2000, 2, None, None)
    with patch("capture.uvc_backend.refresh_native_controls", return_value=None):
        controls = camera.get_controls()
    assert controls is not None
    assert controls["auto_exposure_disabled"] is False
    assert controls["readback_verified"] is False


@pytest.mark.parametrize("flags", [0, 1, 3, -1])
def test_unknown_or_automatic_focus_flags_are_not_manual_lock(flags):
    camera = UvcCamera()
    capture = _FakeCapture()
    _attach_capture(camera, capture)
    camera.set_controls(2000, 2, None, None)
    capture.values[cv2.CAP_PROP_AUTOFOCUS] = flags
    assert _read_controls(camera)["autofocus_disabled"] is False


def test_current_native_flags_replace_prewrite_automatic_state():
    camera = UvcCamera()
    capture = _FakeCapture()
    _attach_capture(camera, capture)
    camera.set_controls(2000, 2, None, None)
    capture.exposure_flags = 1
    assert _read_controls(camera)["auto_exposure_disabled"] is False
    capture.exposure_flags = 2
    assert _read_controls(camera)["auto_exposure_disabled"] is True


@pytest.mark.parametrize("status", list(ControlQueryStatus))
def test_fixed_lens_requires_native_absent_focus_evidence(status):
    camera = UvcCamera()
    capture = _FakeCapture()
    _attach_capture(camera, capture)
    camera.set_controls(488, 168, None, 4500)
    capture.values[cv2.CAP_PROP_AUTOFOCUS] = -1
    evidence = ProbeEvidence(provider="native_directshow", results={
        CONTROL_EXPOSURE: ControlQueryResult(CONTROL_EXPOSURE, ControlQueryStatus.SUPPORTED,
                                             observed_value={"current_flags": 2}),
        CONTROL_FOCUS: ControlQueryResult(CONTROL_FOCUS, status),
    })
    with patch("capture.uvc_backend.refresh_native_controls", return_value=evidence):
        controls = camera.get_controls()
    assert controls is not None
    absent = status == ControlQueryStatus.UNSUPPORTED
    assert controls["autofocus_absent"] is absent
    assert controls["autofocus_disabled"] is absent
    assert controls["readback_verified"] is absent
    assert controls["gain_readback_verified"]


def test_native_absent_focus_cannot_override_enabled_autofocus():
    from capture.uvc_control_evidence import read_controls
    capture = _FakeCapture()
    capture.values[cv2.CAP_PROP_AUTOFOCUS] = 1
    evidence = {CONTROL_FOCUS: ControlQueryResult(CONTROL_FOCUS, ControlQueryStatus.UNSUPPORTED)}
    controls = read_controls(cast(cv2.VideoCapture, capture), "YUYV", {}, evidence)
    assert controls["autofocus_disabled"] is False
    assert controls["autofocus_absent"] is False

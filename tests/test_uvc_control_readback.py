from __future__ import annotations

import cv2
import pytest

from capture.uvc_backend import UvcCamera


class _FakeCapture:
    def __init__(self) -> None:
        self.values = {
            cv2.CAP_PROP_AUTO_EXPOSURE: 0.25,
            cv2.CAP_PROP_AUTO_WB: 0.0,
            cv2.CAP_PROP_AUTOFOCUS: 0.0,
            cv2.CAP_PROP_WB_TEMPERATURE: 0.0,
        }

    def set(self, prop, value):
        self.values[prop] = value
        return True

    def get(self, prop):
        return self.values.get(prop, 0.0)


def test_directshow_controls_are_converted_and_verified_from_readback() -> None:
    camera = UvcCamera()
    camera._capture = _FakeCapture()
    camera.set_controls(2000, 2.0, None, None)

    controls = camera.get_controls()

    assert controls["exposure_backend_raw"] == pytest.approx(-8.965784, rel=1e-5)
    assert controls["exposure_readback_us"] == pytest.approx(2000.0)
    assert controls["autofocus_disabled"] is True
    assert camera._capture.values[cv2.CAP_PROP_AUTOFOCUS] == 0
    assert controls["actual_exposure_us"] == pytest.approx(2000.0)
    assert controls["actual_gain"] == pytest.approx(2.0)
    assert controls["readback_verified"] is True


def test_color_controls_fail_when_auto_white_balance_sample_is_zero() -> None:
    camera = UvcCamera()
    camera._capture = _FakeCapture()
    camera._pixfmt = "YUYV"

    camera.set_controls(2000, 2.0, None, None)
    controls = camera.get_controls()

    assert controls["actual_wb"] is None
    assert controls["resolved_wb"] is None
    assert controls["wb_source"] == "auto_sample_unavailable"
    assert controls["color_white_balance_verified"] is False
    assert controls["readback_verified"] is False


def test_color_controls_auto_sample_then_lock_white_balance() -> None:
    camera = UvcCamera()
    capture = _FakeCapture()
    capture.values[cv2.CAP_PROP_AUTO_WB] = 1.0
    capture.values[cv2.CAP_PROP_WB_TEMPERATURE] = 4750.0
    camera._capture = capture
    camera._pixfmt = "YUYV"

    camera.set_controls(2000, 2.0, None, None)
    controls = camera.get_controls()

    assert capture.values[cv2.CAP_PROP_AUTO_WB] == 0
    assert capture.values[cv2.CAP_PROP_WB_TEMPERATURE] == pytest.approx(4750.0)
    assert controls["resolved_wb"] == pytest.approx(4750.0)
    assert controls["actual_wb"] == pytest.approx(4750.0)
    assert controls["wb_source"] == "auto_sampled_then_locked"
    assert controls["auto_wb_sampled_while_enabled"] is True
    assert controls["readback_verified"] is True


def test_color_controls_verify_explicit_white_balance() -> None:
    camera = UvcCamera()
    camera._capture = _FakeCapture()
    camera._pixfmt = "YUYV"

    camera.set_controls(2000, 2.0, None, 4600)
    controls = camera.get_controls()

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

"""Tests for the stereo setup adapter providers (steps 1 & 2).

All tests run without hardware: camera discovery uses a fake device lister and a
fake catalog; paired preview uses the SimulatedCamera backend.
"""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from contracts.catalog import SIDE_LEFT, SIDE_RIGHT, SIDE_UNASSIGNED  # noqa: E402
from exceptions import CameraError  # noqa: E402
from ui.setup.camera_select_view import grade_selection  # noqa: E402
from ui.setup.paired_preview_view import grade_preview  # noqa: E402
from ui.setup.providers import (  # noqa: E402
    build_live_stereo_step_widgets,
    capture_paired_preview,
    discover_camera_selection,
    make_camera_preview_provider,
    simulated_paired_preview,
)


class _FakeKnownDevice:
    def __init__(self, hardware_id, side):
        self.hardware_id = hardware_id
        self.side = side


class _FakeCatalog:
    def __init__(self, sides=None, recognized_names=()):
        self._sides = sides or {}
        self._recognized = set(recognized_names)

    def known_devices(self):
        return [_FakeKnownDevice(hid, side) for hid, side in self._sides.items()]

    def match_model(self, friendly_name):
        return object() if friendly_name in self._recognized else None


def _devices():
    return [
        {"serial": "LEFTSER", "friendly_name": "Arducam Left", "instance_id": "USB\\1"},
        {"serial": "RIGHTSER", "friendly_name": "Arducam Right", "instance_id": "USB\\2"},
    ]


def test_discover_without_catalog_marks_unassigned():
    snap = discover_camera_selection(list_devices=_devices, catalog=None)
    assert len(snap.cameras) == 2
    assert all(cam.side == SIDE_UNASSIGNED for cam in snap.cameras)
    assert all(not cam.recognized for cam in snap.cameras)
    # No assignment yet => selection fails.
    assert grade_selection(snap)[0] is False


def test_discover_applies_catalog_sides_and_recognition():
    catalog = _FakeCatalog(
        sides={"LEFTSER": SIDE_LEFT, "RIGHTSER": SIDE_RIGHT},
        recognized_names={"Arducam Left", "Arducam Right"},
    )
    snap = discover_camera_selection(list_devices=_devices, catalog=catalog)
    by_id = {cam.hardware_id: cam for cam in snap.cameras}
    assert by_id["LEFTSER"].side == SIDE_LEFT
    assert by_id["RIGHTSER"].side == SIDE_RIGHT
    assert by_id["LEFTSER"].recognized is True
    # Distinct L/R assigned => selection passes.
    assert grade_selection(snap)[0] is True


def test_discover_empty_device_list():
    snap = discover_camera_selection(list_devices=lambda: [], catalog=None)
    assert snap.cameras == ()
    assert grade_selection(snap) == (False, "No cameras discovered.")


def test_discover_falls_back_to_instance_id_when_no_serial():
    devices = [{"friendly_name": "Cam", "instance_id": "USB\\ABC"}]
    snap = discover_camera_selection(list_devices=lambda: devices, catalog=None)
    assert snap.cameras[0].hardware_id == "USB\\ABC"


def test_simulated_paired_preview_passes():
    snap = simulated_paired_preview(frames=3)
    assert snap.left_ok is True
    assert snap.right_ok is True
    assert snap.frames_observed == 3
    assert grade_preview(snap)[0] is True


def test_make_camera_preview_provider_with_simulated_cameras_passes():
    from capture.simulated_camera import SimulatedCamera

    provider = make_camera_preview_provider(
        "sim-left",
        "sim-right",
        camera_factory=SimulatedCamera,
        frames=3,
        tolerance_ms=50.0,
    )

    snap = provider()

    assert snap.left_ok is True
    assert snap.right_ok is True
    assert grade_preview(snap)[0] is True


class _OpenFailCamera:
    def open(self, serial):
        raise CameraError("camera unavailable", camera_id=serial)

    def set_mode(self, *args, **kwargs):
        return None

    def read_frame(self, timeout_ms):
        raise CameraError("no frames")

    def close(self):
        return None


def test_make_camera_preview_provider_reports_open_failure():
    provider = make_camera_preview_provider(
        "dead-left",
        "dead-right",
        camera_factory=_OpenFailCamera,
        frames=1,
    )

    snap = provider()

    assert snap.left_ok is False
    assert snap.right_ok is False
    assert snap.frames_observed == 0
    assert grade_preview(snap) == (False, "No frames received from either camera.")


class _DeadCamera:
    def set_mode(self, *args, **kwargs):
        return None

    def read_frame(self, timeout_ms):
        raise CameraError("no frames")

    def close(self):
        return None


def test_capture_paired_preview_reports_dead_right_side():
    from capture.simulated_camera import SimulatedCamera

    left = SimulatedCamera()
    left.open("sim-left")
    right = _DeadCamera()
    snap = capture_paired_preview(left, right, frames=2)
    left.close()
    assert snap.left_ok is True
    assert snap.right_ok is False
    assert snap.frames_observed == 2
    assert snap.paired_within_tolerance is False
    assert grade_preview(snap) == (False, "Right camera not delivering frames.")


class _SkewedCamera:
    """Fake camera that emits frames with a fixed monotonic timestamp.

    Using injected timestamps keeps the offset deterministic, independent of
    the host clock resolution (Windows monotonic ticks can be coarse enough
    that two real reads land on the same tick, producing a 0ms offset).
    """

    def __init__(self, t_capture_monotonic_ns):
        self._t = t_capture_monotonic_ns
        self._index = 0

    def set_mode(self, *args, **kwargs):
        return None

    def read_frame(self, timeout_ms):
        from contracts.types import Frame

        idx = self._index
        self._index += 1
        return Frame(
            camera_id="fake",
            frame_index=idx,
            t_capture_monotonic_ns=self._t,
            image=None,
            width=64,
            height=48,
            pixfmt="GRAY8",
        )

    def close(self):
        return None


def test_capture_paired_preview_out_of_tolerance():
    # 10ms skew between the two sides, well above the 1ms tolerance.
    left = _SkewedCamera(0)
    right = _SkewedCamera(10_000_000)
    snap = capture_paired_preview(left, right, frames=2, tolerance_ms=1.0)
    assert snap.left_ok is True
    assert snap.right_ok is True
    assert snap.pair_offset_ms == pytest.approx(10.0)
    assert snap.paired_within_tolerance is False
    assert grade_preview(snap)[0] is False


@pytest.fixture(scope="module")
def qapp():
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


def test_build_live_registry_wires_discovery(qapp):
    from ui.setup.state_machine import DEFAULT_SETUP_SPEC, SetupStep
    from ui.setup.steps import CameraSelectStep, PairedPreviewStep

    catalog = _FakeCatalog(sides={"LEFTSER": SIDE_LEFT, "RIGHTSER": SIDE_RIGHT})
    widgets = build_live_stereo_step_widgets(
        catalog=catalog,
        list_devices=_devices,
        preview_provider=lambda: simulated_paired_preview(frames=2),
    )
    assert set(widgets) == {spec.step for spec in DEFAULT_SETUP_SPEC}
    assert isinstance(widgets[SetupStep.SELECT_CAMERAS], CameraSelectStep)
    assert isinstance(widgets[SetupStep.PAIRED_PREVIEW], PairedPreviewStep)
    # The wired discovery provider should drive a real render on enter.
    widgets[SetupStep.SELECT_CAMERAS].on_enter()

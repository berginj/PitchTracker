"""Tests for stereo setup discovery and paired preview providers."""

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from contracts.catalog import SIDE_LEFT, SIDE_RIGHT, SIDE_UNASSIGNED  # noqa: E402
from exceptions import CameraError  # noqa: E402
from ui.setup.camera_select_view import grade_selection  # noqa: E402
from ui.setup.paired_preview_view import grade_preview  # noqa: E402
from ui.setup.providers import (  # noqa: E402
    _new_profile_id,
    capture_paired_preview,
    discover_camera_selection,
    make_camera_preview_provider,
    simulated_paired_preview,
)


def test_profile_ids_are_collision_resistant() -> None:
    profile_ids = {_new_profile_id() for _ in range(100)}

    assert len(profile_ids) == 100
    assert all(profile_id.startswith("rig_") and len(profile_id.rsplit("_", 1)[-1]) == 12 for profile_id in profile_ids)


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
        return SimpleNamespace(global_shutter=True) if friendly_name in self._recognized else None


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
    assert by_id["LEFTSER"].global_shutter is True
    # Distinct L/R assigned => selection passes.
    assert grade_selection(snap)[0] is True


def test_discover_recommends_previously_validated_pair_before_capability_ranking():
    devices = [
        *_devices(),
        {"serial": "SPARE", "friendly_name": "Arducam Spare", "instance_id": "USB\\3"},
    ]
    catalog = _FakeCatalog(recognized_names={item["friendly_name"] for item in devices})

    snap = discover_camera_selection(
        list_devices=lambda: devices,
        catalog=catalog,
        requested_mode=(1280, 720, 60),
        validated_pairs=(
            {
                "left_id": "RIGHTSER",
                "right_id": "LEFTSER",
                "profile_id": "rig-validated",
                "profile_revision": 4,
            },
        ),
    )

    assert snap.recommended_left_id == "RIGHTSER"
    assert snap.recommended_right_id == "LEFTSER"
    assert snap.recommendation_source == "previously_validated_profile"
    selected = {camera.hardware_id: camera for camera in snap.cameras}
    assert selected["RIGHTSER"].previously_validated is True
    assert selected["RIGHTSER"].recommended_side == SIDE_LEFT


def test_discover_recommends_best_requested_mode_capability_pair():
    from contracts.catalog import CameraCapabilities, CameraMode

    class CapabilityCatalog:
        def known_devices(self):
            return []

        def match_model(self, friendly_name):
            requested = friendly_name in {"Requested A", "Requested B"}
            modes = (
                (CameraMode(1280, 720, 60), CameraMode(640, 480, 120))
                if requested
                else (CameraMode(1920, 1080, 30),)
            )
            return SimpleNamespace(
                model="requested" if requested else "other",
                global_shutter=True,
                capabilities=CameraCapabilities(
                    supported_modes=modes,
                    controls=("exposure", "gain"),
                    global_shutter=True,
                    sync_capable=requested,
                ),
            )

    devices = [
        {"serial": "A", "friendly_name": "Requested A"},
        {"serial": "B", "friendly_name": "Requested B"},
        {"serial": "C", "friendly_name": "Other C"},
    ]
    snap = discover_camera_selection(
        list_devices=lambda: devices,
        catalog=CapabilityCatalog(),
        requested_mode=(1280, 720, 60),
    )

    assert {snap.recommended_left_id, snap.recommended_right_id} == {"A", "B"}
    assert snap.recommendation_source == "capability_score"


def test_discover_empty_device_list():
    snap = discover_camera_selection(list_devices=lambda: [], catalog=None)
    assert snap.cameras == ()
    assert grade_selection(snap) == (False, "No cameras discovered.")


def test_discover_recommends_diagnostic_fallback_pair_when_global_shutter_pair_is_unavailable():
    devices = [
        {"serial": "A", "friendly_name": "Webcam A"},
        {"serial": "B", "friendly_name": "Webcam B"},
        {"serial": "C", "friendly_name": "Webcam C"},
    ]

    snap = discover_camera_selection(
        list_devices=lambda: devices,
        catalog=_FakeCatalog(),
        requested_mode=(1280, 720, 60),
    )

    assert snap.recommended_left_id
    assert snap.recommended_right_id
    assert snap.recommended_left_id != snap.recommended_right_id
    assert snap.recommendation_source == "diagnostic_fallback"
    assert "diagnostic setup only" in snap.recommendation_reason


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

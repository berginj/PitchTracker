"""Tests for the stereo setup adapter providers (steps 1 & 2).

All tests run without hardware: camera discovery uses a fake device lister and a
fake catalog; paired preview uses the SimulatedCamera backend.
"""

import os
import sys
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from contracts.catalog import SIDE_LEFT, SIDE_RIGHT, SIDE_UNASSIGNED  # noqa: E402
from exceptions import CameraError  # noqa: E402
from ui.setup.camera_select_view import grade_selection  # noqa: E402
from ui.setup.paired_preview_view import grade_preview  # noqa: E402
from ui.setup.providers import (  # noqa: E402
    LiveSetupContext,
    _new_profile_id,
    build_live_stereo_step_widgets,
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


def test_live_context_persists_assignment_and_reuses_it_for_capture(tmp_path):
    from app.services.catalog import CameraCatalogService
    from capture.simulated_camera import SimulatedCamera

    catalog = CameraCatalogService(catalog_path=tmp_path / "catalog.json")
    context = LiveSetupContext(
        catalog=catalog,
        list_devices=_devices,
        camera_factory=SimulatedCamera,
    )
    context.assign("LEFTSER", "RIGHTSER")

    assert context.assigned_ids() == ("LEFTSER", "RIGHTSER")
    left, right = context.capture(frames=2)
    assert len(left) == len(right) == 2
    assert context.last_controls["left"]["readback_verified"] is True
    context.sync()
    assert context.last_qualification is not None
    assert context.last_qualification.controls_verified is True
    assert context.last_qualification.requested_mode == context.last_qualification.negotiated_mode


def test_reassignment_is_exclusive_and_resets_downstream_evidence(tmp_path):
    from app.services.catalog import CameraCatalogService

    devices = [
        *_devices(),
        {"serial": "NEWLEFT", "friendly_name": "Replacement Left", "instance_id": "USB\\3"},
    ]
    catalog = CameraCatalogService(catalog_path=tmp_path / "catalog.json")
    catalog.remember_device("LEFTSER", "Arducam Left", side=SIDE_LEFT)
    catalog.remember_device("RIGHTSER", "Arducam Right", side=SIDE_RIGHT)
    catalog.remember_device("NEWLEFT", "Replacement Left", side=SIDE_UNASSIGNED)
    context = LiveSetupContext(catalog=catalog, list_devices=lambda: devices)
    context.last_left_frames = [object()]
    context.last_right_frames = [object()]
    context.last_controls = {"left": {"readback_verified": True}}
    context.last_modes = {"left": {"fps": 60}}
    context.last_qualification = object()
    context.last_sync = object()
    context.last_focus = object()
    context.last_overlap = object()
    context.last_rectification = object()

    context.assign("NEWLEFT", "RIGHTSER")

    sides = {device.hardware_id: device.side for device in catalog.known_devices()}
    assert sides == {
        "LEFTSER": SIDE_UNASSIGNED,
        "RIGHTSER": SIDE_RIGHT,
        "NEWLEFT": SIDE_LEFT,
    }
    assert context.assigned_ids() == ("NEWLEFT", "RIGHTSER")
    assert context.last_left_frames == []
    assert context.last_right_frames == []
    assert context.last_controls == {}
    assert context.last_modes == {}
    assert context.last_qualification is None
    assert context.last_sync is None
    assert context.last_focus is None
    assert context.last_overlap is None
    assert context.last_rectification is None


def test_degraded_capture_qualification_fails_final_report(monkeypatch):
    from contracts import QUALITY_DEGRADED, QualityAssessment
    from contracts.setup import (
        CalibrationQualityReport,
        QUALITY_GRADE_FAIL,
        QUALITY_GRADE_GOOD,
        StereoCalibrationProfile,
    )
    import calib.stereo_setup.quality_report as quality_report_module
    import ui.setup.persist_profile_view as persist_profile_module

    stereo = StereoCalibrationProfile(
        baseline_in=19.5,
        rms_reprojection_px=0.3,
        epipolar_error_px=0.2,
        image_width=1280,
        image_height=720,
        source="charuco",
        production_ready=True,
        calibration_file="stereo_calibration.npz",
    )
    passing = CalibrationQualityReport(
        grade=QUALITY_GRADE_GOOD,
        rms_reprojection_px=0.3,
        epipolar_error_px=0.2,
        baseline_in=19.5,
        passed=True,
    )
    monkeypatch.setattr(persist_profile_module, "build_stereo_profile_from_report", lambda _path: stereo)
    monkeypatch.setattr(quality_report_module, "build_quality_report", lambda **_kwargs: passing)
    context = LiveSetupContext(catalog=None)
    context.last_qualification = SimpleNamespace(
        assessment=QualityAssessment(
            assessment_id="setup-current",
            scope="capture_qualification",
            status=QUALITY_DEGRADED,
            reason_codes=["FPS_SHORTFALL_RATIO_LEFT_EXCEEDS_WARN_LIMIT"],
        )
    )

    report = context.quality_report()

    assert report.grade == QUALITY_GRADE_FAIL
    assert report.passed is False
    assert any("degraded" in warning.lower() for warning in report.warnings)
    assert any("FPS_SHORTFALL_RATIO_LEFT" in warning for warning in report.warnings)


def test_fake_live_persistence_writes_and_activates_profile(tmp_path, monkeypatch):
    from app.services.catalog import CameraCatalogService
    from app.services.rig_profile import RigProfileService
    from configs.settings import load_config
    from contracts.setup import CalibrationQualityReport, QUALITY_GRADE_GOOD, StereoCalibrationProfile

    config_path = (Path(__file__).parent.parent / "configs" / "default.yaml").resolve()
    monkeypatch.chdir(tmp_path)
    calibration_dir = tmp_path / "calibration"
    calibration_dir.mkdir()
    (calibration_dir / "stereo_calibration.npz").write_bytes(b"fake-calibration")
    (calibration_dir / "field_transform.json").write_text(
        json.dumps(
            {
                "matrix_4x4": [
                    [1, 0, 0, 2],
                    [0, 1, 0, 3],
                    [0, 0, 1, 0],
                    [0, 0, 0, 1],
                ],
                "rms_residual_ft": 0.01,
                "max_rms_residual_ft": 0.1,
                "fixture_id": "field-targets",
                "fixture_source_sha256": "a" * 64,
                "fixture_point_count": 4,
            }
        ),
        encoding="utf-8",
    )
    roi_dir = tmp_path / "rois"
    roi_dir.mkdir()
    (roi_dir / "shared_rois.json").write_text("{}", encoding="utf-8")
    catalog = CameraCatalogService(catalog_path=tmp_path / "catalog.json")
    context = LiveSetupContext(catalog=catalog, list_devices=_devices, config_path=config_path)
    context.assign("LEFTSER", "RIGHTSER")
    context.last_modes = {
        "left": {"width": 1280, "height": 720, "fps": 60.0, "pixfmt": "YUYV"},
        "right": {"width": 1280, "height": 720, "fps": 60.0, "pixfmt": "YUYV"},
    }
    context.last_controls = {
        "left": {
            "readback_verified": True,
            "resolved_wb": 4700.0,
            "wb_source": "auto_sampled_then_locked",
        },
        "right": {
            "readback_verified": True,
            "resolved_wb": 4725.0,
            "wb_source": "auto_sampled_then_locked",
        },
    }
    context.quality_report = lambda: CalibrationQualityReport(
        grade=QUALITY_GRADE_GOOD,
        rms_reprojection_px=0.3,
        epipolar_error_px=0.2,
        baseline_in=19.5,
        passed=True,
    )
    stereo = StereoCalibrationProfile(
        baseline_in=19.5,
        rms_reprojection_px=0.3,
        epipolar_error_px=0.2,
        image_width=1280,
        image_height=720,
        source="charuco",
        production_ready=True,
        calibration_file="stereo_calibration.npz",
    )

    profile_id = context.persist_profile(stereo)

    service = RigProfileService(config_path=config_path)
    active = service.load_active()
    assert active is not None
    assert active.profile_id == profile_id
    assert active.hardware_fingerprint["left_friendly_name"] == "Arducam Left"
    assert active.hardware_fingerprint["right_friendly_name"] == "Arducam Right"
    assert active.control_settings["wb"] == 4700
    assert active.control_settings["wb_source"] == "auto_sampled_then_locked"
    assert active.control_settings["resolved_wb_by_camera"] == {"left": 4700.0, "right": 4725.0}
    assert active.field_transform["fixture_source_sha256"] == "a" * 64
    assert active.field_transform["fixture_point_count"] == 4
    runtime_config = service.apply_profile_to_config(load_config(config_path), active)
    assert runtime_config.camera.wb == 4700
    assert service.calibration_path(active).read_bytes() == b"fake-calibration"
    assert service.roi_path(active).read_text(encoding="utf-8") == "{}"
    assert active.artifact_hashes.keys() >= {"calibration", "roi"}

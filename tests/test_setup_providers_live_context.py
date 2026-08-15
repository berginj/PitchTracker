"""Tests for live stereo setup context and persistence providers."""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from contracts.catalog import SIDE_LEFT, SIDE_RIGHT, SIDE_UNASSIGNED  # noqa: E402
from ui.setup.providers import (  # noqa: E402
    LiveSetupContext,
    build_live_stereo_step_widgets,
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
        return SimpleNamespace(global_shutter=True) if friendly_name in self._recognized else None


def _devices():
    return [
        {"serial": "LEFTSER", "friendly_name": "Arducam Left", "instance_id": "USB\\1"},
        {"serial": "RIGHTSER", "friendly_name": "Arducam Right", "instance_id": "USB\\2"},
    ]


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
    assert set(context.last_capability_observations) == {"left", "right"}
    assert context.last_capability_observations["left"].camera_id == "LEFTSER"
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
    context.last_capability_observations = {"left": object()}
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
    assert context.last_capability_observations == {}
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
    from contracts.capability_observation import build_simulated_observation

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
    context.last_capability_observations = {
        "left": build_simulated_observation("LEFTSER", context.last_modes["left"], {}),
        "right": build_simulated_observation("RIGHTSER", context.last_modes["right"], {}),
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
    assert active.setup_snapshot["schema_version"] == "setup_system_snapshot.v2"
    snapshot_cameras = active.setup_snapshot["sections"]["cameras"]
    assert snapshot_cameras["left"]["capability_observation"]["camera_id"] == "LEFTSER"
    assert snapshot_cameras["right"]["capability_observation"]["camera_id"] == "RIGHTSER"
    assert service.setup_snapshot_path(active).exists()
    assert active.artifact_hashes.keys() >= {"setup_snapshot"}

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from analysis.camera_alignment_internals import _assess_quality
from app.pipeline.initialization import PipelineInitializer
from app.services.orchestrator import PipelineOrchestrator
from app.services.rig_profile import RigProfile, RigProfileService
from configs.roi_io import load_runtime_roi_maps
from configs.settings import load_config


def _config():
    return load_config(Path(__file__).parent.parent / "configs" / "default.yaml")


def _write_calibration(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        mtx_left=np.eye(3),
        mtx_right=np.eye(3),
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[304.8], [0.0], [0.0]]),
        img_size=np.array([1280, 720]),
        quality_rating="GOOD",
        rms_error_px=0.4,
        calibration_mode="FULL",
        production_ready=True,
        num_images_used=12,
    )


def _write_roi(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "lane_by_camera": {
                    "left_cam": [[10, 10], [110, 10], [110, 100], [10, 100]],
                    "right_cam": [[20, 10], [120, 10], [120, 100], [20, 100]],
                },
                "plate": [[30, 30], [90, 30], [90, 70], [30, 70]],
            }
        ),
        encoding="utf-8",
    )


def _activate_profile(tmp_path: Path) -> RigProfile:
    service = RigProfileService(base_dir=tmp_path / "calibration" / "rigs")
    cfg = _config()
    profile = RigProfile.from_config(
        "rig_active",
        cfg,
        backend="sim",
        left_serial="left_cam",
        right_serial="right_cam",
        quality_metrics={"calibration_mode": "FULL"},
    )
    profile = RigProfile.from_dict(
        {
            **profile.to_dict(),
            "image_transforms": {
                "flip_left": True,
                "flip_right": False,
                "rotation_left": 1.25,
                "rotation_right": -0.75,
                "vertical_offset_px": 4,
            },
        }
    )
    profile_dir = service.profile_dir(profile.profile_id)
    _write_calibration(profile_dir / profile.calibration_file)
    _write_roi(profile_dir / profile.roi_file)
    return service.save(profile, activate=True)


class DummyCamera:
    def __init__(self) -> None:
        self.mode_args = None

    def set_mode(self, *args, **kwargs) -> None:
        self.mode_args = (args, kwargs)

    def set_controls(self, *args, **kwargs) -> None:
        pass


def test_camera_transform_contract_propagates_to_left_and_right() -> None:
    cfg = _config()
    cfg = RigProfileService().apply_profile_to_config(
        cfg,
        RigProfile.from_dict(
            {
                "profile_id": "p",
                "created_utc": "2026-01-01T00:00:00Z",
                "updated_utc": "2026-01-01T00:00:00Z",
                "backend": "sim",
                "image_transforms": {
                    "flip_left": True,
                    "flip_right": True,
                    "rotation_left": 1.5,
                    "rotation_right": -2.5,
                    "vertical_offset_px": 7,
                },
            }
        ),
    )
    left = DummyCamera()
    right = DummyCamera()

    PipelineInitializer.configure_camera(left, cfg, is_left=True)
    PipelineInitializer.configure_camera(right, cfg, is_left=False)

    assert left.mode_args[1]["flip_180"] is True
    assert left.mode_args[1]["rotation_correction"] == 1.5
    assert left.mode_args[1]["vertical_offset_px"] == 0
    assert right.mode_args[1]["flip_180"] is True
    assert right.mode_args[1]["rotation_correction"] == -2.5
    assert right.mode_args[1]["vertical_offset_px"] == 7


def test_profile_controls_are_authoritative_at_runtime() -> None:
    cfg = _config()
    profile = RigProfile.from_dict(
        {
            "profile_id": "controls",
            "created_utc": "2026-01-01T00:00:00Z",
            "updated_utc": "2026-01-01T00:00:00Z",
            "backend": "sim",
            "control_settings": {
                "exposure_us": 3500,
                "gain": 4.5,
                "wb_mode": None,
                "wb": 4200,
            },
        }
    )

    applied = RigProfileService().apply_profile_to_config(cfg, profile)

    assert applied.camera.exposure_us == 3500
    assert applied.camera.gain == 4.5
    assert applied.camera.wb_mode is None
    assert applied.camera.wb == 4200


def test_alignment_quality_near_zero_correlation_is_not_critical() -> None:
    assert _assess_quality(0.0, 2.0, 0.0, 0.0, 0.0) == "EXCELLENT"
    assert _assess_quality(0.0, 45.0, 0.0, 0.0, 0.0) == "CRITICAL"
    assert _assess_quality(0.0, 2.0, 0.0, 0.0, 16.0) == "CRITICAL"
    assert _assess_quality(-12.0, 2.0, 0.0, 0.0, 0.0) == "ACCEPTABLE"


def test_runtime_roi_maps_read_profile_file(tmp_path: Path) -> None:
    roi_path = tmp_path / "roi.json"
    _write_roi(roi_path)

    lane, plate = load_runtime_roi_maps(roi_path, "left_cam", "right_cam")

    assert lane["left_cam"][0] == (10, 10)
    assert lane["right_cam"][0] == (20, 10)
    assert plate["left_cam"][0] == (30, 30)
    assert plate["right_cam"][0] == (30, 30)


def test_reload_rois_updates_detection_service(tmp_path: Path) -> None:
    roi_path = tmp_path / "roi.json"
    _write_roi(roi_path)
    orchestrator = PipelineOrchestrator(backend="sim")
    calls = []

    class FakeDetectionService:
        def set_lane_rois(self, lane_rois, plate_rois=None):
            calls.append((lane_rois, plate_rois))

    orchestrator._detection_service = FakeDetectionService()
    orchestrator._runtime_roi_path = roi_path
    orchestrator._left_serial = "left_cam"
    orchestrator._right_serial = "right_cam"

    orchestrator.reload_rois()

    lane_rois, plate_rois = calls[-1]
    assert sorted(lane_rois) == ["left_cam", "right_cam"]
    assert lane_rois["left_cam"][0] == (10, 10)
    assert lane_rois["right_cam"][0] == (20, 10)
    assert sorted(plate_rois) == ["left_cam", "right_cam"]


def test_orchestrator_rejects_critical_rig_profile_before_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _activate_profile(tmp_path)
    orchestrator = PipelineOrchestrator(backend="sim")

    with pytest.raises(RuntimeError, match="Rig profile runtime validation is CRITICAL"):
        orchestrator.start_capture(_config(), left_serial="wrong_left", right_serial="right_cam")

    assert orchestrator.is_capturing() is False


def test_orchestrator_startup_uses_active_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    profile = _activate_profile(tmp_path)
    cfg = _config()
    orchestrator = PipelineOrchestrator(backend="sim")

    try:
        orchestrator.start_capture(cfg, left_serial="left_cam", right_serial="right_cam")

        assert orchestrator._active_rig_profile is not None
        assert orchestrator._active_rig_profile.profile_id == profile.profile_id
        assert orchestrator._runtime_calibration_path == tmp_path / "calibration/rigs/rig_active/stereo_calibration.npz"
        assert orchestrator._runtime_roi_path == tmp_path / "calibration/rigs/rig_active/roi.json"
        assert orchestrator._config.camera.flip_left is True
        assert orchestrator._config.camera.rotation_left == 1.25
        assert orchestrator._config.camera.vertical_offset_px == 4
    finally:
        orchestrator.stop_capture()

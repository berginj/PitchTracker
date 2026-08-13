from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.services.rig_profile import CRITICAL, PASS, WARN, RigProfile, RigProfileService
from configs.settings import load_config


def _config():
    return load_config(Path(__file__).parent.parent / "configs" / "default.yaml")


def _write_calibration(
    path: Path,
    *,
    mode: str = "FULL",
    quality: str = "GOOD",
    rms_error_px: float = 0.42,
    include_production_metadata: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(
        mtx_left=np.eye(3),
        mtx_right=np.eye(3),
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[304.8], [0.0], [0.0]]),
        F=np.eye(3),
        img_size=np.array([1280, 720]),
        quality_rating=quality,
        rms_error_px=rms_error_px,
        num_images_used=12,
        per_image_errors=np.asarray(
            [
                {
                    "left_rms": rms_error_px,
                    "right_rms": rms_error_px,
                    "combined_rms": rms_error_px,
                }
                for _ in range(12)
            ],
            dtype=object,
        ),
    )
    if include_production_metadata:
        payload["calibration_mode"] = mode
        payload["production_ready"] = mode != "QUICK"
    np.savez(path, **payload)


def _write_roi(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "lane": [[10, 10], [100, 10], [100, 100], [10, 100]],
                "plate": [[20, 20], [80, 20], [80, 60], [20, 60]],
                "lane_by_camera": {
                    "left_cam": [[10, 10], [100, 10], [100, 100], [10, 100]],
                    "right_cam": [[12, 10], [102, 10], [102, 100], [12, 100]],
                },
            }
        ),
        encoding="utf-8",
    )


def _profile(service: RigProfileService, *, mode: str = "FULL", backend: str = "sim") -> RigProfile:
    cfg = _config()
    profile = RigProfile.from_config(
        "rig_a",
        cfg,
        backend=backend,
        left_serial="left_cam",
        right_serial="right_cam",
        quality_metrics={"calibration_mode": mode},
    )
    profile_dir = service.profile_dir(profile.profile_id)
    _write_calibration(profile_dir / profile.calibration_file, mode=mode)
    _write_roi(profile_dir / profile.roi_file)
    return service.save(profile, activate=True)


def test_rig_profile_save_load_and_validate_pass(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    saved = _profile(service)

    loaded = service.load_active()
    assert loaded is not None
    assert loaded.profile_id == saved.profile_id

    validation = service.validate_for_runtime(
        loaded,
        config=_config(),
        backend="sim",
        left_serial="left_cam",
        right_serial="right_cam",
    )

    assert validation.state == PASS
    assert validation.issues == []


def test_rig_profile_missing_calibration_is_critical(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    cfg = _config()
    profile = service.save(RigProfile.from_config("rig_a", cfg, backend="sim"), activate=True)
    _write_roi(service.profile_dir(profile.profile_id) / profile.roi_file)

    validation = service.validate_for_runtime(profile, config=cfg)

    assert validation.state == CRITICAL
    assert any("Calibration file not found" in item for item in validation.issues)


def test_rig_profile_bad_roi_is_critical(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service)
    roi_path = service.profile_dir(profile.profile_id) / profile.roi_file
    roi_path.write_text(json.dumps({"lane": [[1, 2], [3, 4]]}), encoding="utf-8")

    validation = service.validate_for_runtime(profile, config=_config())

    assert validation.state == CRITICAL
    assert any("invalid polygons" in item for item in validation.issues)


def test_rig_profile_camera_serial_mismatch_is_critical(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service)

    validation = service.validate_for_runtime(
        profile,
        config=_config(),
        left_serial="wrong_left",
        right_serial="right_cam",
    )

    assert validation.state == CRITICAL
    assert any("Left camera serial mismatch" in item for item in validation.issues)


def test_physical_runtime_backend_mismatch_is_critical(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service)

    validation = service.validate_for_runtime(profile, config=_config(), backend="uvc")

    assert validation.state == CRITICAL
    assert any("backend is sim" in item for item in validation.issues)


def test_quick_calibration_profile_warns_not_production_ready(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service, mode="QUICK")

    validation = service.validate_for_runtime(profile, config=_config())

    assert validation.state == WARN
    assert any("Quick calibration" in item for item in validation.warnings)


def test_quick_calibration_profile_is_critical_for_physical_backend(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service, mode="QUICK")

    validation = service.validate_for_runtime(profile, config=_config(), backend="uvc")

    assert validation.state == CRITICAL
    assert any("Quick calibration" in item for item in validation.issues)


def test_legacy_scalar_fallback_is_critical_for_physical_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_roi(Path("rois/shared_rois.json"))

    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = service.legacy_fallback(_config(), backend="uvc")

    validation = service.validate_for_runtime(profile, config=_config(), backend="uvc")

    assert validation.state == CRITICAL
    assert any("Calibration file not found" in item for item in validation.issues)


def test_high_rms_calibration_is_critical_for_physical_backend(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service)
    _write_calibration(service.profile_dir(profile.profile_id) / profile.calibration_file, rms_error_px=3.2)

    validation = service.validate_for_runtime(profile, config=_config(), backend="uvc")

    assert validation.state == CRITICAL
    assert any("RMS reprojection" in item for item in validation.issues)


def test_matrix_complete_calibration_without_explicit_metadata_is_critical_for_physical_backend(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service, backend="uvc")
    calibration_path = service.profile_dir(profile.profile_id) / profile.calibration_file
    _write_calibration(calibration_path, include_production_metadata=False)
    profile = service.save(replace(profile, artifact_hashes={}))

    validation = service.validate_for_runtime(profile, config=_config(), backend="uvc")

    assert validation.state == CRITICAL
    assert validation.diagnostics["calibration_mode"] == "UNKNOWN"
    assert any("diagnostic-only" in item for item in validation.issues)


def test_profile_save_preserves_existing_json_when_atomic_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service)
    profile_path = service.profile_path(profile.profile_id)
    original = profile_path.read_bytes()

    def fail_replace(_source, _destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("app.services.rig_profile_persistence.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        service.save(replace(profile, diagnostics={"changed": True}))

    assert profile_path.read_bytes() == original
    assert not list(profile_path.parent.glob(f".{profile_path.name}.*.tmp"))


def test_activation_preserves_existing_marker_when_atomic_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    first = _profile(service)
    second = replace(first, profile_id="rig_b")
    service.save(second)
    original = service.active_marker.read_bytes()

    def fail_replace(_source, _destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("app.services.rig_profile_persistence.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        service.activate(second.profile_id)

    assert service.active_marker.read_bytes() == original
    assert not list(service.active_marker.parent.glob(f".{service.active_marker.name}.*.tmp"))


def test_legacy_fallback_uses_existing_legacy_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_calibration(Path("calibration/stereo_calibration.npz"))
    _write_roi(Path("rois/shared_rois.json"))

    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = service.legacy_fallback(_config(), backend="sim")

    assert profile.profile_id == "legacy"
    assert service.calibration_path(profile) == Path("calibration/stereo_calibration.npz")
    assert service.roi_path(profile) == Path("rois/shared_rois.json")


def test_rig_profile_nests_typed_stereo_profile_and_round_trips():
    from contracts.setup import StereoCalibrationProfile

    stereo = StereoCalibrationProfile(
        baseline_in=8.0,
        rms_reprojection_px=0.4,
        epipolar_error_px=0.3,
        image_width=1280,
        image_height=720,
        source="charuco",
        production_ready=True,
        calibration_file="stereo_calibration.npz",
        created_utc="2024-01-01T00:00:00Z",
        app_version="1.5.0",
        schema_version="1.0",
    )
    profile = RigProfile(
        schema_version="1.0",
        profile_id="rig-1",
        created_utc="2024-01-01T00:00:00Z",
        updated_utc="2024-01-01T00:00:00Z",
        backend="uvc",
        stereo_profile=stereo,
    )
    assert profile.production_ready is True

    restored = RigProfile.from_dict(json.loads(json.dumps(profile.to_dict())))
    assert restored.stereo_profile == stereo
    assert restored.production_ready is True


def test_rig_profile_without_stereo_profile_is_not_production_ready():
    profile = RigProfile.from_dict({"profile_id": "legacy"})
    assert profile.stereo_profile is None
    assert profile.production_ready is False

"""Tests for Phase D calibration hardening.

Covers the production-ready guard in PipelineInitializer.create_stereo_matcher,
F/E persistence helpers, and degenerate-geometry rejection in quick_calibrate.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.pipeline.initialization import PipelineInitializer
from calib.quick_calibrate import _validate_stereo_geometry
from configs.settings import load_config
from exceptions import CalibrationExecutionError
from stereo.calibrated_stereo import CalibratedStereoMatcher
from stereo.simple_stereo import SimpleStereoMatcher


def _write_npz(path: Path, production_ready: bool, include_flag: bool = True) -> None:
    k = np.array([[600, 0, 320], [0, 600, 240], [0, 0, 1]], dtype=np.float64)
    kwargs = dict(
        mtx_left=k,
        mtx_right=k,
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[-120.0], [0.0], [0.0]]),
        F=np.eye(3),
        img_size=np.array([640, 480]),
    )
    if include_flag:
        kwargs["production_ready"] = production_ready
    np.savez(path, **kwargs)


@pytest.fixture
def config():
    return load_config(Path("configs/default.yaml"))


def test_production_ready_calibration_is_used(tmp_path, config):
    npz = tmp_path / "stereo_calibration.npz"
    _write_npz(npz, production_ready=True)
    matcher = PipelineInitializer.create_stereo_matcher(config, npz)
    assert isinstance(matcher, CalibratedStereoMatcher)


def test_quick_mode_calibration_is_rejected(tmp_path, config):
    npz = tmp_path / "stereo_calibration.npz"
    _write_npz(npz, production_ready=False)
    matcher = PipelineInitializer.create_stereo_matcher(config, npz)
    # Falls back to config-driven uncalibrated geometry.
    assert isinstance(matcher, SimpleStereoMatcher)


def test_non_production_can_be_opted_in(tmp_path, config):
    npz = tmp_path / "stereo_calibration.npz"
    _write_npz(npz, production_ready=False)
    matcher = PipelineInitializer.create_stereo_matcher(config, npz, allow_non_production_calibration=True)
    assert isinstance(matcher, CalibratedStereoMatcher)


def test_legacy_calibration_without_flag_is_used(tmp_path, config):
    npz = tmp_path / "stereo_calibration.npz"
    _write_npz(npz, production_ready=True, include_flag=False)
    matcher = PipelineInitializer.create_stereo_matcher(config, npz)
    assert isinstance(matcher, CalibratedStereoMatcher)


def test_missing_calibration_uses_config_geometry(tmp_path, config):
    npz = tmp_path / "does_not_exist.npz"
    matcher = PipelineInitializer.create_stereo_matcher(config, npz)
    assert isinstance(matcher, SimpleStereoMatcher)


# --------------------- degenerate-geometry rejection ----------------------


def test_validate_accepts_reasonable_geometry():
    _validate_stereo_geometry(0.4, 0.5, np.eye(3))  # should not raise


def test_validate_rejects_tiny_baseline():
    with pytest.raises(CalibrationExecutionError):
        _validate_stereo_geometry(0.4, 0.001, np.eye(3))


def test_validate_rejects_nonfinite_rms():
    with pytest.raises(CalibrationExecutionError):
        _validate_stereo_geometry(float("nan"), 0.5, np.eye(3))


def test_validate_rejects_absurd_rms():
    with pytest.raises(CalibrationExecutionError):
        _validate_stereo_geometry(999.0, 0.5, np.eye(3))


def test_validate_rejects_nonfinite_fundamental():
    bad_f = np.full((3, 3), np.inf)
    with pytest.raises(CalibrationExecutionError):
        _validate_stereo_geometry(0.4, 0.5, bad_f)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])

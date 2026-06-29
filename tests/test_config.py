from pathlib import Path

import pytest
import yaml

from configs.settings import load_config
from exceptions import ConfigValidationError


def test_load_config() -> None:
    config = load_config(Path("configs/default.yaml"))

    assert config.camera.width == 1280
    assert config.stereo.pairing_tolerance_ms == 8
    assert config.metrics.velo_bounds_mph == (30, 110)
    assert config.trajectory.primary_mode == "stereo_3d"


def test_default_config_keeps_generic_scalar_stereo_fallback() -> None:
    """Shared defaults must not contain a local rig calibration."""
    config = load_config(Path("configs/default.yaml"))

    assert config.stereo.baseline_ft == 1.625
    assert config.stereo.focal_length_px == 1200.0
    assert config.stereo.cx is None
    assert config.stereo.cy is None


def test_load_all_trajectory_modes(tmp_path: Path) -> None:
    data = yaml.safe_load(Path("configs/default.yaml").read_text())
    data["trajectory"]["primary_mode"] = "ray_reprojection"
    data["trajectory"]["compare_modes"] = ["stereo_3d", "ray_graph"]

    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data))

    config = load_config(path)

    assert config.trajectory.primary_mode == "ray_reprojection"
    assert config.trajectory.compare_modes == ("stereo_3d", "ray_graph")


def test_reject_unknown_trajectory_mode(tmp_path: Path) -> None:
    data = yaml.safe_load(Path("configs/default.yaml").read_text())
    data["trajectory"]["primary_mode"] = "not_a_mode"

    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(ConfigValidationError):
        load_config(path)

from pathlib import Path

from configs.settings import load_config


def test_load_config() -> None:
    config = load_config(Path("configs/default.yaml"))

    assert config.camera.width == 1920
    assert config.stereo.pairing_tolerance_ms == 8
    assert config.metrics.velo_bounds_mph == (30, 110)

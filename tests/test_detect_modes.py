"""Tests for detect/modes.py — verify background stays float32."""

from __future__ import annotations

import numpy as np
import pytest

from detect.config import DetectorConfig
from detect.modes import detect_mode_a, detect_mode_b


@pytest.fixture
def config() -> DetectorConfig:
    return DetectorConfig()


class TestModeABackgroundDtype:
    def test_initial_background_is_float32(self, config: DetectorConfig) -> None:
        frame = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        dets, bg = detect_mode_a(frame, None, None, config)
        assert bg.dtype == np.float32

    def test_updated_background_stays_float32(self, config: DetectorConfig) -> None:
        f1 = np.random.randint(0, 255, (64, 64), dtype=np.uint8).astype(np.float32)
        f2 = f1 + 5.0
        dets, bg = detect_mode_a(f2, f1, f1, config)
        assert bg.dtype == np.float32

    def test_detections_unchanged_with_float_bg(self, config: DetectorConfig) -> None:
        bg = np.full((64, 64), 100.0, dtype=np.float32)
        f1 = np.full((64, 64), 100.0, dtype=np.float32)
        f2 = np.full((64, 64), 100.0, dtype=np.float32)
        f2[20:30, 20:30] = 200.0  # bright blob
        dets, _ = detect_mode_a(f2, f1, bg, config)
        assert len(dets) >= 1


class TestModeBBackgroundDtype:
    def test_initial_background_is_float32(self, config: DetectorConfig) -> None:
        frame = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        dets, bg = detect_mode_b(frame, None, config)
        assert bg.dtype == np.float32

    def test_updated_background_stays_float32(self, config: DetectorConfig) -> None:
        bg = np.full((64, 64), 128.0, dtype=np.float32)
        frame = np.full((64, 64, 3), 130, dtype=np.uint8)
        dets, new_bg = detect_mode_b(frame, bg, config)
        assert new_bg.dtype == np.float32

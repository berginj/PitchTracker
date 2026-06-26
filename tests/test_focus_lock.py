"""Tests for focus and exposure lock evaluation (setup step 4)."""

from __future__ import annotations

import cv2
import numpy as np

from calib.stereo_setup import (
    DEFAULT_SHARPNESS_THRESHOLD,
    ExposureLockInput,
    ExposureValues,
    evaluate_exposure_lock,
    evaluate_focus_lock,
)
from contracts.setup import (
    LOCK_VERDICT_LOCKED,
    LOCK_VERDICT_MARGINAL,
    LOCK_VERDICT_UNLOCKED,
)


def _sharp_image(width: int = 320, height: int = 240, seed: int = 1) -> np.ndarray:
    """High-frequency noise image -> high variance of Laplacian."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width), dtype=np.uint8)


def _blurry_image(width: int = 320, height: int = 240) -> np.ndarray:
    """Heavily blurred image -> low variance of Laplacian."""
    sharp = _sharp_image(width, height)
    return cv2.GaussianBlur(sharp, (0, 0), sigmaX=8)


# ------------------------------ focus lock --------------------------------


def test_focus_lock_sharp_and_autofocus_off_is_locked():
    result = evaluate_focus_lock("left", _sharp_image(), autofocus_disabled=True)
    assert result.verdict == LOCK_VERDICT_LOCKED
    assert result.passed is True
    assert result.sharpness >= DEFAULT_SHARPNESS_THRESHOLD


def test_focus_lock_sharp_but_autofocus_on_is_unlocked():
    result = evaluate_focus_lock("left", _sharp_image(), autofocus_disabled=False)
    assert result.verdict == LOCK_VERDICT_UNLOCKED
    assert result.passed is False
    assert "autofocus" in result.recommendation.lower()


def test_focus_lock_blurry_is_unlocked():
    result = evaluate_focus_lock("right", _blurry_image(), autofocus_disabled=True)
    assert result.verdict == LOCK_VERDICT_UNLOCKED
    assert result.passed is False


def test_focus_lock_marginal_sharpness():
    img = _sharp_image()
    sharpness = float(cv2.Laplacian(img, cv2.CV_64F, ksize=3).var())
    # Threshold just above actual sharpness, but within the marginal band.
    threshold = sharpness / 0.8
    result = evaluate_focus_lock("left", img, autofocus_disabled=True, sharpness_threshold=threshold)
    assert result.verdict == LOCK_VERDICT_MARGINAL
    assert result.passed is False


def test_focus_lock_payload_round_trips():
    payload = evaluate_focus_lock("left", _sharp_image(), autofocus_disabled=True).to_payload()
    assert payload["camera_id"] == "left"
    assert payload["passed"] is True


# ----------------------------- exposure lock ------------------------------


def _values(exp=8000.0, gain=4.0, wb=4500.0) -> ExposureValues:
    return ExposureValues(exposure_us=exp, gain=gain, white_balance_k=wb)


def test_exposure_lock_verified_and_autos_off_is_locked():
    data = ExposureLockInput(
        applied=_values(),
        readback=_values(),
        auto_exposure_disabled=True,
        auto_white_balance_disabled=True,
    )
    result = evaluate_exposure_lock("left", data)
    assert result.verdict == LOCK_VERDICT_LOCKED
    assert result.passed is True
    assert result.readback_verified is True


def test_exposure_lock_autos_on_is_unlocked():
    data = ExposureLockInput(
        applied=_values(),
        readback=_values(),
        auto_exposure_disabled=False,
        auto_white_balance_disabled=True,
    )
    result = evaluate_exposure_lock("left", data)
    assert result.verdict == LOCK_VERDICT_UNLOCKED
    assert result.passed is False


def test_exposure_lock_readback_mismatch_is_marginal():
    data = ExposureLockInput(
        applied=_values(exp=8000.0),
        readback=_values(exp=12000.0),  # device ignored the write
        auto_exposure_disabled=True,
        auto_white_balance_disabled=True,
    )
    result = evaluate_exposure_lock("left", data)
    assert result.verdict == LOCK_VERDICT_MARGINAL
    assert result.readback_verified is False
    assert result.passed is False


def test_exposure_lock_no_readback_is_marginal_when_autos_off():
    data = ExposureLockInput(
        applied=_values(),
        readback=None,
        auto_exposure_disabled=True,
        auto_white_balance_disabled=True,
    )
    result = evaluate_exposure_lock("left", data)
    assert result.verdict == LOCK_VERDICT_MARGINAL
    assert result.readback_verified is False


def test_exposure_lock_within_tolerance_is_locked():
    data = ExposureLockInput(
        applied=_values(exp=8000.0),
        readback=_values(exp=8400.0),  # 5% off, within 10% tolerance
        auto_exposure_disabled=True,
        auto_white_balance_disabled=True,
    )
    result = evaluate_exposure_lock("left", data, rel_tolerance=0.1)
    assert result.verdict == LOCK_VERDICT_LOCKED
    assert result.readback_verified is True


def test_exposure_lock_payload_round_trips():
    data = ExposureLockInput(
        applied=_values(),
        readback=_values(),
        auto_exposure_disabled=True,
        auto_white_balance_disabled=True,
    )
    payload = evaluate_exposure_lock("left", data).to_payload()
    assert set(payload).issuperset({"exposure_us", "gain", "white_balance_k", "readback_verified", "verdict"})

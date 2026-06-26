"""Fixed-focus and exposure-lock evaluation (setup step 4).

The target ArduCam cameras are fixed-focus global-shutter devices, so this step
*verifies* sharpness at the working distance and confirms that autofocus /
auto-exposure / auto-white-balance are disabled and that locked control values
actually took effect on the device. It does not hunt focus.

These functions are pure: given an image (for sharpness) and the applied /
read-back control values, they compute a verdict. Device I/O lives in the
capture backends; this module only judges the results so it can be unit-tested
without hardware.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from contracts.setup import (
    LOCK_VERDICT_LOCKED,
    LOCK_VERDICT_MARGINAL,
    LOCK_VERDICT_UNLOCKED,
    ExposureLockResult,
    FocusLockResult,
)
from detect.utils import compute_focus_score
from log_config.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SHARPNESS_THRESHOLD = 100.0
_MARGINAL_FRACTION = 0.6


def evaluate_focus_lock(
    camera_id: str,
    image: np.ndarray,
    autofocus_disabled: bool,
    sharpness_threshold: float = DEFAULT_SHARPNESS_THRESHOLD,
) -> FocusLockResult:
    """Judge fixed-focus sharpness for a single camera.

    Args:
        camera_id: Camera label or serial.
        image: A frame captured at the working distance (gray or BGR).
        autofocus_disabled: True if autofocus is confirmed off/absent.
        sharpness_threshold: Minimum acceptable variance-of-Laplacian score.

    Returns:
        A :class:`FocusLockResult`. ``passed`` requires sharp AND autofocus off.
    """
    sharpness = compute_focus_score(image)
    sharp_enough = sharpness >= sharpness_threshold
    marginal = sharpness >= sharpness_threshold * _MARGINAL_FRACTION

    if sharp_enough and autofocus_disabled:
        verdict = LOCK_VERDICT_LOCKED
        recommendation = "Focus is sharp and autofocus is disabled."
    elif marginal and autofocus_disabled:
        verdict = LOCK_VERDICT_MARGINAL
        recommendation = (
            "Focus is borderline. Confirm the camera is at the intended "
            "working distance; these are fixed-focus lenses."
        )
    elif not autofocus_disabled:
        verdict = LOCK_VERDICT_UNLOCKED
        recommendation = (
            "Autofocus is still enabled. Disable autofocus before calibrating " "so focus cannot drift between pitches."
        )
    else:
        verdict = LOCK_VERDICT_UNLOCKED
        recommendation = "Image is too soft. Check focus, lighting, and lens cleanliness " "at the working distance."

    passed = verdict == LOCK_VERDICT_LOCKED
    logger.info(
        "Focus lock [{}]: sharpness={:.1f} thr={:.1f} af_off={} verdict={}",
        camera_id,
        sharpness,
        sharpness_threshold,
        autofocus_disabled,
        verdict,
    )
    return FocusLockResult(
        camera_id=camera_id,
        sharpness=float(sharpness),
        sharpness_threshold=float(sharpness_threshold),
        autofocus_disabled=bool(autofocus_disabled),
        verdict=verdict,
        passed=passed,
        recommendation=recommendation,
    )


@dataclass(frozen=True)
class ExposureValues:
    """A triple of exposure-related control values."""

    exposure_us: float
    gain: float
    white_balance_k: float


@dataclass(frozen=True)
class ExposureLockInput:
    """Inputs for judging an exposure/white-balance lock.

    Attributes:
        applied: Values written to the device.
        readback: Values read back from the device, or None if unavailable.
        auto_exposure_disabled: True if auto-exposure is confirmed off.
        auto_white_balance_disabled: True if auto-white-balance is confirmed off.
    """

    applied: ExposureValues
    readback: ExposureValues | None
    auto_exposure_disabled: bool
    auto_white_balance_disabled: bool


def _close(a: float, b: float, rel_tolerance: float) -> bool:
    if a == 0.0 and b == 0.0:
        return True
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom <= rel_tolerance


def evaluate_exposure_lock(
    camera_id: str,
    data: ExposureLockInput,
    rel_tolerance: float = 0.1,
) -> ExposureLockResult:
    """Judge whether exposure/gain/white-balance locks took effect.

    Args:
        camera_id: Camera label or serial.
        data: Applied/read-back values and auto-control flags.
        rel_tolerance: Allowed relative difference between applied and readback.

    Returns:
        An :class:`ExposureLockResult`. ``passed`` requires verified readback
        AND auto-exposure/auto-white-balance both disabled.
    """
    autos_off = data.auto_exposure_disabled and data.auto_white_balance_disabled
    if data.readback is None:
        readback_verified = False
    else:
        readback_verified = (
            _close(data.applied.exposure_us, data.readback.exposure_us, rel_tolerance)
            and _close(data.applied.gain, data.readback.gain, rel_tolerance)
            and _close(
                data.applied.white_balance_k,
                data.readback.white_balance_k,
                rel_tolerance,
            )
        )

    if autos_off and readback_verified:
        verdict = LOCK_VERDICT_LOCKED
        recommendation = "Exposure and white balance are locked and verified."
    elif autos_off and not readback_verified:
        verdict = LOCK_VERDICT_MARGINAL
        recommendation = (
            "Auto controls are off but the device did not confirm the locked "
            "values. Some DirectShow cameras silently ignore control writes."
        )
    else:
        verdict = LOCK_VERDICT_UNLOCKED
        recommendation = (
            "Auto-exposure or auto-white-balance is still enabled; lock both "
            "so brightness and color stay constant during a session."
        )

    passed = verdict == LOCK_VERDICT_LOCKED
    logger.info(
        "Exposure lock [{}]: autos_off={} readback_ok={} verdict={}",
        camera_id,
        autos_off,
        readback_verified,
        verdict,
    )
    return ExposureLockResult(
        camera_id=camera_id,
        exposure_us=float(data.applied.exposure_us),
        gain=float(data.applied.gain),
        white_balance_k=float(data.applied.white_balance_k),
        auto_exposure_disabled=bool(data.auto_exposure_disabled),
        auto_white_balance_disabled=bool(data.auto_white_balance_disabled),
        readback_verified=readback_verified,
        verdict=verdict,
        passed=passed,
        recommendation=recommendation,
    )

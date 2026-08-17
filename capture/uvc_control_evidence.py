"""Apply UVC controls and preserve DirectShow readback evidence."""

from __future__ import annotations

import math
from typing import Any, Optional

import cv2


def _safe_set(capture: cv2.VideoCapture, prop: int, value: float) -> bool:
    try:
        return bool(capture.set(prop, value))
    except (OSError, PermissionError, RuntimeError):
        return False


def _safe_get(capture: cv2.VideoCapture, prop: int) -> float | None:
    try:
        value = float(capture.get(prop))
    except (OSError, PermissionError, RuntimeError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _directshow_exposure_us(raw_value: float) -> float:
    if raw_value < 0:
        return float((2.0**raw_value) * 1_000_000.0)
    if 0.0 < raw_value < 1.0:
        return float(raw_value * 1_000_000.0)
    return float(raw_value)


def _relative_close(actual: float, expected: float, tolerance: float) -> bool:
    if expected == 0.0:
        return abs(actual) <= 1e-6
    return abs(actual - expected) / max(abs(expected), 1e-9) <= tolerance


def apply_controls(
    capture: cv2.VideoCapture,
    pixfmt: str,
    exposure_us: int,
    gain: float,
    wb_mode: Optional[str],
    wb: Optional[int],
) -> dict[str, Any]:
    """Write requested controls and retain write/provenance evidence."""
    requested = {
        "exposure_us": exposure_us,
        "gain": gain,
        "wb_mode": wb_mode,
        "wb": wb,
    }
    auto_exposure_set = _safe_set(capture, cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
    exposure_set = False
    if exposure_us > 0:
        backend_exposure = math.log2(float(exposure_us) / 1_000_000.0)
        exposure_set = _safe_set(capture, cv2.CAP_PROP_EXPOSURE, backend_exposure)
    gain_set = _safe_set(capture, cv2.CAP_PROP_GAIN, gain)

    color_capture = str(pixfmt).upper() != "GRAY8"
    resolved_wb: float | int | None = wb
    wb_source = "configured" if wb is not None else "not_applicable"
    auto_wb_sampled = False
    if color_capture and wb is None:
        auto_wb_raw = _safe_get(capture, cv2.CAP_PROP_AUTO_WB)
        if auto_wb_raw is not None and abs(auto_wb_raw) <= 0.1:
            _safe_set(capture, cv2.CAP_PROP_AUTO_WB, 1)
            auto_wb_raw = _safe_get(capture, cv2.CAP_PROP_AUTO_WB)
        if auto_wb_raw is not None and abs(auto_wb_raw) > 0.1:
            sampled_wb = _safe_get(capture, cv2.CAP_PROP_WB_TEMPERATURE)
            if sampled_wb is not None and sampled_wb > 0:
                resolved_wb = sampled_wb
                wb_source = "auto_sampled_then_locked"
                auto_wb_sampled = True
            else:
                wb_source = "auto_sample_unavailable"

    wb_set = not color_capture
    auto_wb_set = False
    if wb_mode is None:
        auto_wb_set = _safe_set(capture, cv2.CAP_PROP_AUTO_WB, 0)
        if resolved_wb is not None:
            wb_set = _safe_set(capture, cv2.CAP_PROP_WB_TEMPERATURE, float(resolved_wb))

    return {
        "requested": requested,
        "auto_exposure_set": auto_exposure_set,
        "exposure_set": exposure_set,
        "gain_set": gain_set,
        "auto_wb_set": auto_wb_set,
        "wb_set": bool(wb_set),
        "resolved_wb": resolved_wb,
        "wb_source": wb_source,
        "auto_wb_sampled_while_enabled": auto_wb_sampled,
        "autofocus_set": _safe_set(capture, cv2.CAP_PROP_AUTOFOCUS, 0),
    }


def read_controls(
    capture: cv2.VideoCapture,
    pixfmt: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Read controls back and distinguish requested values from observations."""
    requested = dict(state.get("requested", {}))
    exposure_raw = _safe_get(capture, cv2.CAP_PROP_EXPOSURE)
    exposure_readback_us = (
        None if exposure_raw is None else _directshow_exposure_us(exposure_raw)
    )
    gain_readback = _safe_get(capture, cv2.CAP_PROP_GAIN)
    wb_readback = _safe_get(capture, cv2.CAP_PROP_WB_TEMPERATURE)
    auto_exposure_raw = _safe_get(capture, cv2.CAP_PROP_AUTO_EXPOSURE)
    auto_wb_raw = _safe_get(capture, cv2.CAP_PROP_AUTO_WB)
    autofocus_raw = _safe_get(capture, cv2.CAP_PROP_AUTOFOCUS)
    auto_exposure_disabled = (
        auto_exposure_raw is not None
        and bool(state.get("auto_exposure_set"))
        and (
            abs(auto_exposure_raw - 0.25) <= 0.1
            or abs(auto_exposure_raw) <= 0.1
        )
    )
    auto_wb_disabled = auto_wb_raw is not None and abs(auto_wb_raw) <= 0.1
    autofocus_disabled = autofocus_raw is not None and abs(autofocus_raw) <= 0.1
    exposure_ok = exposure_readback_us is not None and bool(state.get("exposure_set")) and _relative_close(
        exposure_readback_us, float(requested.get("exposure_us") or 0.0), 0.25
    )
    gain_ok = gain_readback is not None and bool(state.get("gain_set")) and _relative_close(
        gain_readback,
        float(requested.get("gain") or 0.0),
        0.15,
    )
    requested_wb = state.get("resolved_wb", requested.get("wb"))
    wb_source = str(
        state.get(
            "wb_source",
            "configured" if requested_wb is not None else "not_applicable",
        )
    )
    color_capture = str(pixfmt).upper() != "GRAY8"
    wb_ok = (requested_wb is None and not color_capture) or (
        requested_wb is not None
        and wb_readback is not None
        and auto_wb_disabled
        and bool(state.get("wb_set"))
        and _relative_close(wb_readback, float(requested_wb), 0.1)
    )
    readback_verified = all(
        (
            auto_exposure_disabled,
            auto_wb_disabled,
            autofocus_disabled,
            exposure_ok,
            gain_ok,
            wb_ok,
        )
    )
    return {
        **requested,
        "exposure_backend_raw": exposure_raw,
        "exposure_readback_us": exposure_readback_us,
        "actual_exposure_us": exposure_readback_us,
        "gain_readback": gain_readback,
        "actual_gain": gain_readback,
        "wb_readback": wb_readback,
        "actual_wb": wb_readback if requested_wb is not None else None,
        "resolved_wb": requested_wb,
        "wb_source": wb_source,
        "auto_wb_sampled_while_enabled": bool(state.get("auto_wb_sampled_while_enabled")),
        "auto_exposure_readback_raw": auto_exposure_raw,
        "auto_white_balance_readback_raw": auto_wb_raw,
        "autofocus_readback_raw": autofocus_raw,
        "auto_exposure_disabled": auto_exposure_disabled,
        "auto_white_balance_disabled": auto_wb_disabled,
        "autofocus_disable_write_succeeded": bool(state.get("autofocus_set")),
        "autofocus_disabled": autofocus_disabled,
        "exposure_readback_verified": exposure_ok,
        "gain_readback_verified": gain_ok,
        "color_white_balance_verified": wb_ok if color_capture else None,
        "readback_verified": readback_verified,
        "readback_note": (
            "Verified using DirectShow log2(seconds) exposure semantics."
            if readback_verified
            else "Control write/readback mismatch; measurement setup must remain blocked."
        ),
    }

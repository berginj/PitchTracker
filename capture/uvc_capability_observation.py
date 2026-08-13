"""Build typed capability observations from UVC DirectShow readback values.

Extracted from ``uvc_backend.py`` so the grandfathered backend file does not
grow. All functions accept raw readback dicts/scalars — no circular imports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from contracts.capability_observation import (
    CONTROL_EXPOSURE,
    CONTROL_FPS,
    CONTROL_FOCUS,
    CONTROL_GAIN,
    CONTROL_PIXEL_FORMAT,
    CONTROL_RESOLUTION,
    CONTROL_WHITE_BALANCE,
    CapabilityObservation,
    ControlQueryResult,
    ControlQueryStatus,
)


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _readback_result(
    control: str,
    observed: Any,
    requested: Any,
    backend: str,
    timestamp_utc: str,
    *,
    attempted: bool = True,
    reason: str = "",
) -> ControlQueryResult:
    """Build a ControlQueryResult with correct status semantics.

    * ``attempted=True`` and ``observed is not None`` → SUPPORTED.
    * ``attempted=True`` and ``observed is None``   → QUERY_FAILED
      (the backend tried to read the control but got nothing back).
    * ``attempted=False`` → UNAVAILABLE (query was never attempted /
      not applicable for this backend or pixel format).
    """
    if not attempted:
        status = ControlQueryStatus.UNAVAILABLE
    elif observed is None:
        status = ControlQueryStatus.QUERY_FAILED
    else:
        status = ControlQueryStatus.SUPPORTED
    return ControlQueryResult(
        control=control,
        status=status,
        observed_value=observed,
        requested_value=requested,
        backend=backend,
        reason=reason,
        timestamp_utc=timestamp_utc,
    )


def _focus_result(
    controls: Dict[str, Any],
    timestamp_utc: str,
) -> ControlQueryResult:
    """Classify focus/autofocus control status from DirectShow readback.

    * Write succeeded **and** readback confirms disabled → SUPPORTED
      (the device has a focus control and we successfully commanded it).
    * Write attempted but readback does not confirm → QUERY_FAILED
      (control may exist but we could not verify its state).
    * Write explicitly failed (False) → QUERY_FAILED.
    * Key absent / None (never attempted) → UNAVAILABLE.
    """
    write_key = controls.get("autofocus_disable_write_succeeded")
    readback_disabled = controls.get("autofocus_disabled") is True

    if write_key is None:
        status = ControlQueryStatus.UNAVAILABLE
        reason = "Autofocus disable was never attempted."
    elif write_key and readback_disabled:
        status = ControlQueryStatus.SUPPORTED
        reason = "Autofocus disable write and readback verified."
    elif write_key and not readback_disabled:
        status = ControlQueryStatus.QUERY_FAILED
        reason = "Autofocus disable write reported success but readback did not confirm."
    else:
        status = ControlQueryStatus.QUERY_FAILED
        reason = "Autofocus disable write did not succeed."

    return ControlQueryResult(
        control=CONTROL_FOCUS,
        status=status,
        observed_value=controls.get("autofocus_readback_raw"),
        backend="uvc",
        reason=reason,
        timestamp_utc=timestamp_utc,
    )


def _white_balance_result(
    controls: Dict[str, Any],
    timestamp_utc: str,
) -> ControlQueryResult:
    """Classify white-balance status from DirectShow readback.

    * ``color_white_balance_verified is True`` → SUPPORTED.
    * ``color_white_balance_verified is False`` → QUERY_FAILED
      (control was attempted but readback mismatch).
    * ``color_white_balance_verified is None`` (grayscale) → UNAVAILABLE.
    """
    wb_verified = controls.get("color_white_balance_verified")
    wb_observed = controls.get("wb_readback")

    if wb_verified is True:
        status = ControlQueryStatus.SUPPORTED
    elif wb_verified is False:
        status = ControlQueryStatus.QUERY_FAILED
    else:
        status = ControlQueryStatus.UNAVAILABLE

    return ControlQueryResult(
        control=CONTROL_WHITE_BALANCE,
        status=status,
        observed_value=wb_observed,
        requested_value=controls.get("wb"),
        backend="uvc",
        reason=controls.get("wb_source", ""),
        timestamp_utc=timestamp_utc,
    )


def build_uvc_observation(
    *,
    serial: str,
    requested_width: int,
    requested_height: int,
    requested_fps: int,
    requested_pixfmt: str,
    mode: Dict[str, Any],
    controls: Dict[str, Any],
) -> CapabilityObservation:
    """Assemble a ``CapabilityObservation`` from raw UVC readback dicts.

    This function is intentionally decoupled from the ``UvcCamera`` class
    so it can live in its own module and avoid growing ``uvc_backend.py``.
    """
    now = _utc_now_iso()
    results: Dict[str, ControlQueryResult] = {}

    results[CONTROL_RESOLUTION] = _readback_result(
        CONTROL_RESOLUTION,
        f"{mode.get('width')}x{mode.get('height')}",
        f"{requested_width}x{requested_height}",
        "uvc", now,
    )
    results[CONTROL_FPS] = _readback_result(
        CONTROL_FPS, mode.get("fps"), requested_fps, "uvc", now,
    )
    results[CONTROL_PIXEL_FORMAT] = _readback_result(
        CONTROL_PIXEL_FORMAT, mode.get("pixfmt"), requested_pixfmt, "uvc", now,
    )
    results[CONTROL_EXPOSURE] = _readback_result(
        CONTROL_EXPOSURE,
        controls.get("exposure_readback_us"),
        controls.get("exposure_us"),
        "uvc", now,
    )
    results[CONTROL_GAIN] = _readback_result(
        CONTROL_GAIN,
        controls.get("gain_readback"),
        controls.get("gain"),
        "uvc", now,
    )
    results[CONTROL_FOCUS] = _focus_result(controls, now)
    results[CONTROL_WHITE_BALANCE] = _white_balance_result(controls, now)

    return CapabilityObservation(
        camera_id=serial,
        backend="uvc",
        results=results,
        requested_mode={
            "width": requested_width,
            "height": requested_height,
            "fps": requested_fps,
            "pixfmt": requested_pixfmt,
        },
        negotiated_mode=dict(mode),
        provenance_note="DirectShow UVC backend readback.",
    )

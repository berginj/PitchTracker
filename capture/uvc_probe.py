"""Conservative UVC capability probing and native/fallback composition."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import os
from types import MappingProxyType
from typing import Any, Mapping, Protocol

import cv2

from contracts.capability_observation import (
    ALL_CONTROLS,
    CONTROL_EXPOSURE,
    CONTROL_FOCUS,
    CONTROL_FPS,
    CONTROL_GAIN,
    CONTROL_PIXEL_FORMAT,
    CONTROL_RESOLUTION,
    CONTROL_WHITE_BALANCE,
    CapabilityObservation,
    ControlQueryResult,
    ControlQueryStatus,
)

PROBE_VERSION = "uvc-probe-v1"
_CONCLUSIVE_NATIVE = {
    ControlQueryStatus.SUPPORTED,
    ControlQueryStatus.UNSUPPORTED,
    ControlQueryStatus.PERMISSION_DENIED,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ProbeEvidence:
    """Provider-specific evidence before it is composed into the contract."""

    provider: str
    results: Mapping[str, ControlQueryResult] = field(default_factory=dict)
    supported_modes: tuple[Mapping[str, Any], ...] = ()
    device_metadata: Mapping[str, Any] = field(default_factory=dict)
    note: str = ""
    version: str = PROBE_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", MappingProxyType(dict(self.results)))
        object.__setattr__(
            self,
            "supported_modes",
            tuple(MappingProxyType(dict(mode)) for mode in self.supported_modes),
        )
        object.__setattr__(self, "device_metadata", MappingProxyType(dict(self.device_metadata)))


class UvcCapabilityProbe(Protocol):
    """Optional native probe boundary used before OpenCV owns the device."""

    def probe(self, *, camera_id: str, device_index: int, friendly_name: str) -> ProbeEvidence: ...


@dataclass(frozen=True)
class _PropertyRead:
    status: ControlQueryStatus
    value: float | None = None
    reason: str = ""
    error_code: str = ""


def _error_code(exc: BaseException) -> str:
    value = getattr(exc, "winerror", None)
    if value is None:
        value = getattr(exc, "hresult", None)
    return "" if value is None else str(value)


def _property_read(capture: Any, prop: int) -> _PropertyRead:
    try:
        value = float(capture.get(prop))
    except PermissionError as exc:
        return _PropertyRead(
            ControlQueryStatus.PERMISSION_DENIED,
            reason=str(exc) or "Camera property access was denied.",
            error_code=_error_code(exc),
        )
    except OSError as exc:
        status = (
            ControlQueryStatus.PERMISSION_DENIED
            if getattr(exc, "winerror", None) == 5
            else ControlQueryStatus.QUERY_FAILED
        )
        return _PropertyRead(status, reason=str(exc), error_code=_error_code(exc))
    except Exception as exc:  # noqa: BLE001 - backend errors become typed evidence
        return _PropertyRead(
            ControlQueryStatus.QUERY_FAILED,
            reason=str(exc) or type(exc).__name__,
            error_code=_error_code(exc),
        )
    if not math.isfinite(value):
        return _PropertyRead(
            ControlQueryStatus.QUERY_FAILED,
            reason="Backend returned a non-finite value.",
            error_code="NON_FINITE",
        )
    return _PropertyRead(ControlQueryStatus.SUPPORTED, value=value)


def _result_from_read(
    control: str,
    read: _PropertyRead,
    *,
    observed: Any = None,
    requested: Any = None,
    verified: bool = False,
    reason: str = "",
) -> ControlQueryResult:
    status = read.status
    final_reason = read.reason or reason
    if status == ControlQueryStatus.SUPPORTED and not verified:
        status = ControlQueryStatus.QUERY_FAILED
        final_reason = reason or "Readback did not verify the requested state."
    return ControlQueryResult(
        control=control,
        status=status,
        observed_value=read.value if observed is None else observed,
        requested_value=requested,
        backend="uvc",
        reason=final_reason,
        timestamp_utc=_utc_now_iso(),
        query_method="opencv_directshow_readback",
        error_code=read.error_code,
    )


def _relative_close(actual: float, expected: float, tolerance: float) -> bool:
    if expected == 0.0:
        return abs(actual) <= 1e-6
    return abs(actual - expected) / max(abs(expected), 1e-9) <= tolerance


def _exposure_us(raw: float) -> float:
    if raw < 0:
        return float((2.0**raw) * 1_000_000.0)
    if 0.0 < raw < 1.0:
        return float(raw * 1_000_000.0)
    return float(raw)


def _fourcc(raw: float) -> str:
    value = int(raw)
    if value <= 0:
        return ""
    text = "".join(chr((value >> (8 * index)) & 0xFF) for index in range(4)).rstrip("\x00")
    return text if len(text) == 4 and all(32 <= ord(char) <= 126 for char in text) else ""


class OpenCvDirectShowProbe:
    """Fallback probe that treats OpenCV results as evidence only after validation."""

    def probe(
        self,
        *,
        capture: Any,
        requested_mode: Mapping[str, Any],
        control_state: Mapping[str, Any],
    ) -> ProbeEvidence:
        timestamp = _utc_now_iso()
        requested = dict(control_state.get("requested", {}))
        width = _property_read(capture, cv2.CAP_PROP_FRAME_WIDTH)
        height = _property_read(capture, cv2.CAP_PROP_FRAME_HEIGHT)
        fps = _property_read(capture, cv2.CAP_PROP_FPS)
        fourcc = _property_read(capture, cv2.CAP_PROP_FOURCC)
        exposure = _property_read(capture, cv2.CAP_PROP_EXPOSURE)
        gain = _property_read(capture, cv2.CAP_PROP_GAIN)
        autofocus = _property_read(capture, cv2.CAP_PROP_AUTOFOCUS)
        wb = _property_read(capture, cv2.CAP_PROP_WB_TEMPERATURE)

        actual_width = int(width.value or 0)
        actual_height = int(height.value or 0)
        actual_fps = float(fps.value or 0.0)
        pixfmt = _fourcc(fourcc.value or 0.0)
        requested_exposure = float(requested.get("exposure_us") or 0.0)
        actual_exposure = _exposure_us(float(exposure.value or 0.0))
        requested_gain = float(requested.get("gain") or 0.0)
        actual_gain = float(gain.value or 0.0)
        color_capture = str(requested_mode.get("pixfmt", "")).upper() != "GRAY8"
        requested_wb = control_state.get("resolved_wb", requested.get("wb"))

        mode_reads_ok = width.status.is_observed() and height.status.is_observed()
        results = {
            CONTROL_RESOLUTION: _result_from_read(
                CONTROL_RESOLUTION,
                width if width.status != ControlQueryStatus.SUPPORTED else height,
                observed=f"{actual_width}x{actual_height}",
                requested=f"{requested_mode.get('width')}x{requested_mode.get('height')}",
                verified=mode_reads_ok and actual_width > 0 and actual_height > 0,
                reason="Width/height readback was missing or invalid.",
            ),
            CONTROL_FPS: _result_from_read(
                CONTROL_FPS,
                fps,
                requested=requested_mode.get("fps"),
                verified=actual_fps > 0,
                reason="FPS readback was zero or invalid.",
            ),
            CONTROL_PIXEL_FORMAT: _result_from_read(
                CONTROL_PIXEL_FORMAT,
                fourcc,
                observed=pixfmt or None,
                requested=requested_mode.get("pixfmt"),
                verified=bool(pixfmt),
                reason="Pixel-format readback was empty or invalid.",
            ),
            CONTROL_EXPOSURE: _result_from_read(
                CONTROL_EXPOSURE,
                exposure,
                observed=actual_exposure,
                requested=requested_exposure,
                verified=bool(control_state.get("exposure_set"))
                and _relative_close(actual_exposure, requested_exposure, 0.25),
                reason="Exposure write/readback was not verified.",
            ),
            CONTROL_GAIN: _result_from_read(
                CONTROL_GAIN,
                gain,
                observed=actual_gain,
                requested=requested_gain,
                verified=bool(control_state.get("gain_set"))
                and _relative_close(actual_gain, requested_gain, 0.15),
                reason="Gain write/readback was not verified.",
            ),
            CONTROL_FOCUS: _result_from_read(
                CONTROL_FOCUS,
                autofocus,
                requested=0,
                verified=bool(control_state.get("autofocus_set"))
                and autofocus.value is not None
                and abs(autofocus.value) <= 0.1,
                reason="Autofocus-disable write/readback was not verified.",
            ),
            CONTROL_WHITE_BALANCE: _result_from_read(
                CONTROL_WHITE_BALANCE,
                wb,
                requested=requested_wb,
                verified=(
                    not color_capture
                    or (
                        requested_wb is not None
                        and bool(control_state.get("wb_set"))
                        and wb.value is not None
                        and wb.value > 0
                        and _relative_close(wb.value, float(requested_wb), 0.1)
                    )
                ),
                reason=(
                    "White balance is not applicable to grayscale capture."
                    if not color_capture
                    else "White-balance write/readback was not verified."
                ),
            ),
        }
        if not color_capture:
            results[CONTROL_WHITE_BALANCE] = ControlQueryResult(
                control=CONTROL_WHITE_BALANCE,
                status=ControlQueryStatus.UNAVAILABLE,
                backend="uvc",
                reason="White balance is not applicable to grayscale capture.",
                timestamp_utc=timestamp,
                query_method="opencv_directshow_readback",
            )
        return ProbeEvidence(
            provider="opencv_directshow",
            results=results,
            note="OpenCV DirectShow properties; support requires validated readback.",
        )


def unavailable_native_evidence(reason: str, error_code: str = "") -> ProbeEvidence:
    metadata: dict[str, Any] = {"native_probe_available": False}
    if error_code:
        metadata["native_probe_error_code"] = error_code
    return ProbeEvidence(provider="native_directshow", device_metadata=metadata, note=reason)


def load_native_probe() -> UvcCapabilityProbe | None:
    """Load the optional Windows DirectShow provider without making it mandatory."""
    if os.environ.get("PITCHTRACKER_UVC_NATIVE_PROBE", "auto").lower() in {"0", "false", "off"}:
        return None
    try:
        from capture.uvc_native_directshow import NativeDirectShowProbe
    except (ImportError, OSError):
        return None
    return NativeDirectShowProbe()


def compose_observation(
    *,
    camera_id: str,
    friendly_name: str,
    device_index: int,
    requested_mode: Mapping[str, Any],
    fallback: ProbeEvidence,
    native: ProbeEvidence | None,
    device_metadata: Mapping[str, Any] | None = None,
) -> CapabilityObservation:
    """Compose native and fallback facts without turning guesses into support."""
    native_results = {} if native is None else dict(native.results)
    results: dict[str, ControlQueryResult] = {}
    for control in ALL_CONTROLS:
        native_result = native_results.get(control)
        fallback_result = fallback.results.get(control)
        if native_result is not None and native_result.status in _CONCLUSIVE_NATIVE:
            results[control] = native_result
        elif fallback_result is not None and fallback_result.status == ControlQueryStatus.SUPPORTED:
            results[control] = fallback_result
        elif native_result is not None:
            results[control] = native_result
        elif fallback_result is not None:
            results[control] = fallback_result
        else:
            results[control] = ControlQueryResult(
                control=control,
                status=ControlQueryStatus.UNAVAILABLE,
                backend="uvc",
                reason="No capability provider returned evidence.",
                timestamp_utc=_utc_now_iso(),
                query_method="composite",
            )

    resolution = results[CONTROL_RESOLUTION].observed_value
    width, height = 0, 0
    if isinstance(resolution, str) and "x" in resolution:
        left, _, right = resolution.partition("x")
        if left.isdigit() and right.isdigit():
            width, height = int(left), int(right)
    negotiated_mode = {
        "width": width,
        "height": height,
        "fps": results[CONTROL_FPS].observed_value,
        "pixfmt": results[CONTROL_PIXEL_FORMAT].observed_value,
    }
    metadata = {
        "friendly_name": friendly_name,
        "directshow_index": device_index,
        "native_probe_available": native is not None,
        **dict(device_metadata or {}),
        **({} if native is None else dict(native.device_metadata)),
    }
    notes = [fallback.note]
    if native is None:
        notes.append("Optional native DirectShow probe was not installed.")
    elif native.note:
        notes.append(native.note)
    return CapabilityObservation(
        camera_id=camera_id,
        backend="uvc",
        results=results,
        requested_mode=dict(requested_mode),
        negotiated_mode=negotiated_mode,
        provenance_note=" ".join(note for note in notes if note),
        supported_modes=() if native is None else native.supported_modes,
        probe_version=PROBE_VERSION,
        device_metadata=metadata,
    )

"""Optional native DirectShow capability provider for Windows UVC devices.

The module is imported only when the optional ``comtypes``/``pygrabber``
dependencies are present. It queries controls and stream capabilities without
changing device state.
"""

from __future__ import annotations

from ctypes import HRESULT, POINTER, c_long
import importlib
from typing import Any

from comtypes import (  # type: ignore[import-untyped]
    COMMETHOD,
    GUID,
    COMError,
    IUnknown,
)

from contracts.capability_observation import (
    CONTROL_EXPOSURE,
    CONTROL_FOCUS,
    CONTROL_GAIN,
    CONTROL_WHITE_BALANCE,
    ControlQueryResult,
    ControlQueryStatus,
)
from capture.uvc_probe import PROBE_VERSION, ProbeEvidence, _utc_now_iso

_E_NOINTERFACE = 0x80004002
_E_ACCESSDENIED = 0x80070005
_E_INVALIDARG = 0x80070057
_ERROR_NOT_FOUND = 0x80070490


class _IAMCameraControl(IUnknown):
    _iid_ = GUID("{C6E13370-30AC-11D0-A18C-00A0C9118956}")


_IAMCameraControl._methods_ = [
    COMMETHOD(
        [],
        HRESULT,
        "GetRange",
        (["in"], c_long, "Property"),
        (["out"], POINTER(c_long), "pMin"),
        (["out"], POINTER(c_long), "pMax"),
        (["out"], POINTER(c_long), "pSteppingDelta"),
        (["out"], POINTER(c_long), "pDefault"),
        (["out"], POINTER(c_long), "pCapsFlags"),
    ),
    COMMETHOD(
        [],
        HRESULT,
        "Set",
        (["in"], c_long, "Property"),
        (["in"], c_long, "lValue"),
        (["in"], c_long, "Flags"),
    ),
    COMMETHOD(
        [],
        HRESULT,
        "Get",
        (["in"], c_long, "Property"),
        (["out"], POINTER(c_long), "lValue"),
        (["out"], POINTER(c_long), "Flags"),
    ),
]


class _IAMVideoProcAmp(IUnknown):
    _iid_ = GUID("{C6E13360-30AC-11D0-A18C-00A0C9118956}")


_IAMVideoProcAmp._methods_ = list(_IAMCameraControl._methods_)

_CAMERA_CONTROL_EXPOSURE = 4
_CAMERA_CONTROL_FOCUS = 6
_VIDEO_PROC_AMP_WHITE_BALANCE = 7
_VIDEO_PROC_AMP_GAIN = 9


def _hresult(exc: BaseException) -> int | None:
    value = getattr(exc, "hresult", None)
    return None if value is None else int(value) & 0xFFFFFFFF


def _failure_status(exc: BaseException) -> ControlQueryStatus:
    code = _hresult(exc)
    if code == _E_ACCESSDENIED:
        return ControlQueryStatus.PERMISSION_DENIED
    if code in {_E_NOINTERFACE, _E_INVALIDARG, _ERROR_NOT_FOUND}:
        return ControlQueryStatus.UNSUPPORTED
    return ControlQueryStatus.QUERY_FAILED


def _error_code(exc: BaseException) -> str:
    value = _hresult(exc)
    return "" if value is None else f"0x{value:08X}"


def _query_property(
    interface: Any,
    property_id: int,
    control: str,
    method: str,
) -> ControlQueryResult:
    try:
        minimum, maximum, step, default, caps = interface.GetRange(property_id)
        current, flags = interface.Get(property_id)
    except COMError as exc:
        return ControlQueryResult(
            control=control,
            status=_failure_status(exc),
            backend="uvc",
            reason=str(exc),
            timestamp_utc=_utc_now_iso(),
            query_method=method,
            error_code=_error_code(exc),
        )
    return ControlQueryResult(
        control=control,
        status=ControlQueryStatus.SUPPORTED,
        observed_value={
            "current": int(current),
            "minimum": int(minimum),
            "maximum": int(maximum),
            "step": int(step),
            "default": int(default),
            "caps_flags": int(caps),
            "current_flags": int(flags),
        },
        backend="uvc",
        reason="DirectShow control range and current value queried without mutation.",
        timestamp_utc=_utc_now_iso(),
        query_method=method,
    )


def _query_interface_controls(
    device_filter: Any,
    interface_type: type[Any],
    properties: tuple[tuple[int, str], ...],
    method: str,
) -> dict[str, ControlQueryResult]:
    try:
        interface = device_filter.QueryInterface(interface_type)
    except COMError as exc:
        status = _failure_status(exc)
        return {
            control: ControlQueryResult(
                control=control,
                status=status,
                backend="uvc",
                reason=str(exc),
                timestamp_utc=_utc_now_iso(),
                query_method=method,
                error_code=_error_code(exc),
            )
            for _, control in properties
        }
    return {
        control: _query_property(interface, property_id, control, method)
        for property_id, control in properties
    }


def _normalize_modes(raw_modes: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    modes: list[dict[str, Any]] = []
    for raw in raw_modes:
        width = int(raw.get("width") or 0)
        height = abs(int(raw.get("height") or 0))
        first_fps = float(raw.get("min_framerate") or 0.0)
        second_fps = float(raw.get("max_framerate") or 0.0)
        if width <= 0 or height <= 0 or max(first_fps, second_fps) <= 0:
            continue
        modes.append(
            {
                "width": width,
                "height": height,
                "fps_min": min(first_fps, second_fps),
                "fps_max": max(first_fps, second_fps),
                "pixfmt": str(raw.get("media_type_str") or "UNKNOWN"),
            }
        )
    return tuple(
        sorted(
            modes,
            key=lambda mode: (
                int(mode["width"]),
                int(mode["height"]),
                float(mode["fps_max"]),
                str(mode["pixfmt"]),
            ),
        )
    )


class NativeDirectShowProbe:
    """Query IAMCameraControl/IAMVideoProcAmp/IAMStreamConfig via pygrabber."""

    def probe(self, *, camera_id: str, device_index: int, friendly_name: str) -> ProbeEvidence:
        graph_type = getattr(importlib.import_module("pygrabber.dshow_graph"), "FilterGraph")
        graph: Any = None
        try:
            graph = graph_type()
            names = [str(name) for name in graph.get_input_devices()]
            resolved_index = self._resolve_index(names, device_index, friendly_name)
            graph.add_video_input_device(resolved_index)
            video_input = graph.get_input_device()
            results = {
                **_query_interface_controls(
                    video_input.instance,
                    _IAMCameraControl,
                    (
                        (_CAMERA_CONTROL_EXPOSURE, CONTROL_EXPOSURE),
                        (_CAMERA_CONTROL_FOCUS, CONTROL_FOCUS),
                    ),
                    "directshow_iam_camera_control",
                ),
                **_query_interface_controls(
                    video_input.instance,
                    _IAMVideoProcAmp,
                    (
                        (_VIDEO_PROC_AMP_GAIN, CONTROL_GAIN),
                        (_VIDEO_PROC_AMP_WHITE_BALANCE, CONTROL_WHITE_BALANCE),
                    ),
                    "directshow_iam_video_proc_amp",
                ),
            }
            try:
                modes = _normalize_modes(video_input.get_formats())
                mode_note = "IAMStreamConfig stream capabilities enumerated."
            except COMError as exc:
                modes = ()
                mode_note = f"IAMStreamConfig query failed: {exc}"
            return ProbeEvidence(
                provider="native_directshow",
                results=results,
                supported_modes=modes,
                device_metadata={
                    "native_probe_available": True,
                    "native_provider": "comtypes_pygrabber",
                    "directshow_name": names[resolved_index],
                    "directshow_index": resolved_index,
                    "camera_id": camera_id,
                },
                note=mode_note,
                version=PROBE_VERSION,
            )
        finally:
            if graph is not None:
                try:
                    graph.remove_filters()
                except Exception:  # noqa: BLE001 - best-effort COM cleanup
                    pass

    @staticmethod
    def _resolve_index(names: list[str], device_index: int, friendly_name: str) -> int:
        if 0 <= device_index < len(names):
            if not friendly_name or names[device_index].casefold() == friendly_name.casefold():
                return device_index
        matches = [
            index for index, name in enumerate(names)
            if friendly_name and name.casefold() == friendly_name.casefold()
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError(
                f"DirectShow device name is ambiguous ({friendly_name!r}); "
                "native evidence was not attached to either device."
            )
        raise RuntimeError(
            f"DirectShow device {friendly_name!r} at index {device_index} was not found."
        )

from __future__ import annotations

import sys
from types import ModuleType

import pytest

pytest.importorskip("comtypes")
pytest.importorskip("pygrabber")

from comtypes import COMError  # type: ignore[import-untyped]  # noqa: E402

from capture.uvc_native_directshow import (  # noqa: E402
    NativeDirectShowProbe,
    _E_ACCESSDENIED,
    _E_NOINTERFACE,
    _failure_status,
)
from contracts.capability_observation import (  # noqa: E402
    CONTROL_EXPOSURE,
    CONTROL_FOCUS,
    CONTROL_GAIN,
    CONTROL_WHITE_BALANCE,
    ControlQueryStatus,
)


class _Interface:
    def GetRange(self, _property_id: int) -> tuple[int, int, int, int, int]:
        return 0, 100, 1, 50, 3

    def Get(self, _property_id: int) -> tuple[int, int]:
        return 25, 2


class _Filter:
    def QueryInterface(self, _interface_type: object) -> _Interface:
        return _Interface()


class _VideoInput:
    instance = _Filter()

    def get_formats(self) -> list[dict[str, object]]:
        return [
            {
                "width": 1280,
                "height": 720,
                "min_framerate": 60.0,
                "max_framerate": 30.0,
                "media_type_str": "MJPG",
            }
        ]


class _Graph:
    removed = False

    def get_input_devices(self) -> list[str]:
        return ["Camera A"]

    def add_video_input_device(self, index: int) -> None:
        assert index == 0

    def get_input_device(self) -> _VideoInput:
        return _VideoInput()

    def remove_filters(self) -> None:
        self.removed = True


def _install_fake_graph(monkeypatch: pytest.MonkeyPatch, graph_type: type[_Graph]) -> None:
    module = ModuleType("pygrabber.dshow_graph")
    setattr(module, "FilterGraph", graph_type)
    monkeypatch.setitem(sys.modules, "pygrabber.dshow_graph", module)


def test_native_probe_queries_controls_and_stream_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_graph(monkeypatch, _Graph)

    evidence = NativeDirectShowProbe().probe(
        camera_id="serial-1",
        device_index=0,
        friendly_name="Camera A",
    )

    assert set(evidence.results) == {
        CONTROL_EXPOSURE,
        CONTROL_FOCUS,
        CONTROL_GAIN,
        CONTROL_WHITE_BALANCE,
    }
    assert all(result.status == ControlQueryStatus.SUPPORTED for result in evidence.results.values())
    assert evidence.supported_modes[0]["fps_min"] == 30.0
    assert evidence.supported_modes[0]["fps_max"] == 60.0
    assert evidence.device_metadata["native_provider"] == "comtypes_pygrabber"


@pytest.mark.parametrize(
    ("hresult", "expected"),
    [
        (_E_ACCESSDENIED, ControlQueryStatus.PERMISSION_DENIED),
        (_E_NOINTERFACE, ControlQueryStatus.UNSUPPORTED),
        (0x80004005, ControlQueryStatus.QUERY_FAILED),
    ],
)
def test_native_hresult_mapping(hresult: int, expected: ControlQueryStatus) -> None:
    signed = hresult if hresult < 0x80000000 else hresult - 0x100000000
    error = COMError(signed, "probe failed", None)

    assert _failure_status(error) == expected


def test_native_probe_rejects_ambiguous_friendly_name(monkeypatch: pytest.MonkeyPatch) -> None:
    class AmbiguousGraph(_Graph):
        def get_input_devices(self) -> list[str]:
            return ["Other", "Camera A", "Camera A"]

    _install_fake_graph(monkeypatch, AmbiguousGraph)

    with pytest.raises(RuntimeError, match="ambiguous"):
        NativeDirectShowProbe().probe(
            camera_id="serial-1",
            device_index=0,
            friendly_name="Camera A",
        )

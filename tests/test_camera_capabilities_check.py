"""Characterization tests for the local camera capability CLI."""

from __future__ import annotations

import cv2

from tools import camera_capabilities_check as report
from tools import camera_capability_probes as probes


class _FakeCapture:
    def __init__(self, *, opened: bool = True, fail_on_set: bool = False) -> None:
        self.opened = opened
        self.fail_on_set = fail_on_set
        self.released = False
        self.values = {
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
            cv2.CAP_PROP_FPS: 30,
        }

    def isOpened(self) -> bool:
        return self.opened

    def set(self, prop: int, value: float) -> bool:
        if self.fail_on_set:
            raise OSError("mock set failure")
        self.values[prop] = value
        return True

    def get(self, prop: int) -> float:
        return float(self.values.get(prop, 0))

    def read(self):
        return True, object()

    def release(self) -> None:
        self.released = True

    def getBackendName(self) -> str:
        return "DSHOW"


def test_mode_probe_requires_negotiated_mode_and_releases(monkeypatch) -> None:
    capture = _FakeCapture()
    monkeypatch.setattr(probes, "TEST_MODES", ((640, 480, 30),))
    monkeypatch.setattr(probes.cv2, "VideoCapture", lambda *_: capture)

    supported = probes.test_camera_modes(0)

    assert supported == [(640, 480, 30)]
    assert capture.released is True


def test_mode_probe_releases_after_backend_error(monkeypatch) -> None:
    capture = _FakeCapture(fail_on_set=True)
    monkeypatch.setattr(probes, "TEST_MODES", ((640, 480, 30),))
    monkeypatch.setattr(probes.cv2, "VideoCapture", lambda *_: capture)

    supported = probes.test_camera_modes(0)

    assert supported == []
    assert capture.released is True


def test_enumeration_output_is_windows_ascii_safe(capsys) -> None:
    report.print_camera_enumeration(
        {
            0: {
                "available": True,
                "backend": "DSHOW",
                "manufacturer": "Vendor",
                "name": "ArduCam Global Shutter",
            },
            1: {
                "available": False,
                "backend": "Unknown",
                "name": "Camera 1",
            },
        }
    )

    output = capsys.readouterr().out
    output.encode("ascii")
    assert "Yes" in output
    assert "No" in output
    assert "Found 1 ArduCam device(s)" in output


def test_backend_report_skips_physical_tests_without_common_mode(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        report,
        "test_camera_modes",
        lambda index, *_args, **_kwargs: ([(640, 480, 30)] if index == 0 else [(1280, 720, 30)]),
    )
    monkeypatch.setattr(
        report,
        "test_memory_usage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("memory probe should not run")),
    )
    monkeypatch.setattr(
        report,
        "test_dual_camera",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dual probe should not run")),
    )
    lines: list[str] = []

    report._probe_backend(
        "DirectShow",
        cv2.CAP_DSHOW,
        {0: {"name": "Left"}, 1: {"name": "Right"}},
        lines,
    )

    assert any("Common Supported Modes (0):" in line for line in lines)

from __future__ import annotations

import math

import cv2

from capture.uvc_probe import OpenCvDirectShowProbe, ProbeEvidence, compose_observation
from contracts.capability_observation import (
    ALL_CONTROLS,
    CONTROL_EXPOSURE,
    CONTROL_FPS,
    CONTROL_GAIN,
    CONTROL_RESOLUTION,
    ControlQueryResult,
    ControlQueryStatus,
)


class _Capture:
    def __init__(self) -> None:
        self.values = {
            cv2.CAP_PROP_FRAME_WIDTH: 1280.0,
            cv2.CAP_PROP_FRAME_HEIGHT: 720.0,
            cv2.CAP_PROP_FPS: 60.0,
            cv2.CAP_PROP_FOURCC: float(int.from_bytes(b"MJPG", "little")),
            cv2.CAP_PROP_EXPOSURE: math.log2(0.002),
            cv2.CAP_PROP_GAIN: 2.0,
            cv2.CAP_PROP_AUTOFOCUS: 0.0,
            cv2.CAP_PROP_WB_TEMPERATURE: 4600.0,
        }

    def get(self, prop: int) -> float:
        return self.values[prop]


def _fallback(capture: _Capture | None = None) -> ProbeEvidence:
    return OpenCvDirectShowProbe().probe(
        capture=capture or _Capture(),
        requested_mode={"width": 1920, "height": 1080, "fps": 120, "pixfmt": "MJPG"},
        control_state={
            "requested": {"exposure_us": 2000, "gain": 2.0, "wb": 4600},
            "exposure_set": True,
            "gain_set": True,
            "autofocus_set": True,
            "wb_set": True,
            "resolved_wb": 4600,
        },
    )


def test_opencv_probe_requires_valid_verified_readback() -> None:
    evidence = _fallback()

    assert evidence.results[CONTROL_EXPOSURE].status == ControlQueryStatus.SUPPORTED
    assert evidence.results[CONTROL_GAIN].status == ControlQueryStatus.SUPPORTED
    assert evidence.results[CONTROL_FPS].status == ControlQueryStatus.SUPPORTED
    assert evidence.results[CONTROL_RESOLUTION].observed_value == "1280x720"


def test_opencv_zero_and_non_finite_mode_values_are_query_failures() -> None:
    capture = _Capture()
    capture.values[cv2.CAP_PROP_FPS] = 0.0
    capture.values[cv2.CAP_PROP_FRAME_WIDTH] = float("nan")

    evidence = _fallback(capture)

    assert evidence.results[CONTROL_FPS].status == ControlQueryStatus.QUERY_FAILED
    assert evidence.results[CONTROL_RESOLUTION].status == ControlQueryStatus.QUERY_FAILED


def test_opencv_permission_error_remains_distinct() -> None:
    class DeniedCapture(_Capture):
        def get(self, prop: int) -> float:
            if prop == cv2.CAP_PROP_GAIN:
                raise PermissionError("driver access denied")
            return super().get(prop)

    evidence = _fallback(DeniedCapture())

    assert evidence.results[CONTROL_GAIN].status == ControlQueryStatus.PERMISSION_DENIED
    assert "denied" in evidence.results[CONTROL_GAIN].reason


def test_composite_keeps_conclusive_native_result_and_fills_missing_results() -> None:
    native = ProbeEvidence(
        provider="native_directshow",
        results={
            CONTROL_GAIN: ControlQueryResult(
                CONTROL_GAIN,
                ControlQueryStatus.UNSUPPORTED,
                query_method="directshow_iam_video_proc_amp",
            ),
        },
        supported_modes=({"width": 1280, "height": 720, "fps_max": 60, "pixfmt": "MJPG"},),
        device_metadata={"native_probe_available": True},
    )

    observation = compose_observation(
        camera_id="camera-1",
        friendly_name="Camera",
        device_index=0,
        requested_mode={"width": 1920, "height": 1080, "fps": 120, "pixfmt": "MJPG"},
        fallback=_fallback(),
        native=native,
    )

    assert observation.results[CONTROL_GAIN].status == ControlQueryStatus.UNSUPPORTED
    assert observation.results[CONTROL_EXPOSURE].status == ControlQueryStatus.SUPPORTED
    assert observation.requested_mode["width"] == 1920
    assert observation.negotiated_mode["width"] == 1280
    assert len(observation.supported_modes) == 1
    assert set(observation.results) == set(ALL_CONTROLS)


def test_composite_uses_verified_fallback_after_native_query_failure() -> None:
    native = ProbeEvidence(
        provider="native_directshow",
        results={
            CONTROL_GAIN: ControlQueryResult(
                CONTROL_GAIN,
                ControlQueryStatus.QUERY_FAILED,
                reason="native query failed",
            ),
        },
    )

    observation = compose_observation(
        camera_id="camera-1",
        friendly_name="Camera",
        device_index=0,
        requested_mode={"width": 1920, "height": 1080, "fps": 120, "pixfmt": "MJPG"},
        fallback=_fallback(),
        native=native,
    )

    assert observation.results[CONTROL_GAIN].status == ControlQueryStatus.SUPPORTED
    assert observation.results[CONTROL_GAIN].query_method == "opencv_directshow_readback"

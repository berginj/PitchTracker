#!/usr/bin/env python3
"""Validated capture module for Arducam B0495 (AR0234) on Windows.

Primary backend: DirectShow (cv2.CAP_DSHOW), fallback: Media Foundation (cv2.CAP_MSMF).

Features:
- Enumerate camera indices
- Prefer validated device by probing supported modes (YUY2 + 1920x1200@50)
- Configure YUY2, resolution, FPS
- Log requested vs accepted settings
- Measure actual FPS
- Preview + graceful exit
- Save a 5-second AVI capture
- Basic UVC control APIs (exposure/gain/white balance)

Support Playbook is included at the bottom.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple

import cv2

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---------- Validated device capabilities ----------
VALIDATED_NAME_HINTS = ["Arducam", "B0495", "AR0234"]
FOURCC_YUY2 = getattr(cv2, "VideoWriter_fourcc")(*"YUY2")

USB3_MODES = [
    (1920, 1200, 50),
    (960, 600, 80),
]
USB2_FALLBACK = (960, 600, 10)


# ---------- OpenCV capture property helpers ----------
def _set_prop(cap: cv2.VideoCapture, prop: int, value: float) -> None:
    cap.set(prop, value)


def _get_prop(cap: cv2.VideoCapture, prop: int) -> float:
    return cap.get(prop)


def _fourcc_to_str(fourcc: float) -> str:
    i = int(fourcc)
    return "".join([chr((i >> 8 * k) & 0xFF) for k in range(4)])


@dataclass
class CaptureMode:
    width: int
    height: int
    fps: int


@dataclass
class CaptureResult:
    index: int
    backend: int
    mode: CaptureMode
    ok: bool
    reason: Optional[str] = None


# ---------- Device probing ----------
def probe_mode(cap: cv2.VideoCapture, mode: CaptureMode) -> bool:
    _set_prop(cap, cv2.CAP_PROP_FOURCC, FOURCC_YUY2)
    _set_prop(cap, cv2.CAP_PROP_FRAME_WIDTH, mode.width)
    _set_prop(cap, cv2.CAP_PROP_FRAME_HEIGHT, mode.height)
    _set_prop(cap, cv2.CAP_PROP_FPS, mode.fps)

    actual_w = _get_prop(cap, cv2.CAP_PROP_FRAME_WIDTH)
    actual_h = _get_prop(cap, cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps = _get_prop(cap, cv2.CAP_PROP_FPS)

    return (
        int(actual_w) == mode.width
        and int(actual_h) == mode.height
        and int(actual_fps) == mode.fps
    )


def enumerate_indices(max_index: int = 6, backend: int = cv2.CAP_DSHOW) -> List[int]:
    indices = []
    for idx in range(max_index + 1):
        cap = cv2.VideoCapture(idx, backend)
        if cap.isOpened():
            indices.append(idx)
            cap.release()
    return indices


def select_validated_camera(
    max_index: int = 6,
    backend: int = cv2.CAP_DSHOW,
) -> Optional[int]:
    indices = enumerate_indices(max_index, backend)
    if not indices:
        return None

    # Prefer by probing modes that only validated device should accept
    for idx in indices:
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            continue
        if probe_mode(cap, CaptureMode(*USB3_MODES[0])):
            cap.release()
            return idx
        cap.release()

    # Fallback: any open index
    return indices[0]


# ---------- Capture ----------
def open_with_backend(index: int, backend: int) -> Optional[cv2.VideoCapture]:
    cap = cv2.VideoCapture(index, backend)
    if cap.isOpened():
        return cap
    cap.release()
    return None


def configure_capture(cap: cv2.VideoCapture, mode: CaptureMode) -> None:
    _set_prop(cap, cv2.CAP_PROP_FOURCC, FOURCC_YUY2)
    _set_prop(cap, cv2.CAP_PROP_FRAME_WIDTH, mode.width)
    _set_prop(cap, cv2.CAP_PROP_FRAME_HEIGHT, mode.height)
    _set_prop(cap, cv2.CAP_PROP_FPS, mode.fps)


def get_actual_settings(cap: cv2.VideoCapture) -> Tuple[int, int, int, str]:
    width = int(_get_prop(cap, cv2.CAP_PROP_FRAME_WIDTH))
    height = int(_get_prop(cap, cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(_get_prop(cap, cv2.CAP_PROP_FPS))
    fourcc = _fourcc_to_str(_get_prop(cap, cv2.CAP_PROP_FOURCC))
    return width, height, fps, fourcc


def choose_mode(cap: cv2.VideoCapture) -> CaptureMode:
    for w, h, fps in USB3_MODES:
        mode = CaptureMode(w, h, fps)
        configure_capture(cap, mode)
        actual_w, actual_h, actual_fps, _ = get_actual_settings(cap)
        if actual_w == w and actual_h == h and actual_fps == fps:
            return mode

    # USB2 fallback
    w, h, fps = USB2_FALLBACK
    mode = CaptureMode(w, h, fps)
    configure_capture(cap, mode)
    return mode


def measure_fps(cap: cv2.VideoCapture, sample_sec: float = 2.0) -> float:
    start = time.perf_counter()
    frames = 0
    while time.perf_counter() - start < sample_sec:
        ret, _ = cap.read()
        if not ret:
            break
        frames += 1
    elapsed = time.perf_counter() - start
    return frames / elapsed if elapsed > 0 else 0.0


# ---------- UVC controls (best effort via OpenCV) ----------
def set_auto_exposure(cap: cv2.VideoCapture, enabled: bool) -> None:
    # OpenCV uses 1=manual, 3=auto for DirectShow; MSMF may differ.
    value = 3 if enabled else 1
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, value)


def set_exposure(cap: cv2.VideoCapture, exposure: float) -> None:
    # Exposure unit is backend-dependent (often log scale).
    cap.set(cv2.CAP_PROP_EXPOSURE, exposure)


def set_gain(cap: cv2.VideoCapture, gain: float) -> None:
    cap.set(cv2.CAP_PROP_GAIN, gain)


def set_auto_white_balance(cap: cv2.VideoCapture, enabled: bool) -> None:
    cap.set(cv2.CAP_PROP_AUTO_WB, 1 if enabled else 0)


def set_white_balance(cap: cv2.VideoCapture, temperature: float) -> None:
    cap.set(cv2.CAP_PROP_WB_TEMPERATURE, temperature)


def read_controls(cap: cv2.VideoCapture) -> dict:
    return {
        "exposure": cap.get(cv2.CAP_PROP_EXPOSURE),
        "gain": cap.get(cv2.CAP_PROP_GAIN),
        "auto_exposure": cap.get(cv2.CAP_PROP_AUTO_EXPOSURE),
        "wb_temperature": cap.get(cv2.CAP_PROP_WB_TEMPERATURE),
        "auto_wb": cap.get(cv2.CAP_PROP_AUTO_WB),
    }


# ---------- Main ----------
def run() -> None:
    logging.info("Selecting validated camera (Arducam B0495 preferred)...")
    index = select_validated_camera(backend=cv2.CAP_DSHOW)
    backend = cv2.CAP_DSHOW

    if index is None:
        logging.warning("No camera found with DirectShow. Trying MSMF...")
        index = select_validated_camera(backend=cv2.CAP_MSMF)
        backend = cv2.CAP_MSMF

    if index is None:
        logging.error("No camera found.")
        return

    cap = open_with_backend(index, backend)
    if cap is None:
        logging.error("Failed to open camera.")
        return

    mode = choose_mode(cap)
    actual_w, actual_h, actual_fps, actual_fourcc = get_actual_settings(cap)
    logging.info(
        "Requested: %dx%d @ %dfps YUY2 | Accepted: %dx%d @ %dfps %s (backend=%s)",
        mode.width, mode.height, mode.fps,
        actual_w, actual_h, actual_fps, actual_fourcc,
        "DSHOW" if backend == cv2.CAP_DSHOW else "MSMF"
    )

    if (actual_w, actual_h, actual_fps) == USB2_FALLBACK:
        logging.warning(
            "Camera fell back to USB2 mode (960x600@10). Likely causes: USB2 port, hub, cable, or bandwidth issues."
        )

    fps_measured = measure_fps(cap)
    logging.info("Measured FPS: %.1f", fps_measured)

    # Prepare writer for 5-second capture
    out_path = "camera_test_capture.avi"
    writer = cv2.VideoWriter(
        out_path,
        getattr(cv2, "VideoWriter_fourcc")(*"MJPG"),
        actual_fps if actual_fps > 0 else 30,
        (actual_w, actual_h),
        True,
    )

    start = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            logging.error("Frame capture failed.")
            break

        # Convert YUY2 to BGR for display if needed
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        writer.write(frame)
        cv2.imshow("Arducam B0495 Preview (press q to quit)", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        if time.time() - start >= 5:
            break

    cap.release()
    writer.release()
    cv2.destroyAllWindows()

    logging.info("Saved 5-second capture to %s", out_path)
    logging.info("Control readback: %s", read_controls(cap))


if __name__ == "__main__":
    run()


"""
Support Playbook

Expected behavior (USB3):
- Mode: 1920x1200 @ 50 fps, YUY2
- Measured FPS: typically ~45�55 fps depending on system load

How to verify USB3 performance:
- Use a direct USB3 port (blue port), avoid hubs.
- Confirm Windows Device Manager shows USB 3.0 controller.
- If the camera is only hitting 960x600@10, suspect USB2 link.

Known Windows pitfalls:
- YUY2 at 1920x1200@50 is high bandwidth; some hubs/cables can�t handle it.
- MSMF backend sometimes throttles or drops to lower FPS for UVC devices.
- DirectShow is generally more reliable for UVC control + YUY2 on Windows.

When to try MSMF:
- DirectShow fails to open the device.
- DirectShow returns blank frames or unstable capture.

Common failure symptoms and fixes:
- Low FPS: check USB port/cable/hub, reduce resolution or FPS.
- No frames: switch backend, reboot camera, check power/USB.
- Controls don�t change: OpenCV UVC control support is limited; use DirectShow COM (pywin32) or Media Foundation for full control.
"""

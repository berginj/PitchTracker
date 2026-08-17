"""Hardware probe operations for the camera capability CLI."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import cv2
import psutil

from ui.device_utils import (
    is_arducam_device,
    probe_opencv_indices,
    probe_uvc_devices,
)

logger = logging.getLogger(__name__)

TEST_MODES = (
    (640, 480, 15),
    (640, 480, 30),
    (640, 480, 60),
    (800, 600, 30),
    (1280, 720, 15),
    (1280, 720, 30),
    (1280, 720, 60),
    (1920, 1080, 15),
    (1920, 1080, 30),
    (1920, 1080, 60),
)


def enumerate_cameras(max_cameras: int) -> dict[int, dict[str, Any]]:
    """Enumerate stable UVC identities and currently openable OpenCV indices."""
    logger.info("Enumerating cameras 0-%s", max_cameras - 1)
    try:
        uvc_devices = probe_uvc_devices(use_cache=False)
        uvc_by_index = dict(enumerate(uvc_devices))
        logger.info("Found %s UVC devices", len(uvc_devices))
    except Exception as exc:
        logger.warning("Could not enumerate UVC devices: %s", exc)
        print(f"WARNING: Could not enumerate UVC devices: {exc}")
        uvc_by_index = {}

    try:
        opencv_indices = probe_opencv_indices(
            max_index=max_cameras,
            use_cache=False,
        )
        logger.info("Found OpenCV camera indices: %s", opencv_indices)
    except Exception as exc:
        logger.warning("Could not enumerate OpenCV devices: %s", exc)
        print(f"WARNING: Could not enumerate OpenCV devices: {exc}")
        opencv_indices = list(range(max_cameras))

    camera_info = {}
    for index in range(max_cameras):
        info: dict[str, Any] = {
            "index": index,
            "name": f"Camera {index}",
            "available": index in opencv_indices,
            "backend": "Unknown",
        }
        _add_uvc_identity(info, uvc_by_index.get(index))
        if info["available"]:
            _add_backend_name(info, index)
        camera_info[index] = info

    arducam_count = sum(1 for info in camera_info.values() if is_arducam_device(info["name"]))
    logger.info(
        "Camera enumeration complete. %s ArduCam devices found.",
        arducam_count,
    )
    return camera_info


def _add_uvc_identity(
    info: dict[str, Any],
    device: Optional[dict[str, str]],
) -> None:
    if device is None:
        return
    for source, target in (
        ("friendly_name", "name"),
        ("serial", "serial"),
        ("manufacturer", "manufacturer"),
    ):
        if device.get(source):
            info[target] = device[source]
    info["backend"] = "UVC/DirectShow"


def _add_backend_name(info: dict[str, Any], index: int) -> None:
    capture = None
    try:
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if capture.isOpened():
            info["backend"] = capture.getBackendName()
    except Exception as exc:
        logger.debug("Could not open camera %s: %s", index, exc)
    finally:
        if capture is not None:
            capture.release()


def test_camera_modes(
    camera_index: int,
    backend: int = cv2.CAP_DSHOW,
    camera_name: Optional[str] = None,
) -> list[tuple[int, int, int]]:
    """Return requested modes whose negotiated values and frame read agree."""
    backend_name = "DSHOW" if backend == cv2.CAP_DSHOW else "MSMF"
    camera_label = f"Camera {camera_index}"
    if camera_name:
        camera_label = f"{camera_label} ({camera_name})"
    logger.info("Testing %s with %s backend", camera_label, backend_name)
    print(f"\n=== Testing {camera_label} with {backend_name} ===\n")

    capture = None
    supported = []
    try:
        capture = cv2.VideoCapture(camera_index, backend)
        if not capture.isOpened():
            logger.error("Failed to open camera %s with %s", camera_index, backend_name)
            print(f"ERROR: Failed to open camera {camera_index}")
            return []
        print(f"Testing {len(TEST_MODES)} modes...\n")
        for requested in TEST_MODES:
            observed = _probe_mode(capture, requested)
            width, height, fps, can_read = observed
            if (width, height, fps) == requested and can_read:
                logger.info("%sx%s@%sfps - SUPPORTED", *requested)
                print(f"OK: {requested[0]}x{requested[1]}@{requested[2]}fps - SUPPORTED")
                supported.append(requested)
            else:
                print(
                    f"NO: {requested[0]}x{requested[1]}@{requested[2]}fps "
                    f"- NOT SUPPORTED (got {width}x{height}@{fps}fps, "
                    f"read={can_read})"
                )
        print(f"\nCamera {camera_index} supports " f"{len(supported)}/{len(TEST_MODES)} tested modes")
    except Exception as exc:
        logger.error("Error testing camera %s: %s", camera_index, exc, exc_info=True)
        print(f"ERROR: Error testing camera {camera_index}: {exc}")
    finally:
        if capture is not None:
            capture.release()
    return supported


def _probe_mode(
    capture: cv2.VideoCapture,
    requested: tuple[int, int, int],
) -> tuple[int, int, int, bool]:
    width, height, fps = requested
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2.CAP_PROP_FPS, fps)
    observed = (
        int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        int(capture.get(cv2.CAP_PROP_FPS)),
    )
    read_ok, frame = capture.read()
    return (*observed, bool(read_ok and frame is not None))


def test_memory_usage(
    camera_index: int,
    width: int,
    height: int,
    fps: int,
    duration_sec: int = 5,
    backend: int = cv2.CAP_DSHOW,
) -> dict[str, Any]:
    """Measure process memory and effective FPS for one requested mode."""
    baseline_mb = psutil.Process().memory_info().rss / 1024 / 1024
    print(f"\n=== Memory Test: {width}x{height}@{fps}fps for {duration_sec}s ===")
    print(f"Baseline memory: {baseline_mb:.1f} MB")
    capture = None
    try:
        capture = cv2.VideoCapture(camera_index, backend)
        _set_mode(capture, width, height, fps)
        actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (actual_width, actual_height) != (width, height):
            print(f"WARNING: Requested {width}x{height} but got " f"{actual_width}x{actual_height}")

        start = time.time()
        frame_times = []
        while time.time() - start < duration_sec:
            frame_start = time.time()
            read_ok, _ = capture.read()
            frame_end = time.time()
            if read_ok:
                frame_times.append(frame_end - frame_start)
        elapsed = time.time() - start
        frames_captured = len(frame_times)
        effective_fps = frames_captured / elapsed
        peak_mb = psutil.Process().memory_info().rss / 1024 / 1024
        average_ms = sum(frame_times) / frames_captured * 1000 if frames_captured else 0
        result = {
            "resolution": f"{width}x{height}@{fps}fps",
            "frames_captured": frames_captured,
            "effective_fps": effective_fps,
            "baseline_mb": baseline_mb,
            "peak_mb": peak_mb,
            "delta_mb": peak_mb - baseline_mb,
            "avg_frame_time_ms": average_ms,
            "success": True,
        }
        print(f"OK: Captured {frames_captured} frames in {elapsed:.1f}s")
        print(f"   Effective FPS: {effective_fps:.1f}")
        print(f"   Memory used: {result['delta_mb']:.1f} MB (peak: {peak_mb:.1f} MB)")
        print(f"   Avg frame time: {average_ms:.2f} ms")
        return result
    except Exception as exc:
        logger.error("Memory test failed: %s", exc, exc_info=True)
        print(f"ERROR: {exc}")
        return {
            "resolution": f"{width}x{height}@{fps}fps",
            "error": str(exc),
            "success": False,
        }
    finally:
        if capture is not None:
            capture.release()


def test_dual_camera(
    width: int,
    height: int,
    fps: int,
    duration_sec: int = 10,
    backend: int = cv2.CAP_DSHOW,
) -> dict[str, Any]:
    """Measure simultaneous reads from indices zero and one."""
    print(f"\n=== Dual Camera Test: {width}x{height}@{fps}fps for {duration_sec}s ===")
    left_capture = None
    right_capture = None
    try:
        left_capture = cv2.VideoCapture(0, backend)
        right_capture = cv2.VideoCapture(1, backend)
        for capture in (left_capture, right_capture):
            _set_mode(capture, width, height, fps)
        if not left_capture.isOpened() or not right_capture.isOpened():
            print("ERROR: Failed to open both cameras")
            return {"success": False, "error": "Failed to open cameras"}

        start = time.time()
        left_frames = right_frames = errors = 0
        print("Capturing...")
        while time.time() - start < duration_sec:
            left_ok, _ = left_capture.read()
            right_ok, _ = right_capture.read()
            left_frames += int(left_ok)
            right_frames += int(right_ok)
            errors += int(not left_ok) + int(not right_ok)
            time.sleep(0.001)
        elapsed = time.time() - start
        result = {
            "resolution": f"{width}x{height}@{fps}fps",
            "frames_left": left_frames,
            "frames_right": right_frames,
            "errors": errors,
            "effective_fps_left": left_frames / elapsed,
            "effective_fps_right": right_frames / elapsed,
            "success": True,
        }
        print("OK: Dual camera test complete")
        print(f"   Left: {left_frames} frames ({result['effective_fps_left']:.1f} fps)")
        print(f"   Right: {right_frames} frames ({result['effective_fps_right']:.1f} fps)")
        print(f"   Errors: {errors}")
        return result
    except Exception as exc:
        logger.error("Dual camera test failed: %s", exc, exc_info=True)
        print(f"ERROR: {exc}")
        return {"success": False, "error": str(exc)}
    finally:
        for capture_candidate in (left_capture, right_capture):
            if capture_candidate is not None:
                capture_candidate.release()


def _set_mode(
    capture: cv2.VideoCapture,
    width: int,
    height: int,
    fps: int,
) -> None:
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2.CAP_PROP_FPS, fps)

"""Paired-preview capture lifecycle utilities for stereo setup."""

from __future__ import annotations

from typing import Callable, Optional

from capture.camera_device import CameraDevice
from capture.simulated_camera import SimulatedCamera
from capture.uvc_backend import UvcCamera
from contracts.types import Frame
from exceptions import CameraError
from ui.setup.paired_preview_view import PairedPreviewSnapshot, empty_preview_snapshot

PreviewProvider = Callable[[], PairedPreviewSnapshot]


def capture_paired_preview(
    left: CameraDevice,
    right: CameraDevice,
    *,
    frames: int = 5,
    tolerance_ms: float = 5.0,
    timeout_ms: int = 1000,
    width: int = 64,
    height: int = 48,
    fps: int = 0,
    pixfmt: str = "GRAY8",
) -> PairedPreviewSnapshot:
    """Grab a short burst from a left/right camera pair and grade the pairing.

    Works with any :class:`CameraDevice` (real or :class:`SimulatedCamera`); the
    cameras must already be opened. A per-side read failure is recorded honestly
    rather than raised, so a single dead camera produces a failing snapshot.

    Returns:
        A :class:`PairedPreviewSnapshot` summarising stream health and offset.
    """
    left.set_mode(width, height, fps, pixfmt)
    right.set_mode(width, height, fps, pixfmt)

    left_ok = False
    right_ok = False
    last_left = -1
    last_right = -1
    observed = 0
    paired_count = 0
    max_offset_ms = 0.0

    for _ in range(max(1, frames)):
        left_frame = _read_side(left, timeout_ms)
        right_frame = _read_side(right, timeout_ms)
        if left_frame is not None:
            left_ok = True
            last_left = left_frame.frame_index
        if right_frame is not None:
            right_ok = True
            last_right = right_frame.frame_index
        if left_frame is not None or right_frame is not None:
            observed += 1
        if left_frame is not None and right_frame is not None:
            paired_count += 1
            offset_ms = abs(left_frame.t_capture_monotonic_ns - right_frame.t_capture_monotonic_ns) / 1e6
            max_offset_ms = max(max_offset_ms, offset_ms)

    return PairedPreviewSnapshot(
        left_ok=left_ok,
        right_ok=right_ok,
        paired_within_tolerance=paired_count > 0 and max_offset_ms <= tolerance_ms,
        left_frame_index=last_left,
        right_frame_index=last_right,
        pair_offset_ms=max_offset_ms,
        frames_observed=observed,
    )


def _read_side(camera: CameraDevice, timeout_ms: int) -> Optional[Frame]:
    try:
        return camera.read_frame(timeout_ms)
    except CameraError:
        return None


def simulated_paired_preview(
    *,
    frames: int = 5,
    tolerance_ms: float = 50.0,
) -> PairedPreviewSnapshot:
    """Convenience preview provider backed by two :class:`SimulatedCamera`.

    Useful for demos and self-tests on machines without stereo hardware. The
    default tolerance is generous because simulated capture is not time-locked.
    """
    left = SimulatedCamera()
    right = SimulatedCamera()
    left.open("sim-left")
    right.open("sim-right")
    try:
        return capture_paired_preview(left, right, frames=frames, tolerance_ms=tolerance_ms)
    finally:
        left.close()
        right.close()


def make_camera_preview_provider(
    left_serial: str,
    right_serial: str,
    *,
    camera_factory: Callable[[], CameraDevice] = UvcCamera,
    frames: int = 5,
    tolerance_ms: float = 8.0,
) -> PreviewProvider:
    """Create a paired-preview provider backed by the selected camera serials."""

    def _provider() -> PairedPreviewSnapshot:
        left = camera_factory()
        right = camera_factory()
        try:
            left.open(left_serial)
            right.open(right_serial)
            return capture_paired_preview(left, right, frames=frames, tolerance_ms=tolerance_ms)
        except CameraError:
            return empty_preview_snapshot()
        finally:
            left.close()
            right.close()

    return _provider

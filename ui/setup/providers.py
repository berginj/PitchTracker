"""Real-backend adapter providers for the stereo setup wizard (steps 1 & 2).

These convert live hardware backends into the Qt-free snapshot dataclasses that
the camera-select and paired-preview step widgets render. They are injected into
the widgets by the live wizard; the registry's test-safe defaults in
:mod:`ui.setup.stereo_steps` stay empty so the synthetic step tests never touch
hardware.

Every adapter takes its hardware dependency as an injected parameter so the
logic is unit-testable with fakes and the :class:`SimulatedCamera` backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Sequence

from capture.camera_device import CameraDevice
from capture.device_discovery import list_uvc_devices
from capture.simulated_camera import SimulatedCamera
from capture.uvc_backend import UvcCamera
from contracts.catalog import SIDE_UNASSIGNED
from contracts.types import Frame
from exceptions import CameraError
from ui.setup.camera_select_view import CameraSelectionSnapshot, DiscoveredCamera
from ui.setup.paired_preview_view import PairedPreviewSnapshot, empty_preview_snapshot

if TYPE_CHECKING:
    from ui.setup.state_machine import SetupStep
    from ui.setup.steps.base_step import BaseStep

DeviceLister = Callable[[], Sequence[Dict[str, str]]]
PreviewProvider = Callable[[], PairedPreviewSnapshot]


def discover_camera_selection(
    *,
    list_devices: DeviceLister = list_uvc_devices,
    catalog: Optional[object] = None,
) -> CameraSelectionSnapshot:
    """Adapt live UVC discovery + the camera catalog into a selection snapshot.

    Args:
        list_devices: Callable returning device dicts (keys ``serial`` /
            ``instance_id`` / ``friendly_name``). Injectable for tests.
        catalog: Optional ``CameraCatalogService``-like object exposing
            ``known_devices()`` (for carry-over side assignment) and
            ``match_model(friendly_name)`` (for recognition).

    Returns:
        A :class:`CameraSelectionSnapshot` reflecting the discovered cameras.
    """
    devices = list_devices() or []
    sides = _known_sides(catalog)
    recognize = getattr(catalog, "match_model", None) if catalog is not None else None

    cameras: List[DiscoveredCamera] = []
    for entry in devices:
        hardware_id = str(entry.get("serial") or entry.get("instance_id") or "")
        friendly = str(entry.get("friendly_name") or "")
        recognized = bool(recognize(friendly)) if recognize is not None else False
        cameras.append(
            DiscoveredCamera(
                hardware_id=hardware_id,
                friendly_name=friendly,
                side=sides.get(hardware_id, SIDE_UNASSIGNED),
                recognized=recognized,
            )
        )
    return CameraSelectionSnapshot(cameras=tuple(cameras))


def _known_sides(catalog: Optional[object]) -> Dict[str, str]:
    if catalog is None:
        return {}
    known = getattr(catalog, "known_devices", None)
    if known is None:
        return {}
    return {device.hardware_id: device.side for device in known()}


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


def build_live_stereo_step_widgets(
    *,
    catalog: Optional[object] = None,
    list_devices: DeviceLister = list_uvc_devices,
    preview_provider: Optional[PreviewProvider] = None,
) -> "Dict[SetupStep, BaseStep]":
    """Build the canonical registry with real providers wired for steps 1 & 2.

    Steps 3-9 keep their existing file-based providers from
    :func:`ui.setup.stereo_steps.build_stereo_step_widgets`. Step 1 uses live
    UVC discovery; step 2 uses ``preview_provider`` when supplied (e.g. a
    real-camera burst) and otherwise stays an honest empty preview.

    Args:
        catalog: Optional camera-catalog service for recognition / carry-over.
        list_devices: Device lister for step-1 discovery (injectable for tests).
        preview_provider: Optional callable yielding a paired-preview snapshot
            from live cameras. ``None`` leaves the step's empty default.

    Returns:
        A mapping with an entry for every canonical :class:`SetupStep`.
    """
    from ui.setup.stereo_steps import build_stereo_step_widgets
    from ui.setup.state_machine import SetupStep
    from ui.setup.steps import CameraSelectStep, PairedPreviewStep

    widgets = build_stereo_step_widgets()
    widgets[SetupStep.SELECT_CAMERAS] = CameraSelectStep(
        snapshot_provider=lambda: discover_camera_selection(list_devices=list_devices, catalog=catalog)
    )
    if preview_provider is not None:
        widgets[SetupStep.PAIRED_PREVIEW] = PairedPreviewStep(snapshot_provider=preview_provider)
    return widgets


__all__ = [
    "DeviceLister",
    "PreviewProvider",
    "build_live_stereo_step_widgets",
    "capture_paired_preview",
    "discover_camera_selection",
    "make_camera_preview_provider",
    "simulated_paired_preview",
]

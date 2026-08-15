"""Camera discovery, ranking, and recommendation logic for stereo setup."""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from typing import Any, Dict, Iterable, List, Optional, Sequence, Callable

from capture.device_discovery import list_uvc_devices
from contracts.catalog import SIDE_UNASSIGNED, SIDE_LEFT, SIDE_RIGHT
from ui.setup.camera_select_view import CameraSelectionSnapshot, DiscoveredCamera

DeviceLister = Callable[[], Sequence[Dict[str, Any]]]


def discover_camera_selection(
    *,
    list_devices: DeviceLister = list_uvc_devices,
    catalog: Optional[object] = None,
    requested_mode: Optional[tuple[int, int, int]] = None,
    validated_pairs: Iterable[dict[str, Any]] = (),
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
        matched_model = recognize(friendly) if recognize is not None else None
        recognized = matched_model is not None
        capabilities = getattr(matched_model, "capabilities", None)
        global_shutter = bool(
            getattr(matched_model, "global_shutter", False)
            or getattr(capabilities, "global_shutter", False)
        )
        modes = tuple(
            (int(mode.width), int(mode.height), int(mode.fps))
            for mode in (getattr(capabilities, "supported_modes", ()) or ())
        )
        controls = tuple(str(item) for item in (getattr(capabilities, "controls", ()) or ()))
        cameras.append(
            DiscoveredCamera(
                hardware_id=hardware_id,
                friendly_name=friendly,
                side=sides.get(hardware_id, SIDE_UNASSIGNED),
                recognized=recognized,
                global_shutter=global_shutter,
                model=str(getattr(matched_model, "model", "") or ""),
                supported_modes=modes,
                controls=controls,
                sync_capable=getattr(capabilities, "sync_capable", None),
                instance_id=_optional_device_value(entry, "instance_id"),
                device_path=_optional_device_value(entry, "device_path", "path", "pnp_device_id"),
                usb_controller=_optional_device_value(entry, "usb_controller", "controller"),
                driver_version=_optional_device_value(entry, "driver_version"),
                firmware_version=_optional_device_value(entry, "firmware_version"),
                capability_score=_camera_capability_score(
                    recognized=recognized,
                    global_shutter=global_shutter,
                    sync_capable=getattr(capabilities, "sync_capable", None),
                    supported_modes=modes,
                    controls=controls,
                    requested_mode=requested_mode,
                ),
            )
        )
    return _apply_camera_recommendation(cameras, requested_mode, tuple(validated_pairs))


def _apply_camera_recommendation(
    cameras: list[DiscoveredCamera],
    requested_mode: Optional[tuple[int, int, int]],
    validated_pairs: tuple[dict[str, Any], ...],
) -> CameraSelectionSnapshot:
    by_id = {camera.hardware_id: camera for camera in cameras}
    for pair in validated_pairs:
        left_id = str(pair.get("left_id") or "")
        right_id = str(pair.get("right_id") or "")
        if left_id in by_id and right_id in by_id and left_id != right_id:
            profile_id = str(pair.get("profile_id") or "")
            reason = (
                f"Exact camera pair from previously validated profile {profile_id}; "
                "runtime will re-verify the approval and artifact bindings."
            )
            return _recommended_snapshot(
                cameras,
                left_id,
                right_id,
                source="previously_validated_profile",
                reason=reason,
                validated_profile_id=profile_id,
            )

    eligible = [camera for camera in cameras if camera.recognized and camera.global_shutter]
    if len(eligible) < 2:
        if len(cameras) < 2:
            return CameraSelectionSnapshot(
                cameras=tuple(cameras),
                recommendation_source="unavailable",
                recommendation_reason="Fewer than two cameras are available.",
            )
        return _best_camera_pair_snapshot(
            cameras,
            cameras,
            requested_mode,
            source="diagnostic_fallback",
            reason=(
                "No pair of two recognized global-shutter cameras is available. "
                "This fallback pair may be used for diagnostic setup only; "
                "production measurement remains blocked."
            ),
        )

    return _best_camera_pair_snapshot(
        cameras,
        eligible,
        requested_mode,
        source="capability_score",
        reason_prefix="Best compatible recognized global-shutter pair",
    )


def _best_camera_pair_snapshot(
    cameras: list[DiscoveredCamera],
    eligible: list[DiscoveredCamera],
    requested_mode: Optional[tuple[int, int, int]],
    *,
    source: str,
    reason: str = "",
    reason_prefix: str = "",
) -> CameraSelectionSnapshot:
    pair_candidates = []
    for first, second in combinations(eligible, 2):
        score = _camera_pair_score(first, second, requested_mode)
        tie_key = tuple(sorted((first.hardware_id, second.hardware_id)))
        pair_candidates.append((score, tie_key, first, second))
    best_score = max(item[0] for item in pair_candidates)
    _, _, first, second = min(
        (item for item in pair_candidates if item[0] == best_score),
        key=lambda item: item[1],
    )
    left, right = _recommended_sides(first, second)
    requested_text = (
        f"{requested_mode[0]}x{requested_mode[1]}@{requested_mode[2]}"
        if requested_mode is not None
        else "the requested mode"
    )
    if not reason:
        reason = (
            f"{reason_prefix} for {requested_text}; ranking considers requested-mode "
            "support, synchronization, common modes, controls, and throughput."
        )
    return _recommended_snapshot(
        cameras,
        left.hardware_id,
        right.hardware_id,
        source=source,
        reason=reason,
    )


def _recommended_snapshot(
    cameras: list[DiscoveredCamera],
    left_id: str,
    right_id: str,
    *,
    source: str,
    reason: str,
    validated_profile_id: str = "",
) -> CameraSelectionSnapshot:
    updated = []
    for camera in cameras:
        recommended_side = (
            SIDE_LEFT if camera.hardware_id == left_id else SIDE_RIGHT if camera.hardware_id == right_id else SIDE_UNASSIGNED
        )
        updated.append(
            replace(
                camera,
                recommended_side=recommended_side,
                recommendation_reason=reason if recommended_side != SIDE_UNASSIGNED else "",
                previously_validated=bool(validated_profile_id and recommended_side != SIDE_UNASSIGNED),
                validated_profile_id=validated_profile_id if recommended_side != SIDE_UNASSIGNED else "",
            )
        )
    return CameraSelectionSnapshot(
        cameras=tuple(updated),
        recommended_left_id=left_id,
        recommended_right_id=right_id,
        recommendation_source=source,
        recommendation_reason=reason,
    )


def _recommended_sides(first: DiscoveredCamera, second: DiscoveredCamera) -> tuple[DiscoveredCamera, DiscoveredCamera]:
    if first.side == SIDE_LEFT or second.side == SIDE_RIGHT:
        return first, second
    if second.side == SIDE_LEFT or first.side == SIDE_RIGHT:
        return second, first
    ordered = sorted((first, second), key=lambda camera: camera.hardware_id)
    return ordered[0], ordered[1]


def _camera_pair_score(
    first: DiscoveredCamera,
    second: DiscoveredCamera,
    requested_mode: Optional[tuple[int, int, int]],
) -> tuple[int, int, int, int, int, int]:
    first_modes = set(first.supported_modes)
    second_modes = set(second.supported_modes)
    common_modes = first_modes & second_modes
    requested_supported = int(requested_mode is not None and requested_mode in common_modes)
    both_sync = int(first.sync_capable is True and second.sync_capable is True)
    common_throughput = max((width * height * fps for width, height, fps in common_modes), default=0)
    common_controls = len(set(first.controls) & set(second.controls))
    same_model = int(bool(first.model) and first.model == second.model)
    return (
        requested_supported,
        both_sync,
        common_throughput,
        min(first.capability_score, second.capability_score),
        common_controls,
        same_model,
    )


def _camera_capability_score(
    *,
    recognized: bool,
    global_shutter: bool,
    sync_capable: Optional[bool],
    supported_modes: tuple[tuple[int, int, int], ...],
    controls: tuple[str, ...],
    requested_mode: Optional[tuple[int, int, int]],
) -> int:
    throughput = max((width * height * fps for width, height, fps in supported_modes), default=0)
    return (
        int(recognized) * 10**12
        + int(global_shutter) * 10**11
        + int(requested_mode is not None and requested_mode in supported_modes) * 10**10
        + int(sync_capable is True) * 10**9
        + len(set(controls) & {"exposure", "gain", "white_balance", "focus"}) * 10**7
        + throughput
    )


def _optional_device_value(entry: dict[str, Any], *names: str) -> Optional[str]:
    for name in names:
        value = entry.get(name)
        if value not in {None, ""}:
            return str(value)
    return None


def _known_sides(catalog: Optional[object]) -> Dict[str, str]:
    if catalog is None:
        return {}
    known = getattr(catalog, "known_devices", None)
    if known is None:
        return {}
    return {device.hardware_id: device.side for device in known()}

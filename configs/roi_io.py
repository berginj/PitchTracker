"""Persist shared lane and plate ROI polygons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

Point = Tuple[int, int]
Polygon = List[Point]


def load_rois(path: Path) -> Dict[str, Polygon]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    output: Dict[str, Polygon] = {}
    for key in ("lane", "plate"):
        points = data.get(key)
        if isinstance(points, list):
            output[key] = [(int(x), int(y)) for x, y in points]
    return output


def load_runtime_roi_maps(
    roi_path: Path,
    left_id: str,
    right_id: str,
    *,
    lane_path: Path | None = None,
) -> tuple[Dict[str, Polygon], Dict[str, Polygon]]:
    """Load lane and plate ROI maps for runtime gates.

    The active rig-profile ROI file may contain shared polygons (`lane`,
    `plate`) plus per-camera overrides (`lane_by_camera`,
    `plate_by_camera`). Legacy lane override files are still honored when
    supplied.
    """
    data = _load_roi_payload(roi_path)
    lane_by_camera = _load_polygon_map(data.get("lane_by_camera"))
    plate_by_camera = _load_polygon_map(data.get("plate_by_camera"))

    shared_lane = _load_polygon(data.get("lane"))
    shared_plate = _load_polygon(data.get("plate"))
    if shared_lane:
        lane_by_camera.setdefault(left_id, shared_lane)
        lane_by_camera.setdefault(right_id, shared_lane)
    if shared_plate:
        plate_by_camera.setdefault(left_id, shared_plate)
        plate_by_camera.setdefault(right_id, shared_plate)

    if lane_path is not None and lane_path.exists():
        try:
            from configs.lane_io import load_lane_rois

            legacy_lanes = load_lane_rois(lane_path)
            left_lane = legacy_lanes.get(left_id) or legacy_lanes.get("left")
            right_lane = legacy_lanes.get(right_id) or legacy_lanes.get("right")
            if left_lane is not None:
                lane_by_camera[left_id] = [(int(x), int(y)) for x, y in left_lane.polygon]
            if right_lane is not None:
                lane_by_camera[right_id] = [(int(x), int(y)) for x, y in right_lane.polygon]
        except Exception:
            pass

    return lane_by_camera, plate_by_camera


def save_rois(
    path: Path,
    lane: Polygon | None,
    plate: Polygon | None,
    *,
    lane_by_camera: Mapping[str, Polygon] | None = None,
    plate_by_camera: Mapping[str, Polygon] | None = None,
) -> None:
    payload: dict[str, object] = {
        "shared": True,
        "lane": lane if lane is not None else None,
        "plate": plate if plate is not None else None,
    }
    if lane_by_camera is not None:
        payload["lane_by_camera"] = {
            str(camera_id): _serialize_polygon(points) for camera_id, points in lane_by_camera.items()
        }
    if plate_by_camera is not None:
        payload["plate_by_camera"] = {
            str(camera_id): _serialize_polygon(points) for camera_id, points in plate_by_camera.items()
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _load_roi_payload(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def _load_polygon(points) -> Polygon | None:
    if not isinstance(points, list):
        return None
    output: Polygon = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return None
        x, y = point
        output.append((int(x), int(y)))
    return output if len(output) >= 3 else None


def _load_polygon_map(data) -> Dict[str, Polygon]:
    if not isinstance(data, dict):
        return {}
    output: Dict[str, Polygon] = {}
    for camera_id, points in data.items():
        polygon = _load_polygon(points)
        if polygon:
            output[str(camera_id)] = polygon
    return output


def _serialize_polygon(points: Polygon) -> list[list[int]]:
    return [[int(x), int(y)] for x, y in points]

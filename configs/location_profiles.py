"""Persist setup profiles for known locations."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from configs.roi_io import load_rois, save_rois

Profile = Dict[str, object]


def profiles_dir(root: Optional[Path] = None) -> Path:
    base = root or Path("configs")
    path = base / "locations"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_profiles(root: Optional[Path] = None) -> List[str]:
    path = profiles_dir(root)
    return sorted(p.stem for p in path.glob("*.json"))


def load_profile(name: str, root: Optional[Path] = None) -> Profile:
    path = profiles_dir(root) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Profile '{name}' not found.")
    data: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(key, str) for key in data):
        raise ValueError(f"Profile '{name}' is not a JSON object.")
    return {str(key): value for key, value in data.items()}


def save_profile(
    name: str,
    left_serial: str,
    right_serial: str,
    roi_path: Path,
    root: Optional[Path] = None,
) -> Path:
    rois = load_rois(roi_path)
    payload = {
        "name": name,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "left_serial": left_serial,
        "right_serial": right_serial,
        "lane": rois.get("lane"),
        "plate": rois.get("plate"),
    }
    path = profiles_dir(root) / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def apply_profile(profile: Profile, roi_path: Path) -> None:
    lane = _profile_polygon(profile.get("lane"))
    plate = _profile_polygon(profile.get("plate"))
    save_rois(roi_path, lane, plate)


def _profile_polygon(value: object) -> list[tuple[int, int]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("Profile ROI must be a list")
    points: list[tuple[int, int]] = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Profile ROI points must contain two coordinates")
        x, y = point
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError("Profile ROI coordinates must be numeric")
        points.append((int(x), int(y)))
    return points

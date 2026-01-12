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
    return json.loads(path.read_text())


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
    lane = profile.get("lane")
    plate = profile.get("plate")
    save_rois(roi_path, lane, plate)

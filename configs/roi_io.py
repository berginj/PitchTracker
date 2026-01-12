"""Persist shared lane and plate ROI polygons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

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


def save_rois(path: Path, lane: Polygon | None, plate: Polygon | None) -> None:
    payload = {
        "shared": True,
        "lane": lane if lane is not None else None,
        "plate": plate if plate is not None else None,
    }
    path.write_text(json.dumps(payload, indent=2))

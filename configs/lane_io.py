"""Persist lane ROI polygons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from detect.lane import LaneRoi


def load_lane_rois(path: Path) -> Dict[str, LaneRoi]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {camera_id: LaneRoi(polygon=points) for camera_id, points in data.items()}


def save_lane_rois(path: Path, rois: Dict[str, LaneRoi]) -> None:
    serialized = {camera_id: roi.polygon for camera_id, roi in rois.items()}
    path.write_text(json.dumps(serialized, indent=2))

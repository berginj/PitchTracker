"""OpenCV-based preview window with lane ROI drawing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2

from configs.lane_io import load_lane_rois, save_lane_rois
from detect.lane import LaneRoi

Point = Tuple[int, int]


@dataclass
class PreviewState:
    points: List[Point]


def _draw_polygon(frame, points: List[Point]) -> None:
    if len(points) >= 2:
        cv2.polylines(frame, [cv2.UMat(points).get()], False, (0, 255, 0), 2)
    for point in points:
        cv2.circle(frame, point, 4, (0, 255, 0), -1)


def _mouse_callback(event, x, y, flags, state: PreviewState) -> None:
    if event == cv2.EVENT_LBUTTONDOWN:
        state.points.append((x, y))


def run_preview(
    window_name: str,
    left_frame,
    right_frame,
    lane_path: Path,
    left_id: str,
    right_id: str,
    state: PreviewState,
) -> Dict[str, LaneRoi]:
    lane_rois = load_lane_rois(lane_path)
    if left_id in lane_rois:
        state.points = [(int(x), int(y)) for x, y in lane_rois[left_id].polygon]

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, _mouse_callback, state)

    while True:
        combined = cv2.hconcat([left_frame, right_frame])
        _draw_polygon(combined, state.points)
        cv2.imshow(window_name, combined)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("s"):
            if len(state.points) >= 3:
                lane_rois[left_id] = LaneRoi(polygon=state.points)
                lane_rois[right_id] = LaneRoi(polygon=state.points)
                save_lane_rois(lane_path, lane_rois)
        if key == ord("c"):
            state.points = []
        if key == ord("q"):
            break

    cv2.destroyWindow(window_name)
    return lane_rois

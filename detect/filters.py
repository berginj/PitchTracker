from __future__ import annotations

from detect.config import FilterConfig
from detect.types import BlobDetection, Lanes
from detect.utils import point_in_polygon


def apply_area_filter(
    detections: list[BlobDetection], config: FilterConfig
) -> list[BlobDetection]:
    output = []
    for det in detections:
        if det.area < config.min_area:
            continue
        if config.max_area is not None and det.area > config.max_area:
            continue
        output.append(det)
    return output


def apply_circularity_filter(
    detections: list[BlobDetection], config: FilterConfig
) -> list[BlobDetection]:
    output = []
    for det in detections:
        if det.circularity < config.min_circularity:
            continue
        if config.max_circularity is not None and det.circularity > config.max_circularity:
            continue
        output.append(det)
    return output


def apply_velocity_filter(
    detections: list[BlobDetection], config: FilterConfig
) -> list[BlobDetection]:
    output = []
    for det in detections:
        if det.velocity is None:
            output.append(det)
            continue
        if det.velocity < config.min_velocity:
            continue
        if config.max_velocity is not None and det.velocity > config.max_velocity:
            continue
        output.append(det)
    return output


def apply_lane_gating(
    detections: list[BlobDetection], lanes: Lanes | None
) -> list[BlobDetection]:
    if not lanes:
        return detections
    gated: list[Detection] = []
    lane_list = [list(lane) for lane in lanes]
    for det in detections:
        if any(point_in_polygon(det.centroid, lane) for lane in lane_list):
            gated.append(det)
    return gated


def apply_filters(
    detections: list[BlobDetection], config: FilterConfig, lanes: Lanes | None
) -> list[BlobDetection]:
    output = apply_area_filter(detections, config)
    output = apply_circularity_filter(output, config)
    output = apply_velocity_filter(output, config)
    output = apply_lane_gating(output, lanes)
    return output

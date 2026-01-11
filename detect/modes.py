from __future__ import annotations

import numpy as np

from detect.config import DetectorConfig
from detect.types import Detection
from detect.utils import Component, connected_components, sobel_edges, to_grayscale


def _components_to_detections(components: list[Component]) -> list[Detection]:
    detections: list[Detection] = []
    for comp in components:
        if comp.perimeter == 0:
            circularity = 0.0
        else:
            circularity = 4 * np.pi * comp.area / (comp.perimeter**2)
        detections.append(
            Detection(
                centroid=comp.centroid,
                area=comp.area,
                perimeter=comp.perimeter,
                bbox=comp.bbox,
                circularity=float(circularity),
            )
        )
    return detections


def detect_mode_a(
    frame: np.ndarray,
    prev_frame: np.ndarray | None,
    background: np.ndarray | None,
    config: DetectorConfig,
) -> tuple[list[Detection], np.ndarray]:
    gray = to_grayscale(frame)
    if prev_frame is None:
        return [], gray
    prev_gray = to_grayscale(prev_frame)

    if background is None:
        background = prev_gray

    diff = np.abs(gray - prev_gray)
    bg_diff = np.abs(gray - background)
    foreground = (diff > config.frame_diff_threshold) | (
        bg_diff > config.bg_diff_threshold
    )
    background = config.bg_alpha * gray + (1 - config.bg_alpha) * background

    components = connected_components(foreground)
    return _components_to_detections(components), background


def detect_mode_b(
    frame: np.ndarray,
    background: np.ndarray | None,
    config: DetectorConfig,
) -> tuple[list[Detection], np.ndarray]:
    gray = to_grayscale(frame)
    if background is None:
        background = gray

    edges = sobel_edges(gray)
    edge_mask = edges > config.edge_threshold

    bg_diff = np.abs(gray - background)
    blob_mask = bg_diff > config.blob_threshold
    background = config.bg_alpha * gray + (1 - config.bg_alpha) * background

    hybrid_mask = edge_mask | blob_mask
    components = connected_components(hybrid_mask)
    return _components_to_detections(components), background

from __future__ import annotations

import numpy as np

from detect.config import DetectorConfig
from detect.types import BlobDetection
from detect.utils import Component, connected_components, sobel_edges, to_grayscale


def _components_to_detections(components: list[Component]) -> list[BlobDetection]:
    detections: list[BlobDetection] = []
    for comp in components:
        if comp.perimeter == 0:
            circularity = 0.0
        else:
            circularity = 4 * np.pi * comp.area / (comp.perimeter**2)
        detections.append(
            BlobDetection(
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
) -> tuple[list[BlobDetection], np.ndarray]:
    gray = to_grayscale(frame)
    if prev_frame is None:
        # Return uint8 for memory efficiency (75% less memory than float32)
        return [], np.clip(gray, 0, 255).astype(np.uint8)
    prev_gray = to_grayscale(prev_frame)

    if background is None:
        background = prev_gray

    # Convert background to float32 for computation (preserve precision)
    background_f32 = background.astype(np.float32) if background.dtype == np.uint8 else background

    diff = np.abs(gray - prev_gray)
    bg_diff = np.abs(gray - background_f32)
    foreground = (diff > config.frame_diff_threshold) | (
        bg_diff > config.bg_diff_threshold
    )

    # Update background in float32 for accuracy
    background_f32 = config.bg_alpha * gray + (1 - config.bg_alpha) * background_f32

    # Convert back to uint8 for storage (75% memory reduction)
    background_uint8 = np.clip(background_f32, 0, 255).astype(np.uint8)

    components = connected_components(foreground)
    return _components_to_detections(components), background_uint8


def detect_mode_b(
    frame: np.ndarray,
    background: np.ndarray | None,
    config: DetectorConfig,
) -> tuple[list[BlobDetection], np.ndarray]:
    gray = to_grayscale(frame)
    if background is None:
        # Return uint8 for memory efficiency
        return [], np.clip(gray, 0, 255).astype(np.uint8)

    # Convert background to float32 for computation
    background_f32 = background.astype(np.float32) if background.dtype == np.uint8 else background

    edges = sobel_edges(gray)
    edge_mask = edges > config.edge_threshold

    bg_diff = np.abs(gray - background_f32)
    blob_mask = bg_diff > config.blob_threshold

    # Update background in float32
    background_f32 = config.bg_alpha * gray + (1 - config.bg_alpha) * background_f32

    # Convert back to uint8 for storage (75% memory reduction)
    background_uint8 = np.clip(background_f32, 0, 255).astype(np.uint8)

    hybrid_mask = edge_mask | blob_mask
    components = connected_components(hybrid_mask)
    return _components_to_detections(components), background_uint8

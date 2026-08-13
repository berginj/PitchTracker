"""Detection configuration and frame processing for review mode."""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

import cv2
import numpy as np

from configs.settings import DetectorConfig, DetectorFiltersConfig
from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import (
    DetectorConfig as RuntimeDetectorConfig,
    FilterConfig as RuntimeFilterConfig,
    Mode,
)
from exceptions import PitchTrackerError
from log_config.logger import get_logger

logger = get_logger(__name__)


def default_detector_config() -> DetectorConfig:
    """Return the stable review-mode default detector configuration."""
    return DetectorConfig(
        type="classical",
        model_path=None,
        model_input_size=(640, 640),
        model_conf_threshold=0.25,
        model_class_id=0,
        model_format="yolo_v5",
        mode="MODE_A",
        frame_diff_threshold=18.0,
        bg_diff_threshold=12.0,
        bg_alpha=0.01,
        edge_threshold=50.0,
        blob_threshold=20.0,
        runtime_budget_ms=10.0,
        crop_padding_px=10,
        min_consecutive=3,
        filters=DetectorFiltersConfig(
            min_area=12,
            max_area=500,
            min_circularity=0.1,
            max_circularity=1.0,
            min_velocity=10.0,
            max_velocity=200.0,
        ),
    )


def update_detector_config(
    config: DetectorConfig,
    *,
    frame_diff_threshold: Optional[float],
    bg_diff_threshold: Optional[float],
    min_area: Optional[int],
    max_area: Optional[int],
    min_circularity: Optional[float],
    mode: Optional[Mode],
) -> DetectorConfig:
    """Create an updated frozen detector configuration."""
    filters = replace(
        config.filters,
        min_area=min_area if min_area is not None else config.filters.min_area,
        max_area=max_area if max_area is not None else config.filters.max_area,
        min_circularity=(min_circularity if min_circularity is not None else config.filters.min_circularity),
    )
    return replace(
        config,
        mode=mode.value if mode is not None else config.mode,
        frame_diff_threshold=(
            frame_diff_threshold if frame_diff_threshold is not None else config.frame_diff_threshold
        ),
        bg_diff_threshold=(bg_diff_threshold if bg_diff_threshold is not None else config.bg_diff_threshold),
        filters=filters,
    )


def build_detectors(config: DetectorConfig, mode: Mode) -> tuple[ClassicalDetector, ClassicalDetector]:
    """Build independent left and right review detectors."""
    runtime_config = RuntimeDetectorConfig(
        frame_diff_threshold=config.frame_diff_threshold,
        bg_diff_threshold=config.bg_diff_threshold,
        bg_alpha=config.bg_alpha,
        edge_threshold=config.edge_threshold,
        blob_threshold=config.blob_threshold,
        runtime_budget_ms=config.runtime_budget_ms,
        crop_padding_px=config.crop_padding_px,
        min_consecutive=config.min_consecutive,
        filters=RuntimeFilterConfig(
            min_area=config.filters.min_area,
            max_area=config.filters.max_area,
            min_circularity=config.filters.min_circularity,
            max_circularity=config.filters.max_circularity,
            min_velocity=config.filters.min_velocity,
            max_velocity=config.filters.max_velocity,
        ),
    )
    return (
        ClassicalDetector(config=runtime_config, mode=mode, roi_by_camera={}),
        ClassicalDetector(config=runtime_config, mode=mode, roi_by_camera={}),
    )


def detect_frame(
    detector: Optional[ClassicalDetector],
    image: Optional[np.ndarray],
    camera_id: str,
    frame_index: int,
) -> list:
    """Run a detector on one review frame, returning no candidates on failure."""
    if detector is None or image is None:
        return []
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        frame = Frame(
            camera_id=camera_id,
            frame_index=frame_index,
            t_capture_monotonic_ns=0,
            image=gray,
            width=gray.shape[1],
            height=gray.shape[0],
            pixfmt="GRAY8",
        )
        return detector.detect(frame)
    except (cv2.error, PitchTrackerError, ValueError, TypeError, IndexError) as exc:
        logger.warning(f"{camera_id.capitalize()} detection failed: {exc}")
        return []


def detector_config_dict(config: DetectorConfig) -> dict:
    """Serialize the supported review detector settings."""
    return {
        "detector": {
            "type": config.type,
            "mode": config.mode,
            "frame_diff_threshold": config.frame_diff_threshold,
            "bg_diff_threshold": config.bg_diff_threshold,
            "bg_alpha": config.bg_alpha,
            "edge_threshold": config.edge_threshold,
            "blob_threshold": config.blob_threshold,
            "runtime_budget_ms": config.runtime_budget_ms,
            "crop_padding_px": config.crop_padding_px,
            "min_consecutive": config.min_consecutive,
            "filters": {
                "min_area": config.filters.min_area,
                "max_area": config.filters.max_area,
                "min_circularity": config.filters.min_circularity,
                "max_circularity": config.filters.max_circularity,
                "min_velocity": config.filters.min_velocity,
                "max_velocity": config.filters.max_velocity,
            },
        }
    }

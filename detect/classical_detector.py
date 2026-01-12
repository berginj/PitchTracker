"""Classical CV detector using frame differencing and blob filters."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from contracts import Detection, Frame
from detect.config import DetectorConfig, Mode
from detect.detector import Detector, DetectorHealth
from detect.filters import apply_filters
from detect.modes import detect_mode_a, detect_mode_b
from detect.types import BlobDetection, to_contract_detection


@dataclass
class _CameraState:
    prev_frame: Optional[np.ndarray] = None
    background: Optional[np.ndarray] = None
    last_detection_ns: int = 0
    last_centroid: Optional[tuple[float, float]] = None
    consecutive_hits: int = 0


class ClassicalDetector(Detector):
    def __init__(
        self,
        config: Optional[DetectorConfig] = None,
        mode: Mode = Mode.MODE_A,
        roi_by_camera: Optional[Dict[str, list[tuple[float, float]]]] = None,
    ) -> None:
        self._config = config or DetectorConfig()
        self._mode = mode
        self._state_by_camera: Dict[str, _CameraState] = {}
        self._roi_by_camera = roi_by_camera or {}

    def detect(self, frame: Frame) -> List[Detection]:
        state = self._state_by_camera.setdefault(frame.camera_id, _CameraState())
        image = frame.image
        crop = self._crop_for_camera(frame.camera_id, image)
        if crop is None:
            cropped = image
            offset = (0, 0)
        else:
            cropped, offset = crop
        if self._mode == Mode.MODE_A:
            blobs, background = detect_mode_a(
                cropped, state.prev_frame, state.background, self._config
            )
            state.background = background
        else:
            blobs, background = detect_mode_b(cropped, state.background, self._config)
            state.background = background
        state.prev_frame = cropped

        for blob in blobs:
            if state.last_centroid is not None:
                dx = blob.centroid[0] - state.last_centroid[0]
                dy = blob.centroid[1] - state.last_centroid[1]
                blob.velocity = (dx * dx + dy * dy) ** 0.5
        filtered: List[BlobDetection] = apply_filters(
            blobs, self._config.filters, lanes=None
        )
        detections: List[Detection] = []
        for blob in filtered:
            if offset != (0, 0):
                blob = _offset_blob(blob, offset)
            confidence = min(1.0, max(blob.circularity, 0.0))
            detections.append(
                to_contract_detection(
                    blob=blob,
                    camera_id=frame.camera_id,
                    frame_index=frame.frame_index,
                    t_capture_monotonic_ns=frame.t_capture_monotonic_ns,
                    confidence=confidence,
                )
            )
        if detections:
            state.last_detection_ns = frame.t_capture_monotonic_ns
            best = max(filtered, key=lambda det: det.area, default=None)
            if best is not None:
                state.last_centroid = best.centroid
            state.consecutive_hits += 1
        else:
            state.consecutive_hits = 0
        if state.consecutive_hits < self._config.min_consecutive:
            return []
        return detections

    def health(self) -> DetectorHealth:
        now_ns = time.monotonic_ns()
        last_detection = max(
            (state.last_detection_ns for state in self._state_by_camera.values()),
            default=0,
        )
        if last_detection == 0:
            last_detection = now_ns
        return DetectorHealth(false_positive_rate_hz=0.0, last_detection_ns=last_detection)

    def _crop_for_camera(
        self, camera_id: str, image: np.ndarray
    ) -> Optional[tuple[np.ndarray, tuple[int, int]]]:
        polygon = self._roi_by_camera.get(camera_id)
        if not polygon:
            return None
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        if not xs or not ys:
            return None
        pad = int(self._config.crop_padding_px)
        x1 = max(int(min(xs)) - pad, 0)
        y1 = max(int(min(ys)) - pad, 0)
        x2 = min(int(max(xs)) + pad, image.shape[1] - 1)
        y2 = min(int(max(ys)) + pad, image.shape[0] - 1)
        if x2 - x1 < 2 or y2 - y1 < 2:
            return None
        return image[y1:y2, x1:x2], (x1, y1)


def _offset_blob(blob: BlobDetection, offset: tuple[int, int]) -> BlobDetection:
    dx, dy = offset
    x, y = blob.centroid
    bx1, by1, bx2, by2 = blob.bbox
    return BlobDetection(
        centroid=(x + dx, y + dy),
        area=blob.area,
        perimeter=blob.perimeter,
        bbox=(bx1 + dx, by1 + dy, bx2 + dx, by2 + dy),
        circularity=blob.circularity,
        velocity=blob.velocity,
    )

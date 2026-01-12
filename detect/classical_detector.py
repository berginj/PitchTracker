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


class ClassicalDetector(Detector):
    def __init__(
        self,
        config: Optional[DetectorConfig] = None,
        mode: Mode = Mode.MODE_A,
    ) -> None:
        self._config = config or DetectorConfig()
        self._mode = mode
        self._state_by_camera: Dict[str, _CameraState] = {}

    def detect(self, frame: Frame) -> List[Detection]:
        state = self._state_by_camera.setdefault(frame.camera_id, _CameraState())
        image = frame.image
        if self._mode == Mode.MODE_A:
            blobs, background = detect_mode_a(
                image, state.prev_frame, state.background, self._config
            )
            state.background = background
        else:
            blobs, background = detect_mode_b(image, state.background, self._config)
            state.background = background
        state.prev_frame = image

        filtered: List[BlobDetection] = apply_filters(
            blobs, self._config.filters, lanes=None
        )
        detections: List[Detection] = []
        for blob in filtered:
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

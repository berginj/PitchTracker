from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import time

import numpy as np

from detect.config import DetectorConfig, Mode
from detect.filters import apply_filters
from detect.modes import detect_mode_a, detect_mode_b
from detect.types import Detection, Lanes
from detect import telemetry


@dataclass
class DetectorState:
    prev_frame: np.ndarray | None = None
    background: np.ndarray | None = None
    prev_detections: list[Detection] | None = None
    prev_timestamp: float | None = None


class Detector:
    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()
        self._states: dict[str, DetectorState] = {}

    def detect(
        self,
        frame: np.ndarray,
        *,
        camera_id: str,
        mode: Mode,
        lanes: Lanes | None = None,
        timestamp: float | None = None,
    ) -> list[Detection]:
        start = time.perf_counter()
        state = self._states.get(camera_id, DetectorState())
        if mode == Mode.MODE_A:
            detections, background = detect_mode_a(
                frame, state.prev_frame, state.background, self.config
            )
        elif mode == Mode.MODE_B:
            detections, background = detect_mode_b(frame, state.background, self.config)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        now_ts = timestamp or time.time()
        if state.prev_detections and state.prev_timestamp is not None:
            dt = max(now_ts - state.prev_timestamp, 1e-6)
            _assign_velocities(detections, state.prev_detections, dt)

        detections = apply_filters(detections, self.config.filters, lanes)

        state.prev_frame = frame
        state.background = background
        state.prev_detections = detections
        state.prev_timestamp = now_ts
        self._states[camera_id] = state

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        telemetry.log_timing(camera_id, mode.value, elapsed_ms, self.config.runtime_budget_ms)
        return detections


def _assign_velocities(
    detections: Iterable[Detection],
    prev_detections: Iterable[Detection],
    dt: float,
) -> None:
    prev_list = list(prev_detections)
    if not prev_list:
        return
    for det in detections:
        closest = min(
            prev_list,
            key=lambda prev: _distance(det.centroid, prev.centroid),
        )
        det.velocity = _distance(det.centroid, closest.centroid) / dt


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5

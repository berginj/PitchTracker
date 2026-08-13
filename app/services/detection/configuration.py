"""Detector, threading, ROI, and evidence configuration helpers."""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from app.pipeline.detection.threading_pool import DetectionThreadPool
from contracts.evidence import DecisionArtifactBindings
from detect.config import DetectorConfig, Mode
from detect.lane import LaneGate, LaneRoi
from log_config.logger import get_logger
from stereo import StereoLaneGate

if TYPE_CHECKING:
    from app.services.detection.implementation import DetectionServiceImpl

logger = get_logger(__name__)


class DetectionConfiguration:
    """Configure infrastructure owned by the detection service facade."""

    def __init__(self, service: DetectionServiceImpl) -> None:
        self._service = service

    def configure_detectors(
        self,
        config: DetectorConfig,
        mode: Mode,
        detector_type: str,
        model_path: Optional[str],
        model_input_size: Tuple[int, int],
        model_conf_threshold: float,
        model_class_id: int,
        model_format: str,
    ) -> None:
        service = self._service
        with service._lock:
            initializer = service._initializer
            initializer._detector_config = config
            initializer._detector_mode = mode
            initializer._detector_type = detector_type
            initializer._detector_model_path = model_path
            initializer._detector_model_input_size = model_input_size
            initializer._detector_model_conf_threshold = model_conf_threshold
            initializer._detector_model_class_id = model_class_id
            initializer._detector_model_format = model_format
            detectors = initializer.build_detectors(left_id="left", right_id="right", lane_polygon=None)
            service._left_detector = detectors["left"]
            service._right_detector = detectors["right"]
            service._decision_bindings_cache = None
            logger.info(f"Detectors configured: type={detector_type}, mode={mode}")

    def configure_threading(self, mode: str, worker_count: int) -> None:
        service = self._service
        with service._lock:
            if mode not in ("per_camera", "worker_pool"):
                raise ValueError(f"Invalid threading mode: {mode}")
            if worker_count <= 0:
                raise ValueError(f"Invalid worker_count: {worker_count}")
            if service._thread_pool is None:
                service._thread_pool = DetectionThreadPool(mode, worker_count)
            else:
                service._thread_pool.set_mode(mode, worker_count)
            logger.info(f"Threading configured: mode={mode}, workers={worker_count}")

    def build_gates(
        self,
    ) -> tuple[Optional[LaneGate], Optional[LaneGate], Optional[StereoLaneGate], Optional[StereoLaneGate]]:
        service = self._service
        lane_gate = _build_lane_gate(service._lane_rois)
        plate_gate = _build_lane_gate(service._plate_rois)
        stereo_gate = StereoLaneGate(lane_gate) if lane_gate is not None else None
        plate_stereo_gate = StereoLaneGate(plate_gate) if plate_gate is not None else None
        return lane_gate, plate_gate, stereo_gate, plate_stereo_gate

    def decision_bindings(self, algorithm_name: str, algorithm_version: str) -> DecisionArtifactBindings:
        service = self._service
        base = service._decision_bindings_cache
        if base is None:
            config_payload = json.dumps(asdict(service._config), sort_keys=True, default=str).encode("utf-8")
            roi_payload = json.dumps(
                {"lane": service._lane_rois, "plate": service._plate_rois},
                sort_keys=True,
                default=str,
            ).encode("utf-8")
            detector = service._left_detector
            detector_name = None if detector is None else f"{detector.__class__.__module__}.{detector.__class__.__name__}"
            model_path_raw = getattr(service._initializer, "_detector_model_path", None)
            model_path = None if not model_path_raw else Path(str(model_path_raw))
            base = DecisionArtifactBindings(
                config_sha256=hashlib.sha256(config_payload).hexdigest(),
                calibration_sha256=_file_sha256(service._calibration_path),
                roi_sha256=hashlib.sha256(roi_payload).hexdigest(),
                detector_name=detector_name,
                detector_version=str(getattr(detector, "version", "unknown")) if detector is not None else None,
                model_sha256=_file_sha256(model_path),
            )
            service._decision_bindings_cache = base
        return replace(base, algorithm_name=algorithm_name, algorithm_version=algorithm_version)


def _build_lane_gate(roi_map: Optional[Dict[str, List[Tuple[float, float]]]]) -> Optional[LaneGate]:
    if not roi_map:
        return None
    return LaneGate(roi_by_camera={key: LaneRoi(polygon=list(points)) for key, points in roi_map.items()})


def _file_sha256(path: Optional[Path]) -> Optional[str]:
    if path is None or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()

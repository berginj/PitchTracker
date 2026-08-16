"""Configuration setter mixin for InProcessPipelineService."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, cast

from contracts import Detection, StereoObservation
from detect.config import DetectorConfig as CvDetectorConfig, Mode
from log_config.logger import get_logger
from metrics.strike_zone import StrikeResult

logger = get_logger(__name__)


class _PipelineServiceState:
    """Shared state supplied by InProcessPipelineService's other mixins."""

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)


class PipelineServiceConfigMixin(_PipelineServiceState):
    """Configuration and query methods extracted from InProcessPipelineService."""

    def set_detector_config(
        self,
        config: CvDetectorConfig,
        mode: Mode,
        detector_type: str = "classical",
        model_path: Optional[str] = None,
        model_input_size: Tuple[int, int] = (640, 640),
        model_conf_threshold: float = 0.25,
        model_class_id: int = 0,
        model_format: str = "yolo_v5",
    ) -> None:
        self._initializer.update_detector_config(
            config,
            mode,
            detector_type,
            model_path,
            model_input_size,
            model_conf_threshold,
            model_class_id,
            model_format,
        )
        left_id, right_id = self._camera_mgr.get_camera_ids()
        if left_id and right_id:
            self._detectors_by_camera = self._initializer.build_detectors(left_id, right_id, self._lane_polygon)

    def set_detection_threading(self, mode: str, worker_count: int) -> None:
        if mode not in ("per_camera", "worker_pool"):
            raise ValueError(f"Unknown detection threading mode: {mode}")

        if self._detection_pool:
            is_running = self._detection_pool.is_running()
            if is_running:
                self._detection_pool.stop()
            self._detection_pool.set_mode(mode, worker_count)
            if is_running:
                self._detection_pool.start(queue_size=self._detect_queue_size)

    def get_latest_detections(self) -> Dict[str, list[Detection]]:
        if self._detection_processor:
            return cast(Dict[str, list[Detection]], self._detection_processor.get_latest_detections())
        return {}

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, list[Detection]]]:
        if self._detection_processor:
            return cast(Dict[str, Dict[str, list[Detection]]], self._detection_processor.get_latest_gated_detections())
        return {}

    def get_strike_result(self) -> StrikeResult:
        if self._detection_processor:
            return cast(StrikeResult, self._detection_processor.get_strike_result())
        return StrikeResult(is_strike=False, sample_count=0)

    def is_capturing(self) -> bool:
        """Check if cameras are currently capturing."""
        return bool(self._camera_mgr.is_capturing())

    def set_ball_type(self, ball_type: str) -> None:
        if self._config_service is not None:
            self._config_service.set_ball_type(ball_type)

    def set_batter_height_in(self, height_in: float) -> None:
        if self._config_service is not None:
            self._config_service.update_batter_height(height_in)
            self._config = self._config_service.get_config()
            if self._pitch_analyzer:
                self._pitch_analyzer.update_config(self._config)

    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        if self._config_service is not None:
            self._config_service.update_strike_zone_ratios(top_ratio, bottom_ratio)
            self._config = self._config_service.get_config()
            if self._pitch_analyzer:
                self._pitch_analyzer.update_config(self._config)

    def get_session_summary(self):
        with self._record_lock:
            return self._last_session_summary

    def get_recent_pitch_paths(self) -> list[list[StereoObservation]]:
        if self._session_manager:
            return [list(path) for path in self._session_manager.get_recent_paths()]
        return []

    def get_session_dir(self) -> Optional[Path]:
        if self._session_recorder:
            return cast(Optional[Path], self._session_recorder.get_session_dir())
        return None

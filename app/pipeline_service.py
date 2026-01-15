"""In-process pipeline service to back the UI."""

from __future__ import annotations

import time
import csv
import json
import threading
import queue
from pathlib import Path
from collections import deque
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, Optional, Tuple, List

import cv2
import numpy as np

from capture import CameraDevice, SimulatedCamera, UvcCamera
from capture.camera_device import CameraStats
from capture.opencv_backend import OpenCVCamera
from configs.settings import AppConfig
from configs.roi_io import load_rois
from configs.lane_io import load_lane_rois
from contracts import Detection, Frame, PitchMetrics, StereoObservation
from contracts.versioning import APP_VERSION, SCHEMA_VERSION
from detect.classical_detector import ClassicalDetector
from detect.ml_detector import MlDetector
from detect.config import DetectorConfig as CvDetectorConfig
from detect.config import FilterConfig, Mode
from detect.lane import LaneGate, LaneRoi
from metrics.simple_metrics import (
    PlateMetricsStub,
    compute_plate_from_observations,
    compute_plate_stub,
)
from metrics.strike_zone import StrikeResult, build_strike_zone, is_strike
from record.recorder import RecordingBundle
from stereo import StereoLaneGate
from stereo.association import StereoMatch
from stereo.simple_stereo import SimpleStereoMatcher, StereoGeometry
from track.simple_tracker import SimpleTracker
from integrations.radar import RadarGunClient, NullRadarGun


@dataclass(frozen=True)
class CalibrationProfile:
    profile_id: str
    created_utc: str
    schema_version: str


@dataclass(frozen=True)
class PitchSummary:
    pitch_id: str
    t_start_ns: int
    t_end_ns: int
    is_strike: bool
    zone_row: Optional[int]
    zone_col: Optional[int]
    run_in: float
    rise_in: float
    speed_mph: Optional[float]
    rotation_rpm: Optional[float]
    sample_count: int


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    pitch_count: int
    strikes: int
    balls: int
    heatmap: List[List[int]]
    pitches: List[PitchSummary]


class PipelineService(ABC):
    @abstractmethod
    def start_capture(self, config: AppConfig, left_serial: str, right_serial: str) -> None:
        """Start capture on both cameras."""

    @abstractmethod
    def stop_capture(self) -> None:
        """Stop capture on both cameras."""

    @abstractmethod
    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        """Return the latest frames for UI preview."""

    @abstractmethod
    def start_recording(
        self,
        pitch_id: Optional[str] = None,
        session_name: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> None:
        """Begin recording frames and metadata."""

    @abstractmethod
    def set_record_directory(self, path: Optional[Path]) -> None:
        """Set base directory for recordings."""

    @abstractmethod
    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        """Set manual speed from external device."""

    @abstractmethod
    def stop_recording(self) -> RecordingBundle:
        """Stop recording and return the bundle."""

    @abstractmethod
    def run_calibration(self, profile_id: str) -> CalibrationProfile:
        """Run calibration and return a profile summary."""

    @abstractmethod
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Return capture stats for both cameras."""

    @abstractmethod
    def get_plate_metrics(self) -> PlateMetricsStub:
        """Return latest plate-gated metrics (stubbed if unavailable)."""

    @abstractmethod
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
        """Update detector configuration for the active session."""

    @abstractmethod
    def set_detection_threading(self, mode: str, worker_count: int) -> None:
        """Set detection threading mode ("per_camera" or "worker_pool")."""

    @abstractmethod
    def get_latest_detections(self) -> Dict[str, list[Detection]]:
        """Return latest raw detections by camera id."""

    @abstractmethod
    def get_latest_gated_detections(self) -> Dict[str, Dict[str, list[Detection]]]:
        """Return latest gated detections by camera id and gate name."""

    @abstractmethod
    def get_strike_result(self) -> StrikeResult:
        """Return latest strike determination."""

    @abstractmethod
    def set_ball_type(self, ball_type: str) -> None:
        """Set ball type for strike detection."""

    @abstractmethod
    def set_batter_height_in(self, height_in: float) -> None:
        """Set batter height for strike zone calculation."""

    @abstractmethod
    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        """Set strike zone top/bottom ratios for the active session."""

    @abstractmethod
    def get_session_summary(self) -> SessionSummary:
        """Return the latest session summary."""

    @abstractmethod
    def get_session_dir(self) -> Optional[Path]:
        """Return the current session directory if available."""


class InProcessPipelineService(PipelineService):
    def __init__(self, backend: str = "uvc", radar_client: Optional[RadarGunClient] = None) -> None:
        self._backend = backend
        self._left: Optional[CameraDevice] = None
        self._right: Optional[CameraDevice] = None
        self._left_id: Optional[str] = None
        self._right_id: Optional[str] = None
        self._lane_gate: Optional[LaneGate] = None
        self._plate_gate: Optional[LaneGate] = None
        self._stereo_gate: Optional[StereoLaneGate] = None
        self._plate_stereo_gate: Optional[StereoLaneGate] = None
        self._detector_config = CvDetectorConfig()
        self._detector_mode = Mode.MODE_A
        self._detector_type = "classical"
        self._detector_model_path: Optional[str] = None
        self._detector_model_input_size: Tuple[int, int] = (640, 640)
        self._detector_model_conf_threshold = 0.25
        self._detector_model_class_id = 0
        self._detector_model_format = "yolo_v5"
        self._detectors_by_camera: Dict[str, object] = {}
        self._lane_polygon: Optional[list[tuple[float, float]]] = None
        self._stereo: Optional[SimpleStereoMatcher] = None
        self._tracker = SimpleTracker()
        self._plate_observations = deque(maxlen=12)
        self._current_pitch_observations: List[StereoObservation] = []
        self._recording = False
        self._recorded_frames: list[Frame] = []
        self._pitch_id = "pitch-unknown"
        self._config: Optional[AppConfig] = None
        self._last_plate_metrics = PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)
        self._last_detections: Dict[str, list[Detection]] = {}
        self._last_gated: Dict[str, Dict[str, list[Detection]]] = {}
        self._strike_result = StrikeResult(is_strike=False, sample_count=0)
        self._ball_type = "baseball"
        self._record_dir: Optional[Path] = None
        self._record_session: Optional[str] = None
        self._record_mode: Optional[str] = None
        self._record_left_writer = None
        self._record_right_writer = None
        self._record_left_csv = None
        self._record_right_csv = None
        self._session_left_writer = None
        self._session_right_writer = None
        self._session_left_csv = None
        self._session_right_csv = None
        self._session_dir: Optional[Path] = None
        self._radar_client: RadarGunClient = radar_client or NullRadarGun()
        self._pitch_left_writer = None
        self._pitch_right_writer = None
        self._pitch_left_csv = None
        self._pitch_right_csv = None
        self._pitch_post_end_ns: Optional[int] = None
        self._pitch_latest_ns: Dict[str, int] = {"left": 0, "right": 0}
        self._pre_roll_ns = 0
        self._post_roll_ns = 0
        self._pre_roll_left: deque[Frame] = deque()
        self._pre_roll_right: deque[Frame] = deque()
        self._manual_speed_mph: Optional[float] = None
        self._record_lock = threading.Lock()
        self._detect_lock = threading.Lock()
        self._capture_running = False
        self._left_thread: Optional[threading.Thread] = None
        self._right_thread: Optional[threading.Thread] = None
        self._detection_mode = "per_camera"
        self._detection_worker_count = 2
        self._detection_running = False
        self._detector_threads: List[threading.Thread] = []
        self._worker_threads: List[threading.Thread] = []
        self._stereo_thread: Optional[threading.Thread] = None
        self._detect_queue_size = 6
        self._left_detect_queue: queue.Queue[Frame] = queue.Queue()
        self._right_detect_queue: queue.Queue[Frame] = queue.Queue()
        self._detect_result_queue: queue.Queue[Tuple[str, Frame, list[Detection]]] = queue.Queue()
        self._detector_busy: Dict[str, bool] = {"left": False, "right": False}
        self._detector_busy_lock = threading.Lock()
        self._left_latest: Optional[Frame] = None
        self._right_latest: Optional[Frame] = None
        self._latest_lock = threading.Lock()
        self._session_active = False
        self._pitch_active = False
        self._pitch_active_frames = 0
        self._pitch_gap_frames = 0
        self._pitch_index = 0
        self._pitch_start_ns = 0
        self._pitch_end_ns = 0
        self._session_pitches: List[PitchSummary] = []
        self._last_session_summary = SessionSummary(
            session_id="session",
            pitch_count=0,
            strikes=0,
            balls=0,
            heatmap=[[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            pitches=[],
        )

    def start_capture(self, config: AppConfig, left_serial: str, right_serial: str) -> None:
        self._config = config
        self._left_id = left_serial
        self._right_id = right_serial
        self._ball_type = config.ball.type
        self._record_dir = Path(config.recording.output_dir)
        self._detect_queue_size = config.camera.queue_depth or 6
        self._left = self._build_camera()
        self._right = self._build_camera()
        self._left.open(left_serial)
        self._right.open(right_serial)
        self._configure_camera(self._left, config)
        self._configure_camera(self._right, config)
        self._load_rois()
        self._init_detector(config)
        self._init_stereo(config)
        self._start_capture_threads()
        self._start_detection_threads()

    def stop_capture(self) -> None:
        self._capture_running = False
        self._stop_detection_threads()
        if self._left_thread is not None:
            self._left_thread.join(timeout=1.0)
            self._left_thread = None
        if self._right_thread is not None:
            self._right_thread.join(timeout=1.0)
            self._right_thread = None
        if self._left is not None:
            self._left.close()
            self._left = None
        if self._right is not None:
            self._right.close()
            self._right = None

    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        if self._left is None or self._right is None:
            raise RuntimeError("Capture not started.")
        with self._latest_lock:
            left_frame = self._left_latest
            right_frame = self._right_latest
        if left_frame is None or right_frame is None:
            raise RuntimeError("Waiting for camera frames.")
        return left_frame, right_frame

    def start_recording(
        self,
        pitch_id: Optional[str] = None,
        session_name: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> None:
        self._recording = True
        self._recorded_frames = []
        if pitch_id:
            self._pitch_id = pitch_id
        else:
            self._pitch_id = time.strftime("pitch-%Y%m%d-%H%M%S", time.gmtime())
        self._record_session = session_name
        self._record_mode = mode
        self._session_active = True
        self._session_pitches = []
        self._pitch_index = 0
        self._pitch_active = False
        self._pitch_active_frames = 0
        self._pitch_gap_frames = 0
        self._current_pitch_observations = []
        self._last_session_summary = _build_session_summary(
            self._record_session or "session",
            self._session_pitches,
        )
        self._start_recording_io()

    def set_record_directory(self, path: Optional[Path]) -> None:
        self._record_dir = path

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        self._manual_speed_mph = speed_mph

    def stop_recording(self) -> RecordingBundle:
        self._recording = False
        if self._pitch_active:
            self._finalize_pitch(self._pitch_end_ns or time.monotonic_ns())
        self._session_active = False
        self._stop_recording_io()
        metrics = PitchMetrics(
            pitch_id=self._pitch_id,
            t_start_ns=0,
            t_end_ns=0,
            velo_mph=0.0,
            HB_in=0.0,
            iVB_in=0.0,
            release_xyz_ft=(0.0, 0.0, 0.0),
            approach_angles_deg=(0.0, 0.0),
            confidence=0.0,
        )
        return RecordingBundle(
            pitch_id=self._pitch_id,
            frames=[],
            detections=[],
            track=[],
            metrics=metrics,
        )

    def run_calibration(self, profile_id: str) -> CalibrationProfile:
        created_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return CalibrationProfile(profile_id=profile_id, created_utc=created_utc, schema_version="1.0.0")

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        if self._left is None or self._right is None:
            return {}
        return {
            "left": _stats_to_dict(self._left.get_stats()),
            "right": _stats_to_dict(self._right.get_stats()),
        }

    def get_plate_metrics(self) -> PlateMetricsStub:
        with self._detect_lock:
            return self._last_plate_metrics

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
        self._detector_config = config
        self._detector_mode = mode
        self._detector_type = detector_type
        self._detector_model_path = model_path
        self._detector_model_input_size = model_input_size
        self._detector_model_conf_threshold = model_conf_threshold
        self._detector_model_class_id = model_class_id
        self._detector_model_format = model_format
        self._rebuild_detectors()

    def set_detection_threading(self, mode: str, worker_count: int) -> None:
        if mode not in ("per_camera", "worker_pool"):
            raise ValueError(f"Unknown detection threading mode: {mode}")
        self._detection_mode = mode
        self._detection_worker_count = max(1, int(worker_count))
        if self._capture_running:
            self._stop_detection_threads()
            self._start_detection_threads()

    def get_latest_detections(self) -> Dict[str, list[Detection]]:
        with self._detect_lock:
            return dict(self._last_detections)

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, list[Detection]]]:
        with self._detect_lock:
            return {key: dict(value) for key, value in self._last_gated.items()}

    def get_strike_result(self) -> StrikeResult:
        with self._detect_lock:
            return self._strike_result

    def set_ball_type(self, ball_type: str) -> None:
        self._ball_type = ball_type

    def set_batter_height_in(self, height_in: float) -> None:
        if self._config is None:
            return
        updated = self._config.strike_zone.__class__(
            batter_height_in=height_in,
            top_ratio=self._config.strike_zone.top_ratio,
            bottom_ratio=self._config.strike_zone.bottom_ratio,
            plate_width_in=self._config.strike_zone.plate_width_in,
            plate_length_in=self._config.strike_zone.plate_length_in,
        )
        self._config = self._config.__class__(
            camera=self._config.camera,
            stereo=self._config.stereo,
            tracking=self._config.tracking,
            metrics=self._config.metrics,
            recording=self._config.recording,
            ui=self._config.ui,
            telemetry=self._config.telemetry,
            detector=self._config.detector,
            strike_zone=updated,
            ball=self._config.ball,
        )

    def set_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        if self._config is None:
            return
        updated = self._config.strike_zone.__class__(
            batter_height_in=self._config.strike_zone.batter_height_in,
            top_ratio=top_ratio,
            bottom_ratio=bottom_ratio,
            plate_width_in=self._config.strike_zone.plate_width_in,
            plate_length_in=self._config.strike_zone.plate_length_in,
        )
        self._config = self._config.__class__(
            camera=self._config.camera,
            stereo=self._config.stereo,
            tracking=self._config.tracking,
            metrics=self._config.metrics,
            recording=self._config.recording,
            ui=self._config.ui,
            telemetry=self._config.telemetry,
            detector=self._config.detector,
            strike_zone=updated,
            ball=self._config.ball,
        )

    def get_session_summary(self) -> SessionSummary:
        return self._last_session_summary

    def get_session_dir(self) -> Optional[Path]:
        return self._session_dir

    def _build_camera(self) -> CameraDevice:
        if self._backend == "opencv":
            return OpenCVCamera()
        if self._backend == "sim":
            return SimulatedCamera()
        return UvcCamera()

    def _start_capture_threads(self) -> None:
        if self._left is None or self._right is None:
            return
        self._capture_running = True
        self._left_thread = threading.Thread(
            target=self._capture_loop,
            args=("left", self._left),
            daemon=True,
        )
        self._right_thread = threading.Thread(
            target=self._capture_loop,
            args=("right", self._right),
            daemon=True,
        )
        self._left_thread.start()
        self._right_thread.start()

    def _capture_loop(self, label: str, camera: CameraDevice) -> None:
        while self._capture_running:
            try:
                frame = camera.read_frame(timeout_ms=200)
            except Exception:
                continue
            with self._latest_lock:
                if label == "left":
                    self._left_latest = frame
                else:
                    self._right_latest = frame
            if self._recording:
                self._write_record_frame_single(label, frame)
            self._enqueue_detection_frame(label, frame)

    def _reset_detection_queues(self) -> None:
        self._left_detect_queue = queue.Queue(maxsize=self._detect_queue_size)
        self._right_detect_queue = queue.Queue(maxsize=self._detect_queue_size)
        self._detect_result_queue = queue.Queue(maxsize=self._detect_queue_size * 4)

    @staticmethod
    def _queue_put_drop_oldest(target: queue.Queue, item) -> None:
        try:
            target.put_nowait(item)
            return
        except queue.Full:
            pass
        try:
            target.get_nowait()
        except queue.Empty:
            pass
        try:
            target.put_nowait(item)
        except queue.Full:
            pass

    def _enqueue_detection_frame(self, label: str, frame: Frame) -> None:
        if not self._detection_running:
            return
        target = self._left_detect_queue if label == "left" else self._right_detect_queue
        self._queue_put_drop_oldest(target, frame)

    def _start_detection_threads(self) -> None:
        if self._detection_running:
            return
        if self._left is None or self._right is None:
            return
        self._reset_detection_queues()
        self._detection_running = True
        self._detector_busy = {"left": False, "right": False}
        self._detector_threads = []
        self._worker_threads = []
        self._stereo_thread = threading.Thread(target=self._stereo_loop, daemon=True)
        self._stereo_thread.start()
        if self._detection_mode == "per_camera":
            self._detector_threads = [
                threading.Thread(
                    target=self._detection_loop_per_camera,
                    args=("left", self._left_detect_queue),
                    daemon=True,
                ),
                threading.Thread(
                    target=self._detection_loop_per_camera,
                    args=("right", self._right_detect_queue),
                    daemon=True,
                ),
            ]
            for thread in self._detector_threads:
                thread.start()
            return
        for _ in range(max(1, self._detection_worker_count)):
            thread = threading.Thread(target=self._detection_loop_pool, daemon=True)
            self._worker_threads.append(thread)
            thread.start()

    def _stop_detection_threads(self) -> None:
        self._detection_running = False
        for thread in self._detector_threads:
            thread.join(timeout=1.0)
        for thread in self._worker_threads:
            thread.join(timeout=1.0)
        if self._stereo_thread is not None:
            self._stereo_thread.join(timeout=1.0)
        self._detector_threads = []
        self._worker_threads = []
        self._stereo_thread = None

    def _detect_frame(self, label: str, frame: Frame) -> list[Detection]:
        detector = self._detectors_by_camera.get(label)
        if detector is None:
            return []
        try:
            return detector.detect(frame)
        except Exception:
            return []

    def _detection_loop_per_camera(self, label: str, source: queue.Queue) -> None:
        while self._detection_running:
            try:
                frame = source.get(timeout=0.2)
            except queue.Empty:
                continue
            detections = self._detect_frame(label, frame)
            with self._detect_lock:
                self._last_detections[frame.camera_id] = detections
            self._queue_put_drop_oldest(self._detect_result_queue, (label, frame, detections))

    def _detection_loop_pool(self) -> None:
        while self._detection_running:
            handled = False
            for label in ("left", "right"):
                if not self._detection_running:
                    return
                with self._detector_busy_lock:
                    if self._detector_busy.get(label, False):
                        continue
                    source = self._left_detect_queue if label == "left" else self._right_detect_queue
                    try:
                        frame = source.get_nowait()
                    except queue.Empty:
                        continue
                    self._detector_busy[label] = True
                detections = self._detect_frame(label, frame)
                with self._detect_lock:
                    self._last_detections[frame.camera_id] = detections
                self._queue_put_drop_oldest(self._detect_result_queue, (label, frame, detections))
                with self._detector_busy_lock:
                    self._detector_busy[label] = False
                handled = True
            if not handled:
                time.sleep(0.005)

    def _stereo_loop(self) -> None:
        left_buffer: deque[Tuple[Frame, list[Detection]]] = deque(maxlen=6)
        right_buffer: deque[Tuple[Frame, list[Detection]]] = deque(maxlen=6)
        while self._detection_running:
            try:
                label, frame, detections = self._detect_result_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if label == "left":
                left_buffer.append((frame, detections))
            else:
                right_buffer.append((frame, detections))
            self._match_stereo_buffers(left_buffer, right_buffer)

    def _match_stereo_buffers(
        self,
        left_buffer: deque[Tuple[Frame, list[Detection]]],
        right_buffer: deque[Tuple[Frame, list[Detection]]],
    ) -> None:
        while left_buffer and right_buffer:
            left_frame, left_dets = left_buffer[0]
            right_frame, right_dets = right_buffer[0]
            delta = abs(left_frame.t_capture_monotonic_ns - right_frame.t_capture_monotonic_ns)
            tolerance = 0
            if self._config is not None:
                tolerance = int(self._config.stereo.pairing_tolerance_ms * 1e6)
            if tolerance and delta > tolerance:
                if left_frame.t_capture_monotonic_ns < right_frame.t_capture_monotonic_ns:
                    left_buffer.popleft()
                else:
                    right_buffer.popleft()
                continue
            left_buffer.popleft()
            right_buffer.popleft()
            self._update_plate_metrics(left_frame, right_frame, left_dets, right_dets)

    def _start_recording_io(self) -> None:
        if self._config is None:
            return
        base = self._record_session or self._pitch_id
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in base)
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        base_dir = self._record_dir or Path("recordings")
        self._session_dir = base_dir / f"{safe}_{timestamp}"
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._pre_roll_ns = int(self._config.recording.pre_roll_ms * 1e6)
        self._post_roll_ns = int(self._config.recording.post_roll_ms * 1e6)
        self._pre_roll_left.clear()
        self._pre_roll_right.clear()
        self._open_session_recording()

    def _stop_recording_io(self) -> None:
        self._close_pitch_recording(force=True)
        if self._session_dir is None:
            return
        self._close_session_recording()
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "rig_id": None,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pitch_id": self._pitch_id,
            "session": self._record_session,
            "mode": self._record_mode,
            "measured_speed_mph": self._manual_speed_mph,
            "config_path": "configs/default.yaml",
            "calibration_profile_id": None,
            "session_summary": "session_summary.json",
            "session_summary_csv": "session_summary.csv",
            "session_left_video": "session_left.avi",
            "session_right_video": "session_right.avi",
            "session_left_timestamps": "session_left_timestamps.csv",
            "session_right_timestamps": "session_right_timestamps.csv",
        }
        (self._session_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )
        self._write_session_summary()

    def _write_record_frame_single(self, label: str, frame: Frame) -> None:
        if not self._recording:
            return
        self._buffer_pre_roll(label, frame)
        self._write_session_frame(label, frame)
        if self._pitch_active or self._pitch_post_end_ns is not None:
            self._write_pitch_frame(label, frame)

    def _open_session_recording(self) -> None:
        if self._config is None or self._session_dir is None:
            return
        left_path = self._session_dir / "session_left.avi"
        right_path = self._session_dir / "session_right.avi"
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self._session_left_writer = cv2.VideoWriter(
            str(left_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        self._session_right_writer = cv2.VideoWriter(
            str(right_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        left_csv = (self._session_dir / "session_left_timestamps.csv").open("w", newline="")
        right_csv = (self._session_dir / "session_right_timestamps.csv").open("w", newline="")
        self._session_left_csv = (left_csv, csv.writer(left_csv))
        self._session_right_csv = (right_csv, csv.writer(right_csv))
        self._session_left_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )
        self._session_right_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )

    def _close_session_recording(self) -> None:
        with self._record_lock:
            if self._session_left_writer is not None:
                self._session_left_writer.release()
                self._session_left_writer = None
            if self._session_right_writer is not None:
                self._session_right_writer.release()
                self._session_right_writer = None
            if self._session_left_csv is not None:
                self._session_left_csv[0].close()
                self._session_left_csv = None
            if self._session_right_csv is not None:
                self._session_right_csv[0].close()
                self._session_right_csv = None

    def _write_session_frame(self, label: str, frame: Frame) -> None:
        if self._session_left_writer is None or self._session_right_writer is None:
            return
        image = frame.image
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        with self._record_lock:
            if label == "left" and self._session_left_writer is not None:
                self._session_left_writer.write(image)
                if self._session_left_csv is not None:
                    self._session_left_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )
            elif label == "right" and self._session_right_writer is not None:
                self._session_right_writer.write(image)
                if self._session_right_csv is not None:
                    self._session_right_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )

    @staticmethod
    def _configure_camera(camera: CameraDevice, config: AppConfig) -> None:
        camera.set_mode(
            config.camera.width,
            config.camera.height,
            config.camera.fps,
            config.camera.pixfmt,
        )
        camera.set_controls(
            config.camera.exposure_us,
            config.camera.gain,
            config.camera.wb_mode,
            config.camera.wb,
        )

    def _load_rois(self) -> None:
        if self._left_id is None or self._right_id is None:
            return
        rois = load_rois(Path("configs/roi.json"))
        lane = rois.get("lane")
        plate = rois.get("plate")
        lane_rois = load_lane_rois(Path("configs/lane_roi.json"))
        if lane:
            self._lane_polygon = [(float(x), float(y)) for x, y in lane]
            lane_roi_left = LaneRoi(polygon=[(float(x), float(y)) for x, y in lane])
            lane_roi_right = lane_roi_left
            if lane_rois:
                lane_left = lane_rois.get(self._left_id) or lane_rois.get("left")
                lane_right = lane_rois.get(self._right_id) or lane_rois.get("right")
                if lane_left is not None:
                    lane_roi_left = lane_left
                if lane_right is not None:
                    lane_roi_right = lane_right
            self._lane_gate = LaneGate(
                roi_by_camera={self._left_id: lane_roi_left, self._right_id: lane_roi_right}
            )
            self._stereo_gate = StereoLaneGate(lane_gate=self._lane_gate)
        else:
            self._lane_polygon = None
            self._lane_gate = None
            self._stereo_gate = None
        if plate:
            plate_roi = LaneRoi(polygon=[(float(x), float(y)) for x, y in plate])
            self._plate_gate = LaneGate(roi_by_camera={self._left_id: plate_roi, self._right_id: plate_roi})
            self._plate_stereo_gate = StereoLaneGate(lane_gate=self._plate_gate)
        else:
            self._plate_gate = None
            self._plate_stereo_gate = None

    def _init_stereo(self, config: AppConfig) -> None:
        cx = config.stereo.cx
        cy = config.stereo.cy
        if cx is None:
            cx = config.camera.width / 2.0
        if cy is None:
            cy = config.camera.height / 2.0
        geometry = StereoGeometry(
            baseline_ft=config.stereo.baseline_ft,
            focal_length_px=config.stereo.focal_length_px,
            cx=float(cx),
            cy=float(cy),
            epipolar_epsilon_px=float(config.stereo.epipolar_epsilon_px),
            z_min_ft=float(config.stereo.z_min_ft),
            z_max_ft=float(config.stereo.z_max_ft),
        )
        self._stereo = SimpleStereoMatcher(geometry)

    def _init_detector(self, config: AppConfig) -> None:
        cfg = config.detector
        self._detector_type = cfg.type
        self._detector_model_path = cfg.model_path
        self._detector_model_input_size = cfg.model_input_size
        self._detector_model_conf_threshold = cfg.model_conf_threshold
        self._detector_model_class_id = cfg.model_class_id
        self._detector_model_format = cfg.model_format
        filter_cfg = FilterConfig(
            min_area=cfg.filters.min_area,
            max_area=cfg.filters.max_area,
            min_circularity=cfg.filters.min_circularity,
            max_circularity=cfg.filters.max_circularity,
            min_velocity=cfg.filters.min_velocity,
            max_velocity=cfg.filters.max_velocity,
        )
        detector_cfg = CvDetectorConfig(
            frame_diff_threshold=cfg.frame_diff_threshold,
            bg_diff_threshold=cfg.bg_diff_threshold,
            bg_alpha=cfg.bg_alpha,
            edge_threshold=cfg.edge_threshold,
            blob_threshold=cfg.blob_threshold,
            runtime_budget_ms=cfg.runtime_budget_ms,
            crop_padding_px=cfg.crop_padding_px,
            min_consecutive=cfg.min_consecutive,
            filters=filter_cfg,
        )
        self._detector_config = detector_cfg
        self._detector_mode = Mode(cfg.mode)
        self._rebuild_detectors()

    def _rebuild_detectors(self) -> None:
        detectors: Dict[str, object] = {}
        if self._left_id:
            detectors["left"] = self._build_detector_for_camera(self._left_id)
        if self._right_id:
            detectors["right"] = self._build_detector_for_camera(self._right_id)
        self._detectors_by_camera = detectors
        if self._detector_type == "ml":
            self._warmup_detectors()

    def _build_detector_for_camera(self, camera_id: str):
        if self._detector_type == "ml":
            return MlDetector(
                model_path=self._detector_model_path,
                input_size=self._detector_model_input_size,
                conf_threshold=self._detector_model_conf_threshold,
                class_id=self._detector_model_class_id,
                output_format=self._detector_model_format,
            )
        roi_by_camera = {}
        if self._lane_polygon:
            roi_by_camera = {camera_id: self._lane_polygon}
        return ClassicalDetector(
            config=self._detector_config,
            mode=self._detector_mode,
            roi_by_camera=roi_by_camera,
        )

    def _warmup_detectors(self) -> None:
        if self._config is None:
            return
        height = self._config.camera.height
        width = self._config.camera.width
        dummy = np.zeros((height, width), dtype=np.uint8)
        for label, detector in self._detectors_by_camera.items():
            frame = Frame(
                camera_id=label,
                frame_index=0,
                t_capture_monotonic_ns=0,
                image=dummy,
                width=width,
                height=height,
                pixfmt=self._config.camera.pixfmt,
            )
            try:
                detector.detect(frame)
            except Exception:
                continue

    def _update_plate_metrics(
        self,
        left_frame: Frame,
        right_frame: Frame,
        left_detections: list[Detection],
        right_detections: list[Detection],
    ) -> None:
        if self._left_id is None or self._right_id is None:
            return
        if self._stereo is None:
            return
        with self._detect_lock:
            self._last_detections = {
                left_frame.camera_id: left_detections,
                right_frame.camera_id: right_detections,
            }
        detections = left_detections + right_detections
        gated = _gate_detections(self._lane_gate, detections)
        left_gated = [d for d in gated if d.camera_id == self._left_id]
        right_gated = [d for d in gated if d.camera_id == self._right_id]
        plate_left = []
        plate_right = []
        if self._plate_gate is not None:
            plate = _gate_detections(self._plate_gate, gated)
            plate_left = [d for d in plate if d.camera_id == self._left_id]
            plate_right = [d for d in plate if d.camera_id == self._right_id]
        with self._detect_lock:
            self._last_gated = {
                left_frame.camera_id: {
                    "lane": left_gated,
                    "plate": plate_left,
                },
                right_frame.camera_id: {
                    "lane": right_gated,
                    "plate": plate_right,
                },
            }
        if self._config is not None:
            tolerance_ns = int(self._config.stereo.pairing_tolerance_ms * 1e6)
            delta_ns = abs(left_frame.t_capture_monotonic_ns - right_frame.t_capture_monotonic_ns)
            if delta_ns > tolerance_ns:
                with self._detect_lock:
                    self._last_plate_metrics = compute_plate_stub([])
                    self._strike_result = StrikeResult(is_strike=False, sample_count=0)
                return
        matches = _build_stereo_matches(left_gated, right_gated)
        if self._stereo_gate is not None:
            matches = self._stereo_gate.filter_matches(matches)
        if self._plate_stereo_gate is not None:
            plate_matches = self._plate_stereo_gate.filter_matches(matches)
        else:
            plate_matches = []
        observations = []
        for match in plate_matches:
            observations.append(self._stereo.triangulate(match))
        for obs in observations:
            state = self._tracker.update(obs)
            if state.samples:
                self._plate_observations.append(obs)
                if self._pitch_active:
                    self._current_pitch_observations.append(obs)
        if self._plate_observations:
            metrics = compute_plate_from_observations(self._plate_observations)
        else:
            metrics = compute_plate_stub(plate_matches)
        if self._config is not None:
            zone = build_strike_zone(
                plate_z_ft=self._config.metrics.plate_plane_z_ft,
                plate_width_in=self._config.strike_zone.plate_width_in,
                plate_length_in=self._config.strike_zone.plate_length_in,
                batter_height_in=self._config.strike_zone.batter_height_in,
                top_ratio=self._config.strike_zone.top_ratio,
                bottom_ratio=self._config.strike_zone.bottom_ratio,
            )
            radius_in = self._config.ball.radius_in.get(self._ball_type, 1.45)
            strike = is_strike(self._plate_observations, zone, radius_in)
        else:
            strike = StrikeResult(is_strike=False, sample_count=0)
        with self._detect_lock:
            self._last_plate_metrics = metrics
            self._strike_result = strike
        lane_count = len(left_gated) + len(right_gated)
        plate_count = len(plate_left) + len(plate_right)
        obs_count = len(observations)
        frame_ns = max(left_frame.t_capture_monotonic_ns, right_frame.t_capture_monotonic_ns)
        self._update_pitch_state(frame_ns, lane_count, plate_count, obs_count)

    def _update_pitch_state(
        self,
        frame_ns: int,
        lane_count: int,
        plate_count: int,
        obs_count: int,
    ) -> None:
        if not self._session_active or self._config is None:
            return
        min_active = self._config.recording.session_min_active_frames
        end_gap = self._config.recording.session_end_gap_frames
        if self._plate_gate is None:
            active = lane_count > 0
        else:
            active = plate_count > 0 or obs_count > 0
        if active:
            self._pitch_gap_frames = 0
            self._pitch_active_frames += 1
            self._pitch_end_ns = frame_ns
            if not self._pitch_active and self._pitch_active_frames >= min_active:
                self._start_pitch(frame_ns)
        else:
            if self._pitch_active:
                self._pitch_gap_frames += 1
                if self._pitch_gap_frames >= end_gap:
                    self._finalize_pitch(frame_ns)
            else:
                self._pitch_active_frames = 0

    def _start_pitch(self, frame_ns: int) -> None:
        self._pitch_active = True
        self._pitch_start_ns = frame_ns
        self._pitch_index += 1
        self._current_pitch_observations = []
        self._plate_observations.clear()
        session = self._record_session or "session"
        self._pitch_id = f"{session}-pitch-{self._pitch_index:03d}"
        self._open_pitch_recording()

    def _finalize_pitch(self, frame_ns: int) -> None:
        self._pitch_active = False
        self._pitch_active_frames = 0
        self._pitch_gap_frames = 0
        self._pitch_end_ns = frame_ns
        self._pitch_post_end_ns = frame_ns + self._post_roll_ns
        if self._config is None:
            return
        zone = build_strike_zone(
            plate_z_ft=self._config.metrics.plate_plane_z_ft,
            plate_width_in=self._config.strike_zone.plate_width_in,
            plate_length_in=self._config.strike_zone.plate_length_in,
            batter_height_in=self._config.strike_zone.batter_height_in,
            top_ratio=self._config.strike_zone.top_ratio,
            bottom_ratio=self._config.strike_zone.bottom_ratio,
        )
        radius_in = self._config.ball.radius_in.get(self._ball_type, 1.45)
        strike = is_strike(self._current_pitch_observations, zone, radius_in)
        metrics = compute_plate_from_observations(self._current_pitch_observations)
        radar_speed = self._radar_client.latest_speed_mph() if self._manual_speed_mph is None else self._manual_speed_mph
        summary = PitchSummary(
            pitch_id=self._pitch_id,
            t_start_ns=self._pitch_start_ns,
            t_end_ns=self._pitch_end_ns,
            is_strike=strike.is_strike,
            zone_row=strike.zone_row,
            zone_col=strike.zone_col,
            run_in=metrics.run_in,
            rise_in=metrics.rise_in,
            speed_mph=radar_speed,
            rotation_rpm=None,
            sample_count=metrics.sample_count,
        )
        self._session_pitches.append(summary)
        self._last_session_summary = _build_session_summary(
            self._record_session or "session",
            self._session_pitches,
        )
        self._current_pitch_observations = []
        self._write_pitch_manifest(summary)

    def _write_session_summary(self) -> None:
        if self._session_dir is None:
            return
        summary = self._last_session_summary
        path = self._session_dir / "session_summary.json"
        payload = asdict(summary)
        payload["schema_version"] = SCHEMA_VERSION
        payload["app_version"] = APP_VERSION
        path.write_text(json.dumps(payload, indent=2))
        self._write_session_summary_csv(summary)

    def _write_session_summary_csv(self, summary: SessionSummary) -> None:
        if self._session_dir is None:
            return
        path = self._session_dir / "session_summary.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "pitch_id",
                    "t_start_ns",
                    "t_end_ns",
                    "is_strike",
                    "zone_row",
                    "zone_col",
                    "run_in",
                    "rise_in",
                    "speed_mph",
                    "rotation_rpm",
                    "sample_count",
                ]
            )
            for pitch in summary.pitches:
                writer.writerow(
                    [
                        pitch.pitch_id,
                        pitch.t_start_ns,
                        pitch.t_end_ns,
                        int(pitch.is_strike),
                        pitch.zone_row if pitch.zone_row is not None else "",
                        pitch.zone_col if pitch.zone_col is not None else "",
                        f"{pitch.run_in:.3f}",
                        f"{pitch.rise_in:.3f}",
                        f"{pitch.speed_mph:.3f}" if pitch.speed_mph is not None else "",
                        f"{pitch.rotation_rpm:.3f}" if pitch.rotation_rpm is not None else "",
                        pitch.sample_count,
                    ]
                )

    def _pitch_dir(self, pitch_id: str) -> Optional[Path]:
        if self._session_dir is None:
            return None
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in pitch_id)
        pitch_dir = self._session_dir / safe
        pitch_dir.mkdir(parents=True, exist_ok=True)
        return pitch_dir

    def _open_pitch_recording(self) -> None:
        if self._config is None:
            return
        pitch_dir = self._pitch_dir(self._pitch_id)
        if pitch_dir is None:
            return
        left_path = pitch_dir / "left.avi"
        right_path = pitch_dir / "right.avi"
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self._pitch_left_writer = cv2.VideoWriter(
            str(left_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        self._pitch_right_writer = cv2.VideoWriter(
            str(right_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        left_csv = (pitch_dir / "left_timestamps.csv").open("w", newline="")
        right_csv = (pitch_dir / "right_timestamps.csv").open("w", newline="")
        self._pitch_left_csv = (left_csv, csv.writer(left_csv))
        self._pitch_right_csv = (right_csv, csv.writer(right_csv))
        self._pitch_left_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )
        self._pitch_right_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )
        self._pitch_post_end_ns = None
        self._pitch_latest_ns = {"left": 0, "right": 0}
        self._flush_pre_roll()

    def _close_pitch_recording(self, force: bool = False) -> None:
        with self._record_lock:
            if self._pitch_left_writer is not None:
                self._pitch_left_writer.release()
                self._pitch_left_writer = None
            if self._pitch_right_writer is not None:
                self._pitch_right_writer.release()
                self._pitch_right_writer = None
            if self._pitch_left_csv is not None:
                self._pitch_left_csv[0].close()
                self._pitch_left_csv = None
            if self._pitch_right_csv is not None:
                self._pitch_right_csv[0].close()
                self._pitch_right_csv = None
            if force:
                self._pitch_post_end_ns = None
                self._pitch_latest_ns = {"left": 0, "right": 0}

    def _buffer_pre_roll(self, label: str, frame: Frame) -> None:
        buffer = self._pre_roll_left if label == "left" else self._pre_roll_right
        buffer.append(frame)
        cutoff = frame.t_capture_monotonic_ns - self._pre_roll_ns
        while buffer and buffer[0].t_capture_monotonic_ns < cutoff:
            buffer.popleft()

    def _flush_pre_roll(self) -> None:
        for frame in list(self._pre_roll_left):
            self._write_pitch_frame("left", frame)
        for frame in list(self._pre_roll_right):
            self._write_pitch_frame("right", frame)

    def _write_pitch_frame(self, label: str, frame: Frame) -> None:
        if self._pitch_left_writer is None or self._pitch_right_writer is None:
            return
        image = frame.image
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        with self._record_lock:
            if label == "left" and self._pitch_left_writer is not None:
                self._pitch_left_writer.write(image)
                if self._pitch_left_csv is not None:
                    self._pitch_left_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )
                self._pitch_latest_ns["left"] = frame.t_capture_monotonic_ns
            elif label == "right" and self._pitch_right_writer is not None:
                self._pitch_right_writer.write(image)
                if self._pitch_right_csv is not None:
                    self._pitch_right_csv[1].writerow(
                        [frame.camera_id, frame.frame_index, frame.t_capture_monotonic_ns]
                    )
                self._pitch_latest_ns["right"] = frame.t_capture_monotonic_ns
        self._maybe_close_pitch(frame.t_capture_monotonic_ns)

    def _maybe_close_pitch(self, frame_ns: int) -> None:
        if self._pitch_post_end_ns is None:
            return
        left_ns = self._pitch_latest_ns.get("left", 0)
        right_ns = self._pitch_latest_ns.get("right", 0)
        if left_ns >= self._pitch_post_end_ns and right_ns >= self._pitch_post_end_ns:
            self._close_pitch_recording()
            self._pitch_post_end_ns = None
            self._pitch_latest_ns = {"left": 0, "right": 0}

    def _write_pitch_manifest(self, summary: PitchSummary) -> None:
        pitch_dir = self._pitch_dir(summary.pitch_id)
        if pitch_dir is None:
            return
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "rig_id": None,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pitch_id": summary.pitch_id,
            "t_start_ns": summary.t_start_ns,
            "t_end_ns": summary.t_end_ns,
            "is_strike": summary.is_strike,
            "zone_row": summary.zone_row,
            "zone_col": summary.zone_col,
            "run_in": summary.run_in,
            "rise_in": summary.rise_in,
            "measured_speed_mph": summary.speed_mph,
            "rotation_rpm": summary.rotation_rpm,
            "left_video": "left.avi",
            "right_video": "right.avi",
            "left_timestamps": "left_timestamps.csv",
            "right_timestamps": "right_timestamps.csv",
            "config_path": "configs/default.yaml",
        }
        (pitch_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def _stats_to_dict(stats: CameraStats) -> Dict[str, float]:
    return {
        "fps_avg": stats.fps_avg,
        "fps_instant": stats.fps_instant,
        "jitter_p95_ms": stats.jitter_p95_ms,
        "dropped_frames": float(stats.dropped_frames),
        "queue_depth": float(stats.queue_depth),
        "capture_latency_ms": stats.capture_latency_ms,
    }


def _gate_detections(
    lane_gate: Optional[LaneGate], detections: Iterable
) -> list:
    if lane_gate is None:
        return list(detections)
    return lane_gate.filter_detections(detections)


def _build_stereo_matches(
    left_detections: Iterable, right_detections: Iterable
) -> list[StereoMatch]:
    matches: list[StereoMatch] = []
    for left in left_detections:
        for right in right_detections:
            matches.append(
                StereoMatch(
                    left=left,
                    right=right,
                    epipolar_error_px=abs(left.v - right.v),
                    score=min(left.confidence, right.confidence),
                )
            )
    return matches


def _build_session_summary(session_id: str, pitches: List[PitchSummary]) -> SessionSummary:
    heatmap = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    strikes = 0
    balls = 0
    for pitch in pitches:
        if pitch.is_strike:
            strikes += 1
        else:
            balls += 1
        if pitch.zone_row and pitch.zone_col:
            row = max(1, min(3, pitch.zone_row))
            row = 3 - row
            col = max(1, min(3, pitch.zone_col)) - 1
            heatmap[row][col] += 1
    return SessionSummary(
        session_id=session_id,
        pitch_count=len(pitches),
        strikes=strikes,
        balls=balls,
        heatmap=heatmap,
        pitches=list(pitches),
    )

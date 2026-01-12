"""In-process pipeline service to back the UI."""

from __future__ import annotations

import time
import csv
import json
from pathlib import Path
from collections import deque
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import cv2

from capture import CameraDevice, SimulatedCamera, UvcCamera
from capture.camera_device import CameraStats
from capture.opencv_backend import OpenCVCamera
from configs.settings import AppConfig
from configs.roi_io import load_rois
from contracts import Detection, Frame, PitchMetrics
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


@dataclass(frozen=True)
class CalibrationProfile:
    profile_id: str
    created_utc: str
    schema_version: str


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
    def set_detector_config(self, config: CvDetectorConfig, mode: Mode) -> None:
        """Update detector configuration for the active session."""

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


class InProcessPipelineService(PipelineService):
    def __init__(self, backend: str = "uvc") -> None:
        self._backend = backend
        self._left: Optional[CameraDevice] = None
        self._right: Optional[CameraDevice] = None
        self._left_id: Optional[str] = None
        self._right_id: Optional[str] = None
        self._lane_gate: Optional[LaneGate] = None
        self._plate_gate: Optional[LaneGate] = None
        self._stereo_gate: Optional[StereoLaneGate] = None
        self._plate_stereo_gate: Optional[StereoLaneGate] = None
        self._detector = ClassicalDetector(config=CvDetectorConfig(), mode=Mode.MODE_A)
        self._lane_polygon: Optional[list[tuple[float, float]]] = None
        self._stereo: Optional[SimpleStereoMatcher] = None
        self._tracker = SimpleTracker()
        self._plate_observations = deque(maxlen=12)
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
        self._manual_speed_mph: Optional[float] = None

    def start_capture(self, config: AppConfig, left_serial: str, right_serial: str) -> None:
        self._config = config
        self._left_id = left_serial
        self._right_id = right_serial
        self._ball_type = config.ball.type
        self._record_dir = Path(config.recording.output_dir)
        self._left = self._build_camera()
        self._right = self._build_camera()
        self._left.open(left_serial)
        self._right.open(right_serial)
        self._configure_camera(self._left, config)
        self._configure_camera(self._right, config)
        self._load_rois()
        self._init_detector(config)
        self._init_stereo(config)

    def stop_capture(self) -> None:
        if self._left is not None:
            self._left.close()
            self._left = None
        if self._right is not None:
            self._right.close()
            self._right = None

    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        if self._left is None or self._right is None:
            raise RuntimeError("Capture not started.")
        left_frame = self._left.read_frame(timeout_ms=50)
        right_frame = self._right.read_frame(timeout_ms=50)
        self._update_plate_metrics(left_frame, right_frame)
        if self._recording:
            self._recorded_frames.extend([left_frame, right_frame])
            self._write_record_frame(left_frame, right_frame)
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
        self._start_recording_io()

    def set_record_directory(self, path: Optional[Path]) -> None:
        self._record_dir = path

    def set_manual_speed_mph(self, speed_mph: Optional[float]) -> None:
        self._manual_speed_mph = speed_mph

    def stop_recording(self) -> RecordingBundle:
        self._recording = False
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
            frames=self._recorded_frames,
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
        return self._last_plate_metrics

    def set_detector_config(self, config: CvDetectorConfig, mode: Mode) -> None:
        self._detector = ClassicalDetector(config=config, mode=mode)

    def get_latest_detections(self) -> Dict[str, list[Detection]]:
        return dict(self._last_detections)

    def get_latest_gated_detections(self) -> Dict[str, Dict[str, list[Detection]]]:
        return {key: dict(value) for key, value in self._last_gated.items()}

    def get_strike_result(self) -> StrikeResult:
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

    def _build_camera(self) -> CameraDevice:
        if self._backend == "opencv":
            return OpenCVCamera()
        if self._backend == "sim":
            return SimulatedCamera()
        return UvcCamera()

    def _start_recording_io(self) -> None:
        if self._config is None:
            return
        base = self._record_session or self._pitch_id
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in base)
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        base_dir = self._record_dir or Path("recordings")
        self._record_dir = base_dir / f"{safe}_{timestamp}"
        self._record_dir.mkdir(parents=True, exist_ok=True)
        left_path = self._record_dir / "left.avi"
        right_path = self._record_dir / "right.avi"
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self._record_left_writer = cv2.VideoWriter(
            str(left_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        self._record_right_writer = cv2.VideoWriter(
            str(right_path),
            fourcc,
            self._config.camera.fps,
            (self._config.camera.width, self._config.camera.height),
            True,
        )
        left_csv = (self._record_dir / "left_timestamps.csv").open("w", newline="")
        right_csv = (self._record_dir / "right_timestamps.csv").open("w", newline="")
        self._record_left_csv = (left_csv, csv.writer(left_csv))
        self._record_right_csv = (right_csv, csv.writer(right_csv))
        self._record_left_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )
        self._record_right_csv[1].writerow(
            ["camera_id", "frame_index", "t_capture_monotonic_ns"]
        )

    def _stop_recording_io(self) -> None:
        if self._record_left_writer is not None:
            self._record_left_writer.release()
            self._record_left_writer = None
        if self._record_right_writer is not None:
            self._record_right_writer.release()
            self._record_right_writer = None
        if self._record_left_csv is not None:
            self._record_left_csv[0].close()
            self._record_left_csv = None
        if self._record_right_csv is not None:
            self._record_right_csv[0].close()
            self._record_right_csv = None
        if self._record_dir is None:
            return
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "rig_id": None,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pitch_id": self._pitch_id,
            "session": self._record_session,
            "mode": self._record_mode,
            "measured_speed_mph": self._manual_speed_mph,
            "left_video": "left.avi",
            "right_video": "right.avi",
            "left_timestamps": "left_timestamps.csv",
            "right_timestamps": "right_timestamps.csv",
            "config_path": "configs/default.yaml",
            "calibration_profile_id": None,
        }
        (self._record_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )

    def _write_record_frame(self, left: Frame, right: Frame) -> None:
        if self._record_left_writer is None or self._record_right_writer is None:
            return
        left_image = left.image
        right_image = right.image
        if left_image.ndim == 2:
            left_image = cv2.cvtColor(left_image, cv2.COLOR_GRAY2BGR)
        if right_image.ndim == 2:
            right_image = cv2.cvtColor(right_image, cv2.COLOR_GRAY2BGR)
        self._record_left_writer.write(left_image)
        self._record_right_writer.write(right_image)
        if self._record_left_csv is not None:
            self._record_left_csv[1].writerow(
                [left.camera_id, left.frame_index, left.t_capture_monotonic_ns]
            )
        if self._record_right_csv is not None:
            self._record_right_csv[1].writerow(
                [right.camera_id, right.frame_index, right.t_capture_monotonic_ns]
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
        if lane:
            self._lane_polygon = [(float(x), float(y)) for x, y in lane]
            lane_roi = LaneRoi(polygon=[(float(x), float(y)) for x, y in lane])
            self._lane_gate = LaneGate(roi_by_camera={self._left_id: lane_roi, self._right_id: lane_roi})
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
        if cfg.type == "ml":
            self._detector = MlDetector(model_path=cfg.model_path)
            return
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
        mode = Mode(cfg.mode)
        roi_by_camera = {}
        if self._lane_polygon and self._left_id and self._right_id:
            roi_by_camera = {
                self._left_id: self._lane_polygon,
                self._right_id: self._lane_polygon,
            }
        self._detector = ClassicalDetector(
            config=detector_cfg,
            mode=mode,
            roi_by_camera=roi_by_camera,
        )

    def _update_plate_metrics(self, left_frame: Frame, right_frame: Frame) -> None:
        if self._left_id is None or self._right_id is None:
            return
        if self._stereo is None:
            return
        left_detections = self._detector.detect(left_frame)
        right_detections = self._detector.detect(right_frame)
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
        if self._plate_observations:
            self._last_plate_metrics = compute_plate_from_observations(self._plate_observations)
        else:
            self._last_plate_metrics = compute_plate_stub(plate_matches)
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
            self._strike_result = is_strike(self._plate_observations, zone, radius_in)


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

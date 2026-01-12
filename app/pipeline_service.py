"""In-process pipeline service to back the UI."""

from __future__ import annotations

import time
from pathlib import Path
from collections import deque
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from capture import CameraDevice, SimulatedCamera, UvcCamera
from capture.camera_device import CameraStats
from capture.opencv_backend import OpenCVCamera
from configs.settings import AppConfig
from configs.roi_io import load_rois
from contracts import Frame, PitchMetrics
from detect.lane import LaneGate, LaneRoi
from detect.simple_detector import CenterDetector
from metrics.simple_metrics import (
    PlateMetricsStub,
    compute_plate_from_observations,
    compute_plate_stub,
)
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
    def start_recording(self, pitch_id: Optional[str] = None) -> None:
        """Begin recording frames and metadata."""

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
        self._detector = CenterDetector()
        self._stereo: Optional[SimpleStereoMatcher] = None
        self._tracker = SimpleTracker()
        self._plate_observations = deque(maxlen=12)
        self._recording = False
        self._recorded_frames: list[Frame] = []
        self._pitch_id = "pitch-unknown"
        self._config: Optional[AppConfig] = None
        self._last_plate_metrics = PlateMetricsStub(run_in=0.0, rise_in=0.0, sample_count=0)

    def start_capture(self, config: AppConfig, left_serial: str, right_serial: str) -> None:
        self._config = config
        self._left_id = left_serial
        self._right_id = right_serial
        self._left = self._build_camera()
        self._right = self._build_camera()
        self._left.open(left_serial)
        self._right.open(right_serial)
        self._configure_camera(self._left, config)
        self._configure_camera(self._right, config)
        self._load_rois()
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
        return left_frame, right_frame

    def start_recording(self, pitch_id: Optional[str] = None) -> None:
        self._recording = True
        self._recorded_frames = []
        if pitch_id:
            self._pitch_id = pitch_id
        else:
            self._pitch_id = time.strftime("pitch-%Y%m%d-%H%M%S", time.gmtime())

    def stop_recording(self) -> RecordingBundle:
        self._recording = False
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

    def _build_camera(self) -> CameraDevice:
        if self._backend == "opencv":
            return OpenCVCamera()
        if self._backend == "sim":
            return SimulatedCamera()
        return UvcCamera()

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
            lane_roi = LaneRoi(polygon=[(float(x), float(y)) for x, y in lane])
            self._lane_gate = LaneGate(roi_by_camera={self._left_id: lane_roi, self._right_id: lane_roi})
            self._stereo_gate = StereoLaneGate(lane_gate=self._lane_gate)
        else:
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

    def _update_plate_metrics(self, left_frame: Frame, right_frame: Frame) -> None:
        if self._left_id is None or self._right_id is None:
            return
        if self._stereo is None:
            return
        detections = self._detector.detect(left_frame) + self._detector.detect(right_frame)
        gated = _gate_detections(self._lane_gate, detections)
        left_gated = [d for d in gated if d.camera_id == self._left_id]
        right_gated = [d for d in gated if d.camera_id == self._right_id]
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

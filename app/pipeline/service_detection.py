"""Detection, stereo, and pitch-event callbacks for the legacy pipeline service."""

from __future__ import annotations

from typing import List

from app.events import ErrorCategory, ErrorSeverity, publish_error
from app.pipeline.pitch_tracking_v2 import PitchData
from app.pipeline.recording.pitch_recorder import PitchRecorder
from contracts import Detection, Frame, StereoObservation
from log_config.logger import get_logger

logger = get_logger(__name__)


class PipelineServiceDetectionMixin:
    """Detection and pitch-event behavior for InProcessPipelineService."""

    def _on_camera_state_changed(self, camera_id: str, state) -> None:
        from app.camera import CameraState

        if state == CameraState.RECONNECTING:
            logger.info(f"🔄 Camera {camera_id} disconnected, attempting reconnection...")
        elif state == CameraState.CONNECTED:
            logger.info(f"✅ Camera {camera_id} reconnected successfully")
        elif state == CameraState.FAILED:
            logger.error(f"❌ Camera {camera_id} reconnection failed permanently")
        elif state == CameraState.DISCONNECTED:
            logger.warning(f"⚠️ Camera {camera_id} disconnected")

    def _on_frame_captured(self, label: str, frame: Frame) -> None:
        if self._pitch_tracker and self._session_active:
            self._pitch_tracker.buffer_frame(label, frame)

        if self._recording:
            self._write_record_frame_single(label, frame)

        if self._detection_pool:
            self._detection_pool.enqueue_frame(label, frame)

    def _detect_frame(self, label: str, frame: Frame) -> list[Detection]:
        detector = self._detectors_by_camera.get(label)
        if detector is None:
            return []
        try:
            return detector.detect(frame)
        except Exception as exc:
            logger.error(
                f"Detection failed for {label} camera: {exc.__class__.__name__}: {exc}",
                exc_info=True,
            )
            error_type = exc.__class__.__name__
            if "memory" in str(exc).lower() or "allocation" in str(exc).lower():
                user_msg = (
                    f"Detection failed on {label} camera due to memory issue. "
                    "Try closing other applications."
                )
            elif "model" in str(exc).lower():
                user_msg = (
                    f"Detection model error on {label} camera. "
                    "Switch to classical detector in settings."
                )
            else:
                user_msg = (
                    f"Detection failed on {label} camera: {error_type}. "
                    "Check logs for details."
                )

            publish_error(
                category=ErrorCategory.DETECTION,
                severity=ErrorSeverity.ERROR,
                message=user_msg,
                source=f"PipelineService.{label}",
                exception=exc,
                camera=label,
            )
            return []

    def _on_detection_result(self, label: str, frame: Frame, detections: list[Detection]) -> None:
        if self._pitch_recorder and self._pitch_recorder.is_active() and detections:
            self._pitch_recorder.write_frame_with_detections(label, frame, detections)

        if self._detection_processor:
            self._detection_processor.process_detection_result(label, frame, detections)

    def _on_stereo_pair(
        self,
        left_frame: Frame,
        right_frame: Frame,
        left_detections: list[Detection],
        right_detections: list[Detection],
        observations: List[StereoObservation],
        lane_count: int,
        plate_count: int,
    ) -> None:
        del left_detections, right_detections
        if self._pitch_tracker:
            for obs in observations:
                self._pitch_tracker.add_observation(obs)
                if self._pitch_recorder and self._pitch_recorder.is_active():
                    self._pitch_recorder.add_observation(obs)

            frame_ns = max(left_frame.t_capture_monotonic_ns, right_frame.t_capture_monotonic_ns)
            self._pitch_tracker.update(frame_ns, lane_count, plate_count, len(observations))

    def _on_pitch_start(self, pitch_index: int, pitch_data: PitchData) -> None:
        session = self._record_session or "session"
        with self._record_lock:
            self._pitch_id = f"{session}-pitch-{pitch_index:03d}"

        if self._config and self._session_recorder:
            session_dir = self._session_recorder.get_session_dir()
            if session_dir:
                recorder = PitchRecorder(self._config, session_dir, self._pitch_id)
                recorder.start_pitch()
                for cam_label, frame in pitch_data.pre_roll_frames:
                    recorder.write_frame(cam_label, frame)
                with self._record_lock:
                    self._pitch_recorder = recorder

    def _on_pitch_end(self, pitch_data: PitchData) -> None:
        if self._pitch_analyzer is None or self._session_manager is None:
            return

        observations = pitch_data.observations
        start_ns = pitch_data.start_ns
        end_ns = pitch_data.end_ns

        summary = self._pitch_analyzer.analyze_pitch(
            pitch_id=self._pitch_id,
            start_ns=start_ns,
            end_ns=end_ns,
            observations=observations,
        )

        self._session_manager.add_pitch(summary, observations)
        with self._record_lock:
            self._last_session_summary = self._session_manager.get_summary()
            self._last_pitch_summary = summary

        if self._pitch_recorder:
            self._pitch_recorder.end_pitch(end_ns)
            duration_ns = end_ns - start_ns
            performance_metrics = {
                "detection_quality": {
                    "stereo_observations": len(observations),
                    "detection_rate_hz": (
                        float(len(observations)) / (duration_ns / 1e9)
                        if duration_ns > 0
                        else 0.0
                    ),
                    "observation_duration_ms": summary.observation_duration_ms,
                    "observation_max_gap_ms": summary.observation_max_gap_ms,
                    "observation_z_span_ft": summary.observation_z_span_ft,
                    "observation_mean_confidence": summary.observation_mean_confidence,
                },
                "timing_accuracy": {
                    "pre_roll_frames_captured": len(pitch_data.pre_roll_frames),
                    "duration_ns": duration_ns,
                    "start_ns": start_ns,
                    "end_ns": end_ns,
                },
            }

            config_path = str(self._config_path) if self._config_path else None
            self._pitch_recorder.write_manifest(summary, config_path, performance_metrics)

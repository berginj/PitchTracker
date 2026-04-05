"""Recording helpers for the legacy in-process pipeline service."""

from __future__ import annotations

from app.pipeline.analysis.pitch_summary import PitchAnalyzer
from app.pipeline.analysis.session_summary import SessionManager
from app.pipeline.pitch_tracking_v2 import PitchConfig, PitchStateMachineV2
from app.pipeline.recording.calibration_export import export_calibration_metadata
from app.pipeline.recording.session_recorder import SessionRecorder
from contracts import Frame
from log_config.logger import get_logger

logger = get_logger(__name__)


class PipelineServiceRecordingMixin:
    """Recording IO helpers for InProcessPipelineService."""

    def _start_recording_io(self) -> str:
        if self._config is None:
            return ""

        self._session_recorder = SessionRecorder(self._config, self._record_dir)
        self._session_recorder.set_disk_error_callback(self._on_disk_critical)

        session_dir, warning = self._session_recorder.start_session(
            self._record_session or "session",
            self._pitch_id,
        )

        if session_dir:
            left_serial = (
                getattr(self._camera_mgr._left, "_serial", "left")
                if self._camera_mgr and self._camera_mgr._left
                else "left"
            )
            right_serial = (
                getattr(self._camera_mgr._right, "_serial", "right")
                if self._camera_mgr and self._camera_mgr._right
                else "right"
            )
            export_calibration_metadata(
                session_dir=session_dir,
                stereo=self._stereo,
                left_camera_id=left_serial,
                right_camera_id=right_serial,
                lane_gate=self._lane_gate,
                plate_gate=self._plate_gate,
            )
            logger.info(f"Exported calibration metadata to {session_dir / 'calibration'}")

        self._pitch_analyzer = PitchAnalyzer(
            config=self._config,
            get_ball_radius_fn=lambda: (
                self._config_service.get_ball_radius_in() if self._config_service else 1.45
            ),
            radar_speed_fn=lambda: (
                self._radar_client.latest_speed_mph()
                if self._manual_speed_mph is None
                else self._manual_speed_mph
            ),
        )

        self._session_manager = SessionManager(self._record_session or "session")

        pitch_config = PitchConfig(
            min_active_frames=self._config.recording.session_min_active_frames,
            end_gap_frames=self._config.recording.session_end_gap_frames,
            use_plate_gate=self._plate_gate is not None,
            min_observations=3,
            min_duration_ms=100.0,
            pre_roll_ms=float(self._config.recording.pre_roll_ms),
            frame_rate=float(self._config.camera.fps),
        )
        self._pitch_tracker = PitchStateMachineV2(pitch_config)
        self._pitch_tracker.set_callbacks(
            on_pitch_start=self._on_pitch_start,
            on_pitch_end=self._on_pitch_end,
        )

        return warning

    def _stop_recording_io(self) -> None:
        if self._pitch_recorder:
            self._pitch_recorder.close(force=True)
            self._pitch_recorder = None

        if self._session_recorder:
            config_path = str(self._config_path) if self._config_path else None
            self._session_recorder.stop_session(
                config_path,
                self._pitch_id,
                self._record_session,
                self._record_mode,
                self._manual_speed_mph,
            )
            self._write_session_summary()

    def _write_record_frame_single(self, label: str, frame: Frame) -> None:
        if not self._recording:
            return
        if self._session_recorder:
            self._session_recorder.write_frame(label, frame)
        if self._pitch_recorder and self._pitch_recorder.is_active():
            self._pitch_recorder.write_frame(label, frame)
            if self._pitch_recorder.should_close():
                self._pitch_recorder.close()
                self._pitch_recorder = None

    def _write_session_summary(self) -> None:
        if self._session_recorder:
            self._session_recorder.write_session_summary(self._last_session_summary)

    def _on_disk_critical(self, free_gb: float, message: str) -> None:
        del free_gb
        logger.critical(f"Disk critical callback triggered: {message}")

        if self._recording:
            logger.warning("Auto-stopping recording due to critical disk space")
            try:
                self.stop_recording()
            except Exception as exc:
                logger.error(f"Error stopping recording on disk critical: {exc}")

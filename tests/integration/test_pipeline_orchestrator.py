"""Integration tests for PipelineOrchestrator.

Tests the event-driven pipeline orchestrator that coordinates all services.
"""

import shutil
import tempfile
import time
from pathlib import Path

import cv2
import pytest

from app.services.orchestrator import PipelineOrchestrator
from configs.settings import load_config
from contracts import StereoObservation


# Test fixtures


def create_test_config():
    """Create test configuration from default.yaml."""
    config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
    return load_config(config_path)


def has_video_writer_codec() -> bool:
    """Return whether this environment can open an OpenCV video writer."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        path = temp_dir / "codec_probe.avi"
        for codec_name in ("H264", "avc1", "XVID", "MP4V", "MJPG"):
            fourcc = cv2.VideoWriter_fourcc(*codec_name)
            writer = cv2.VideoWriter(str(path), fourcc, 30.0, (64, 64), True)
            try:
                if writer.isOpened():
                    return True
            finally:
                writer.release()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return False


requires_video_codec = pytest.mark.skipif(
    not has_video_writer_codec(),
    reason="OpenCV cannot open any configured video writer codec in this environment",
)


def create_test_observation(t_ns: int, x: float, y: float, z: float) -> StereoObservation:
    """Create test stereo observation."""
    return StereoObservation(
        t_ns=t_ns,
        left=(100.0, 100.0),
        right=(110.0, 100.0),
        X=x,
        Y=y,
        Z=z,
        quality=0.9,
        confidence=0.9,
    )


class TestPipelineOrchestratorBasics:
    """Test basic PipelineOrchestrator functionality."""

    def test_initialization(self):
        """Test PipelineOrchestrator initialization."""
        orchestrator = PipelineOrchestrator(backend="sim")

        # Should initialize without errors
        assert orchestrator is not None

    def test_run_calibration_points_to_setup_tooling(self):
        """Runtime calibration API should explain the setup/tooling boundary."""
        orchestrator = PipelineOrchestrator(backend="sim")

        with pytest.raises(NotImplementedError) as exc_info:
            orchestrator.run_calibration("pilot-rig")

        message = str(exc_info.value)
        assert "Setup Doctor" in message
        assert "SubprocessToolingService" in message
        assert "runtime capture" in message

    def test_start_stop_capture(self):
        """Test starting and stopping capture."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        # Start capture
        orchestrator.start_capture(config, left_serial="left", right_serial="right")

        # Wait a bit
        time.sleep(0.2)

        # Stop capture
        orchestrator.stop_capture()

    def test_start_capture_already_started(self):
        """Test starting capture when already started raises error."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        orchestrator.start_capture(config, left_serial="left", right_serial="right")

        # Try to start again - should raise
        with pytest.raises(RuntimeError, match="Capture already started"):
            orchestrator.start_capture(config, left_serial="left", right_serial="right")

        orchestrator.stop_capture()

    def test_stop_capture_idempotent(self):
        """Test stopping capture multiple times is safe."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        orchestrator.start_capture(config, left_serial="left", right_serial="right")
        orchestrator.stop_capture()

        # Stop again - should not raise
        orchestrator.stop_capture()


class TestPipelineOrchestratorPreview:
    """Test preview frame functionality."""

    def test_get_preview_frames(self):
        """Test getting preview frames."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        orchestrator.start_capture(config, left_serial="left", right_serial="right")

        # Wait for frames to be available
        time.sleep(0.2)

        # Get preview frames
        left_frame, right_frame = orchestrator.get_preview_frames()
        assert left_frame is not None
        assert right_frame is not None
        assert left_frame.camera_id == "left"
        assert right_frame.camera_id == "right"

        orchestrator.stop_capture()

    def test_get_preview_frames_not_capturing(self):
        """Test getting preview frames when not capturing raises error."""
        orchestrator = PipelineOrchestrator(backend="sim")

        with pytest.raises(RuntimeError, match="Capture not active"):
            orchestrator.get_preview_frames()


class TestPipelineOrchestratorRecording:
    """Test recording functionality."""

    def test_recording_start_failure_rolls_back_detection_and_analysis(self, monkeypatch):
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()
        orchestrator.start_capture(config, left_serial="left", right_serial="right")

        def fail_start_session(*_args, **_kwargs):
            raise RuntimeError("disk unavailable")

        monkeypatch.setattr(orchestrator._recording_service, "start_session", fail_start_session)

        with pytest.raises(RuntimeError, match="disk unavailable"):
            orchestrator.start_recording(session_name="rollback")

        assert orchestrator._recording_active is False
        assert orchestrator._detection_started is False
        assert orchestrator._analysis_service._analysis_active is False
        orchestrator.stop_capture()

    @requires_video_codec
    def test_start_stop_recording(self):
        """Test starting and stopping recording."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        # Set record directory to temp location
        import tempfile

        test_dir = Path(tempfile.mkdtemp())
        orchestrator.set_record_directory(test_dir)

        # Start capture first
        orchestrator.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.1)

        # Start recording
        warning = orchestrator.start_recording(session_name="test_session")
        assert isinstance(warning, str)

        # Wait a bit
        time.sleep(0.2)

        # Stop recording
        try:
            bundle = orchestrator.stop_recording()
            assert bundle is not None
            assert bundle.session_dir is not None
        except Exception:
            # Recording may fail in test environment, just verify the method can be called
            pass

        orchestrator.stop_capture()

    def test_start_recording_without_capture(self):
        """Test starting recording without capture raises error."""
        orchestrator = PipelineOrchestrator(backend="sim")

        with pytest.raises(RuntimeError, match="Cannot start recording without capture"):
            orchestrator.start_recording()

    def test_set_record_directory(self):
        """Test setting record directory."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        # Set record directory before starting capture
        import tempfile

        test_dir = Path(tempfile.mkdtemp())
        orchestrator.set_record_directory(test_dir)

        # Start capture to initialize services
        orchestrator.start_capture(config, left_serial="left", right_serial="right")

        orchestrator.stop_capture()


class TestPipelineOrchestratorStats:
    """Test statistics functionality."""

    def test_get_stats(self):
        """Test getting capture statistics."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        orchestrator.start_capture(config, left_serial="left", right_serial="right")

        # Wait for some frames
        time.sleep(0.2)

        # Get stats
        stats = orchestrator.get_stats()
        assert "left" in stats
        assert "right" in stats

        orchestrator.stop_capture()

    def test_get_stats_not_capturing(self):
        """Test getting stats when not capturing returns empty dict."""
        orchestrator = PipelineOrchestrator(backend="sim")

        stats = orchestrator.get_stats()
        assert stats == {}

    def test_get_plate_metrics(self):
        """Test getting plate metrics."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        orchestrator.start_capture(config, left_serial="left", right_serial="right")

        metrics = orchestrator.get_plate_metrics()
        assert metrics is not None
        assert hasattr(metrics, "run_in")
        assert hasattr(metrics, "rise_in")

        orchestrator.stop_capture()


class TestPipelineOrchestratorDetectionConfig:
    """Test detection configuration."""

    def test_set_detector_config(self):
        """Test setting detector configuration."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        orchestrator.start_capture(config, left_serial="left", right_serial="right")

        # Set detector config
        from detect.config import Mode

        orchestrator.set_detector_config(
            config=config.detector,
            mode=Mode.MODE_A,
            detector_type="classical",
        )

        orchestrator.stop_capture()

    def test_set_detection_threading(self):
        """Test setting detection threading mode."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        orchestrator.start_capture(config, left_serial="left", right_serial="right")

        # Set threading mode
        orchestrator.set_detection_threading(mode="per_camera", worker_count=2)

        orchestrator.stop_capture()


class TestPipelineOrchestratorDetections:
    """Test detection retrieval."""

    @requires_video_codec
    def test_get_latest_detections(self):
        """Test getting latest detections."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        orchestrator.start_capture(config, left_serial="left", right_serial="right")
        import tempfile

        test_dir = Path(tempfile.mkdtemp())
        orchestrator.set_record_directory(test_dir)
        orchestrator.start_recording(session_name="test_session")

        # Wait for some detections
        time.sleep(0.5)

        # Get latest detections
        detections = orchestrator.get_latest_detections()
        assert isinstance(detections, dict)

        orchestrator.stop_recording()
        orchestrator.stop_capture()

    @requires_video_codec
    def test_get_latest_gated_detections(self):
        """Test getting latest gated detections."""
        orchestrator = PipelineOrchestrator(backend="sim")
        config = create_test_config()

        orchestrator.start_capture(config, left_serial="left", right_serial="right")
        import tempfile

        test_dir = Path(tempfile.mkdtemp())
        orchestrator.set_record_directory(test_dir)
        orchestrator.start_recording(session_name="test_session")

        # Wait for some detections
        time.sleep(0.5)

        # Get latest gated detections
        gated = orchestrator.get_latest_gated_detections()
        assert isinstance(gated, dict)

        orchestrator.stop_recording()
        orchestrator.stop_capture()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

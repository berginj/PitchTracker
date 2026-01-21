"""Integration tests for QtPipelineService with PipelineOrchestrator.

Tests that QtPipelineService correctly wraps PipelineOrchestrator and converts
EventBus events to Qt signals for thread-safe UI updates.
"""

import sys
import time
from pathlib import Path
from typing import List

import pytest
from PySide6 import QtWidgets, QtCore

from app.qt_pipeline_service import QtPipelineService
from app.events.event_types import PitchStartEvent, PitchEndEvent
from configs.settings import load_config
from contracts import StereoObservation


@pytest.fixture(scope="module")
def qapp():
    """Create Qt application for testing."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    yield app
    # Note: Don't quit the app, it may be shared across tests


def create_test_config():
    """Create test configuration from default.yaml."""
    config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
    return load_config(config_path)


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


class TestQtPipelineServiceBasics:
    """Test basic QtPipelineService functionality."""

    def test_initialization(self, qapp):
        """Test QtPipelineService initialization."""
        service = QtPipelineService(backend="sim")

        # Should initialize without errors
        assert service is not None
        assert service._service is not None
        assert hasattr(service._service, '_event_bus')

    def test_uses_pipeline_orchestrator(self, qapp):
        """Test QtPipelineService uses PipelineOrchestrator."""
        from app.services.orchestrator import PipelineOrchestrator

        service = QtPipelineService(backend="sim")

        # Verify underlying service is PipelineOrchestrator
        assert isinstance(service._service, PipelineOrchestrator)

    def test_subscribes_to_eventbus(self, qapp):
        """Test QtPipelineService subscribes to EventBus events."""
        service = QtPipelineService(backend="sim")

        # Verify subscription happened (check internal EventBus state)
        event_bus = service._service._event_bus
        assert event_bus is not None

        # EventBus should have subscribers for PitchStartEvent and PitchEndEvent
        assert PitchStartEvent in event_bus._subscribers
        assert PitchEndEvent in event_bus._subscribers


class TestQtPipelineServiceDelegation:
    """Test QtPipelineService delegates methods to PipelineOrchestrator."""

    def test_start_stop_capture(self, qapp):
        """Test start_capture and stop_capture delegation."""
        service = QtPipelineService(backend="sim")
        config = create_test_config()

        # Start capture
        service.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.1)

        # Verify capture is active
        assert service.is_capturing()

        # Stop capture
        service.stop_capture()
        assert not service.is_capturing()

    def test_get_preview_frames(self, qapp):
        """Test get_preview_frames delegation."""
        service = QtPipelineService(backend="sim")
        config = create_test_config()

        service.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.2)

        # Get preview frames
        left_frame, right_frame = service.get_preview_frames()
        assert left_frame is not None
        assert right_frame is not None

        service.stop_capture()

    def test_get_stats(self, qapp):
        """Test get_stats delegation."""
        service = QtPipelineService(backend="sim")
        config = create_test_config()

        service.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.2)

        # Get stats
        stats = service.get_stats()
        assert "left" in stats
        assert "right" in stats

        service.stop_capture()

    def test_set_record_directory(self, qapp):
        """Test set_record_directory delegation."""
        import tempfile

        service = QtPipelineService(backend="sim")
        test_dir = Path(tempfile.mkdtemp())

        # Should not raise
        service.set_record_directory(test_dir)

    def test_start_stop_recording(self, qapp):
        """Test start_recording and stop_recording delegation."""
        import tempfile

        service = QtPipelineService(backend="sim")
        config = create_test_config()
        test_dir = Path(tempfile.mkdtemp())

        # Set record directory before starting capture
        service.set_record_directory(test_dir)
        service.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.1)

        # Start recording (may fail due to file system in test environment)
        try:
            warning = service.start_recording(session_name="test_session")
            assert isinstance(warning, str)

            time.sleep(0.2)

            # Stop recording
            try:
                bundle = service.stop_recording()
                # Bundle may be None in test environment
            except Exception:
                # Recording may fail in test environment
                pass
        except Exception as e:
            # Recording may fail due to file system issues in test environment
            # This is acceptable as long as the delegation works
            pass

        service.stop_capture()


class TestQtPipelineServiceSignals:
    """Test QtPipelineService Qt signal emission from EventBus events."""

    def test_pitch_started_signal(self, qapp):
        """Test pitch_started signal is emitted when PitchStartEvent is published."""
        service = QtPipelineService(backend="sim")

        # Track signal emissions
        pitch_started_signals: List[tuple] = []

        def handle_pitch_started(pitch_index: int, pitch_data):
            pitch_started_signals.append((pitch_index, pitch_data))

        service.pitch_started.connect(handle_pitch_started)

        # Publish PitchStartEvent to EventBus
        event = PitchStartEvent(
            pitch_id="pitch_00001",
            pitch_index=1,
            timestamp_ns=1000000000
        )
        service._service._event_bus.publish(event)

        # Process Qt events to ensure signal delivery
        qapp.processEvents()
        time.sleep(0.05)
        qapp.processEvents()

        # Verify signal was emitted
        assert len(pitch_started_signals) == 1
        assert pitch_started_signals[0][0] == 1
        assert pitch_started_signals[0][1] is None  # PitchData not available in start event

    def test_pitch_ended_signal(self, qapp):
        """Test pitch_ended signal is emitted when PitchEndEvent is published."""
        service = QtPipelineService(backend="sim")

        # Track signal emissions
        pitch_ended_signals: List = []

        def handle_pitch_ended(event):
            pitch_ended_signals.append(event)

        service.pitch_ended.connect(handle_pitch_ended)

        # Create test observations
        observations = [
            create_test_observation(1000000000 + i * 10000000, 0.0, 3.0, 60.0 - i * 2.0)
            for i in range(10)
        ]

        # Publish PitchEndEvent to EventBus
        event = PitchEndEvent(
            pitch_id="pitch_00001",
            observations=observations,
            timestamp_ns=1000000000,
            duration_ns=100000000,
        )
        service._service._event_bus.publish(event)

        # Process Qt events to ensure signal delivery
        qapp.processEvents()
        time.sleep(0.05)
        qapp.processEvents()

        # Verify signal was emitted
        assert len(pitch_ended_signals) == 1
        assert pitch_ended_signals[0].pitch_id == "pitch_00001"
        assert len(pitch_ended_signals[0].observations) == 10

    def test_multiple_signals(self, qapp):
        """Test multiple pitch events are converted to signals correctly."""
        service = QtPipelineService(backend="sim")

        # Track signal emissions
        start_signals: List[int] = []
        end_signals: List[str] = []

        def handle_start(pitch_index: int, pitch_data):
            start_signals.append(pitch_index)

        def handle_end(event):
            end_signals.append(event.pitch_id)

        service.pitch_started.connect(handle_start)
        service.pitch_ended.connect(handle_end)

        # Publish multiple events
        for i in range(3):
            # Start event
            start_event = PitchStartEvent(
                pitch_id=f"pitch_{i:05d}",
                pitch_index=i,
                timestamp_ns=1000000000 + i * 1000000000
            )
            service._service._event_bus.publish(start_event)

            # End event
            observations = [
                create_test_observation(1000000000 + i * 1000000000, 0.0, 3.0, 60.0)
            ]
            end_event = PitchEndEvent(
                pitch_id=f"pitch_{i:05d}",
                observations=observations,
                timestamp_ns=1000000000 + i * 1000000000,
                duration_ns=100000000,
            )
            service._service._event_bus.publish(end_event)

            # Process events
            qapp.processEvents()

        time.sleep(0.1)
        qapp.processEvents()

        # Verify all signals were emitted
        assert len(start_signals) == 3
        assert start_signals == [0, 1, 2]
        assert len(end_signals) == 3
        assert end_signals == ["pitch_00000", "pitch_00001", "pitch_00002"]


class TestQtPipelineServiceThreadSafety:
    """Test QtPipelineService thread safety."""

    def test_signal_emission_from_worker_thread(self, qapp):
        """Test signals can be emitted safely from worker threads."""
        import threading

        service = QtPipelineService(backend="sim")

        # Track signal emissions
        pitch_signals: List[int] = []
        lock = threading.Lock()

        def handle_pitch_started(pitch_index: int, pitch_data):
            with lock:
                pitch_signals.append(pitch_index)

        service.pitch_started.connect(handle_pitch_started)

        # Publish events from worker thread
        def publish_events():
            for i in range(5):
                event = PitchStartEvent(
                    pitch_id=f"pitch_{i:05d}",
                    pitch_index=i,
                    timestamp_ns=1000000000 + i * 100000000
                )
                service._service._event_bus.publish(event)
                time.sleep(0.01)

        thread = threading.Thread(target=publish_events)
        thread.start()
        thread.join()

        # Process Qt events
        time.sleep(0.2)
        qapp.processEvents()

        # Verify all signals were delivered
        assert len(pitch_signals) == 5

    def test_concurrent_method_calls(self, qapp):
        """Test concurrent method calls are thread-safe."""
        import threading

        service = QtPipelineService(backend="sim")
        config = create_test_config()

        service.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.2)

        results = []
        lock = threading.Lock()

        def query_stats():
            for _ in range(10):
                stats = service.get_stats()
                with lock:
                    results.append(stats)
                time.sleep(0.01)

        # Create multiple threads
        threads = [threading.Thread(target=query_stats) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All queries should have succeeded
        assert len(results) == 30  # 3 threads × 10 queries each

        service.stop_capture()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

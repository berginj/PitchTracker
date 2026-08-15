"""Integration tests for AnalysisService paths and session behavior."""

import threading
import time
from pathlib import Path

import numpy as np
import pytest

from app.events.event_bus import EventBus
from app.events.event_types import PitchEndEvent
from app.pipeline.pitch_tracking_v2 import PitchData, PitchPhase
from app.services.analysis import AnalysisServiceImpl
from configs.settings import load_config
from contracts import StereoObservation


def create_test_config():
    """Create test configuration from default.yaml."""
    config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
    return load_config(config_path)


def create_test_observation(t_ns: int, x_ft: float, y_ft: float, z_ft: float) -> StereoObservation:
    """Create test stereo observation."""
    return StereoObservation(
        t_ns=t_ns, left=(100.0, 100.0), right=(110.0, 100.0), X=x_ft, Y=y_ft, Z=z_ft, quality=0.9, confidence=0.9
    )


def create_test_pitch_data(pitch_index: int, obs_count: int = 20) -> PitchData:
    """Create test pitch data with observations."""
    start_ns = 1000000000
    end_ns = start_ns + 500000000
    observations = []
    for i in range(obs_count):
        t_ns = start_ns + i * (end_ns - start_ns) // obs_count
        z_ft = 60.0 - (60.0 - 17.0) * i / obs_count
        x_ft = 0.5 * np.sin(i * 0.1)
        y_ft = 3.5 + 0.1 * np.sin(i * 0.2)
        observations.append(create_test_observation(t_ns, x_ft, y_ft, z_ft))
    first_t = observations[0].t_ns if observations else start_ns
    last_t = observations[-1].t_ns if observations else end_ns
    return PitchData(
        pitch_index=pitch_index,
        phase=PitchPhase.FINALIZED,
        start_ns=start_ns,
        end_ns=end_ns,
        first_detection_ns=first_t,
        last_detection_ns=last_t,
        observations=observations,
    )


class TestAnalysisServiceRecentPitchPaths:
    """Test recent pitch paths functionality."""

    def test_get_recent_pitch_paths_empty(self):
        """Test getting recent pitch paths when empty."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)
        paths = service.get_recent_pitch_paths()
        assert paths == []

    def test_get_recent_pitch_paths(self):
        """Test getting recent pitch paths after analysis."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)
        service.start_analysis()
        for i in range(3):
            pitch_data = create_test_pitch_data(i + 1, obs_count=10)
            event = PitchEndEvent(
                pitch_id=f"pitch_{i:03d}",
                observations=pitch_data.observations,
                timestamp_ns=pitch_data.end_ns,
                duration_ns=pitch_data.end_ns - pitch_data.start_ns,
            )
            bus.publish(event)
        assert service.wait_for_idle(timeout=300)
        paths = service.get_recent_pitch_paths()
        assert len(paths) == 3
        assert all(len(path) == 10 for path in paths)
        service.stop_analysis()

    @pytest.mark.timeout(300)
    def test_recent_pitch_paths_max_count(self):
        """Test recent pitch paths respects maximum count.

        Publishes 15 pitches; each triggers a full physics trajectory fit
        (~8s each on the slow drag model), so this needs a larger timeout
        than the default 120s. See trajectory/physics.py perf note.
        """
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)
        service.start_analysis()
        for i in range(15):
            pitch_data = create_test_pitch_data(i + 1, obs_count=10)
            event = PitchEndEvent(
                pitch_id=f"pitch_{i:03d}",
                observations=pitch_data.observations,
                timestamp_ns=pitch_data.end_ns,
                duration_ns=pitch_data.end_ns - pitch_data.start_ns,
            )
            bus.publish(event)
        assert service.wait_for_idle(timeout=300)
        paths = service.get_recent_pitch_paths()
        assert len(paths) == 10
        service.stop_analysis()


class TestAnalysisServicePlateMetrics:
    """Test plate metrics functionality."""

    def test_get_plate_metrics(self):
        """Test getting plate metrics."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)
        metrics = service.get_plate_metrics()
        assert metrics is not None
        assert hasattr(metrics, "run_in")
        assert hasattr(metrics, "rise_in")


class TestAnalysisServiceSessionAnalysis:
    """Test session analysis functionality."""

    def test_analyze_session_not_found(self):
        """Test analyzing non-existent session raises error."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)
        session_path = Path("/nonexistent/session")
        with pytest.raises(FileNotFoundError):
            service.analyze_session(session_path)

    def test_detect_patterns_not_found(self):
        """Test pattern detection on non-existent session raises error."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)
        session_path = Path("/nonexistent/session")
        with pytest.raises(FileNotFoundError):
            service.detect_patterns(session_path)


class TestAnalysisServiceThreadSafety:
    """Test AnalysisService thread safety."""

    def test_concurrent_summary_queries(self):
        """Test multiple threads querying session summary simultaneously."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)
        service.start_analysis()
        results = []
        lock = threading.Lock()

        def query_summary():
            for _ in range(10):
                summary = service.get_session_summary()
                with lock:
                    results.append(summary)
                time.sleep(0.01)

        threads = [threading.Thread(target=query_summary) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(results) == 50
        service.stop_analysis()

    def test_concurrent_config_updates(self):
        """Test multiple threads updating config simultaneously."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        def update_config():
            for _ in range(5):
                service.set_batter_height_in(72.0)
                service.set_ball_type("baseball")
                time.sleep(0.01)

        threads = [threading.Thread(target=update_config) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

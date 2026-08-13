"""Integration tests for AnalysisService.

Tests the event-driven analysis service that manages pitch analysis and session summaries.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.events.event_bus import EventBus
from app.events.event_types import PitchEndEvent
from app.pipeline.pitch_tracking_v2 import PitchData, PitchPhase
from app.services.analysis import AnalysisServiceImpl
from configs.settings import load_config
from contracts import StereoObservation
from metrics.strike_zone import StrikeResult


# Test fixtures


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
    end_ns = start_ns + 500000000  # 500ms duration

    observations = []
    for i in range(obs_count):
        t_ns = start_ns + i * (end_ns - start_ns) // obs_count
        # Simulate pitch trajectory: start at (0, 60), end at (0, 17) at plate (z=0)
        z_ft = 60.0 - (60.0 - 17.0) * i / obs_count
        x_ft = 0.5 * np.sin(i * 0.1)  # Small lateral movement
        y_ft = 3.5 + 0.1 * np.sin(i * 0.2)  # Height variation

        obs = create_test_observation(t_ns, x_ft, y_ft, z_ft)
        observations.append(obs)

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


class TestAnalysisServiceBasics:
    """Test basic AnalysisService functionality."""

    def test_initialization(self):
        """Test AnalysisService initialization."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Service should initialize without starting
        summary = service.get_session_summary()
        assert summary.pitch_count == 0

    def test_start_stop_analysis(self):
        """Test starting and stopping analysis."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Start analysis
        service.start_analysis()
        summary = service.get_session_summary()
        assert summary.session_id == "current"
        assert summary.pitch_count == 0

        # Stop analysis
        service.stop_analysis()

    def test_start_analysis_idempotent(self):
        """Test starting analysis multiple times is safe."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        service.start_analysis()
        service.start_analysis()  # Should not raise

        service.stop_analysis()

    def test_stop_analysis_idempotent(self):
        """Test stopping analysis multiple times is safe."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        service.start_analysis()
        service.stop_analysis()
        service.stop_analysis()  # Should not raise


class TestAnalysisServicePitchAnalysis:
    """Test pitch analysis functionality."""

    def test_analyze_pitch(self):
        """Test analyzing a single pitch."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Create pitch data
        pitch_data = create_test_pitch_data(1, obs_count=20)

        # Analyze pitch
        summary = service.analyze_pitch(pitch_data, config)

        # Verify summary
        assert summary.pitch_id == "pitch_00001"
        # speed_mph may be None if trajectory fit fails with synthetic data
        assert summary.speed_mph is None or summary.speed_mph > 0
        assert summary.is_strike is not None

    def test_analyze_pitch_no_observations(self):
        """Test analyzing pitch with no observations raises error."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Create pitch data with no observations
        pitch_data = PitchData(
            pitch_index=1,
            phase=PitchPhase.FINALIZED,
            start_ns=0,
            end_ns=1000000,
            first_detection_ns=0,
            last_detection_ns=1000000,
            observations=[],
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="Pitch has no observations"):
            service.analyze_pitch(pitch_data, config)

    def test_analyze_pitch_minimal_observations(self):
        """Test analyzing pitch with minimal observations."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Create pitch data with only 3 observations
        pitch_data = create_test_pitch_data(1, obs_count=3)

        # Should complete without raising
        summary = service.analyze_pitch(pitch_data, config)
        assert summary.pitch_id == "pitch_00001"


class TestAnalysisServiceSessionSummary:
    """Test session summary functionality."""

    def test_get_session_summary_not_started(self):
        """Test getting session summary before starting returns empty."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        summary = service.get_session_summary()
        assert summary.session_id == "none"
        assert summary.pitch_count == 0

    def test_session_summary_updates(self):
        """Test session summary updates after analyzing pitches."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        service.start_analysis()

        # Publish pitch events (use event handler to update summary)
        for i in range(5):
            pitch_data = create_test_pitch_data(i + 1, obs_count=15)
            event = PitchEndEvent(
                pitch_id=f"pitch_{i:03d}",
                observations=pitch_data.observations,
                timestamp_ns=pitch_data.end_ns,
                duration_ns=pitch_data.end_ns - pitch_data.start_ns,
            )
            bus.publish(event)

        # Wait for processing
        assert service.wait_for_idle(timeout=300)

        # Check session summary
        session_summary = service.get_session_summary()
        assert session_summary.pitch_count == 5
        usable = [
            pitch
            for pitch in session_summary.pitches
            if pitch.measurement_status not in {"REJECTED", "UNAVAILABLE"}
        ]
        assert session_summary.strikes + session_summary.balls == len(usable)

        service.stop_analysis()


class TestAnalysisServiceStrikeZone:
    """Test strike zone calculation functionality."""

    def test_calculate_strike_result(self):
        """Test calculating strike result for an observation."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Create observation at plate (z=0)
        obs = create_test_observation(t_ns=1000000000, x_ft=0.0, y_ft=3.0, z_ft=0.0)  # Center  # Mid-height  # At plate

        # Calculate strike result
        result = service.calculate_strike_result(obs, config)
        assert isinstance(result, StrikeResult)
        assert result.is_strike is not None

    def test_set_batter_height(self):
        """Test setting batter height."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Set valid height
        service.set_batter_height_in(72.0)

        # Should not raise

    def test_set_batter_height_invalid(self):
        """Test setting invalid batter height raises error."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Too short
        with pytest.raises(ValueError, match="Invalid batter height"):
            service.set_batter_height_in(20.0)

        # Too tall
        with pytest.raises(ValueError, match="Invalid batter height"):
            service.set_batter_height_in(100.0)

    def test_set_strike_zone_ratios(self):
        """Test setting strike zone ratios."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Set valid ratios
        service.set_strike_zone_ratios(top_ratio=0.7, bottom_ratio=0.3)

        # Should not raise

    def test_set_strike_zone_ratios_invalid(self):
        """Test setting invalid strike zone ratios raises error."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # top_ratio < bottom_ratio
        with pytest.raises(ValueError, match="top_ratio"):
            service.set_strike_zone_ratios(top_ratio=0.3, bottom_ratio=0.7)

        # top_ratio out of range
        with pytest.raises(ValueError, match="Invalid top_ratio"):
            service.set_strike_zone_ratios(top_ratio=1.5, bottom_ratio=0.3)

        # bottom_ratio out of range
        with pytest.raises(ValueError, match="Invalid bottom_ratio"):
            service.set_strike_zone_ratios(top_ratio=0.7, bottom_ratio=-0.1)


class TestAnalysisServiceConfiguration:
    """Test configuration functionality."""

    def test_set_ball_type(self):
        """Test setting ball type."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        service.set_ball_type("baseball")
        service.set_ball_type("softball")

        # Should not raise

    def test_initial_ball_type_comes_from_config(self):
        bus = EventBus()
        config = create_test_config()
        config = replace(config, ball=replace(config.ball, type="softball"))

        service = AnalysisServiceImpl(bus, config)

        assert service._get_ball_radius() == config.ball.radius_in["softball"]

    def test_update_config(self):
        """Test updating configuration."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Update config
        new_config = create_test_config()
        service.update_config(new_config)

        # Should not raise


class TestAnalysisServiceEventBusIntegration:
    """Test EventBus integration."""

    def test_pitch_end_event_subscription(self):
        """Test PitchEndEvent triggers automatic analysis."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        # Start analysis (subscribes to events)
        service.start_analysis()

        # Publish PitchEndEvent
        pitch_data = create_test_pitch_data(1, obs_count=20)
        event = PitchEndEvent(
            pitch_id="pitch_001",
            observations=pitch_data.observations,
            timestamp_ns=pitch_data.end_ns,
            duration_ns=pitch_data.end_ns - pitch_data.start_ns,
        )

        bus.publish(event)

        # Wait for processing
        assert service.wait_for_idle(timeout=300)

        # Check session summary updated
        summary = service.get_session_summary()
        assert summary.pitch_count == 1

        service.stop_analysis()

    def test_multiple_pitch_end_events(self):
        """Test multiple PitchEndEvents are processed correctly."""
        bus = EventBus()
        config = create_test_config()
        service = AnalysisServiceImpl(bus, config)

        service.start_analysis()

        # Publish multiple events
        for i in range(5):
            pitch_data = create_test_pitch_data(i + 1, obs_count=15)
            event = PitchEndEvent(
                pitch_id=f"pitch_{i:03d}",
                observations=pitch_data.observations,
                timestamp_ns=pitch_data.end_ns,
                duration_ns=pitch_data.end_ns - pitch_data.start_ns,
            )
            bus.publish(event)

        # Wait for processing
        assert service.wait_for_idle(timeout=300)

        # Check session summary
        summary = service.get_session_summary()
        assert summary.pitch_count == 5

        service.stop_analysis()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

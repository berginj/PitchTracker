"""Tests for app.pipeline.analysis.session_summary module."""

from __future__ import annotations

import pytest

from app.pipeline.analysis.session_summary import SessionManager
from app.pipeline_service import PitchSummary
from contracts import StereoObservation


class TestSessionManager:
    """Tests for SessionManager."""

    @pytest.fixture
    def manager(self):
        """Create session manager."""
        return SessionManager("session-001")

    def test_initial_summary(self, manager):
        """Test initial session summary."""
        summary = manager.get_summary()

        assert summary.session_id == "session-001"
        assert summary.pitch_count == 0
        assert summary.strikes == 0
        assert summary.balls == 0
        assert summary.pitches == []

    def test_add_single_pitch(self, manager):
        """Test adding a single pitch."""
        pitch = PitchSummary(
            pitch_id="pitch-001",
            t_start_ns=1000,
            t_end_ns=2000,
            is_strike=True,
            zone_row=1,
            zone_col=1,
            run_in=2.5,
            rise_in=1.0,
            speed_mph=85.0,
            rotation_rpm=2000.0,
            sample_count=30,
        )
        observations = [
            StereoObservation(
                x_ft=0.0,
                y_ft=0.0,
                z_ft=50.0,
                t_ns=1000,
                x_px_left=100.0,
                y_px_left=100.0,
                x_px_right=90.0,
                y_px_right=100.0,
            )
        ]

        manager.add_pitch(pitch, observations)

        summary = manager.get_summary()
        assert summary.pitch_count == 1
        assert summary.strikes == 1
        assert summary.balls == 0
        assert len(summary.pitches) == 1

    def test_add_multiple_pitches(self, manager):
        """Test adding multiple pitches."""
        strike = PitchSummary(
            pitch_id="pitch-001",
            t_start_ns=1000,
            t_end_ns=2000,
            is_strike=True,
            zone_row=1,
            zone_col=1,
            run_in=2.5,
            rise_in=1.0,
            speed_mph=85.0,
            rotation_rpm=2000.0,
            sample_count=30,
        )
        ball = PitchSummary(
            pitch_id="pitch-002",
            t_start_ns=3000,
            t_end_ns=4000,
            is_strike=False,
            zone_row=0,
            zone_col=0,
            run_in=-1.5,
            rise_in=3.0,
            speed_mph=82.0,
            rotation_rpm=1800.0,
            sample_count=25,
        )

        manager.add_pitch(strike, [])
        manager.add_pitch(ball, [])

        summary = manager.get_summary()
        assert summary.pitch_count == 2
        assert summary.strikes == 1
        assert summary.balls == 1

    def test_recent_paths_limit(self, manager):
        """Test recent paths limited to 12 pitches."""
        for i in range(15):
            pitch = PitchSummary(
                pitch_id=f"pitch-{i:03d}",
                t_start_ns=i * 1000,
                t_end_ns=(i + 1) * 1000,
                is_strike=True,
                zone_row=1,
                zone_col=1,
                run_in=2.5,
                rise_in=1.0,
                speed_mph=85.0,
                rotation_rpm=2000.0,
                sample_count=30,
            )
            observations = [
                StereoObservation(
                    x_ft=0.0,
                    y_ft=0.0,
                    z_ft=50.0,
                    t_ns=i * 1000,
                    x_px_left=100.0,
                    y_px_left=100.0,
                    x_px_right=90.0,
                    y_px_right=100.0,
                )
            ]
            manager.add_pitch(pitch, observations)

        paths = manager.get_recent_paths()
        assert len(paths) == 12  # Limited to 12 most recent

    def test_heatmap_generation(self, manager):
        """Test heatmap generation from pitch locations."""
        # Add pitch to zone (1, 1)
        pitch = PitchSummary(
            pitch_id="pitch-001",
            t_start_ns=1000,
            t_end_ns=2000,
            is_strike=True,
            zone_row=1,
            zone_col=1,
            run_in=2.5,
            rise_in=1.0,
            speed_mph=85.0,
            rotation_rpm=2000.0,
            sample_count=30,
        )

        manager.add_pitch(pitch, [])

        summary = manager.get_summary()
        # Check heatmap has count at (1, 1)
        assert summary.heatmap[1][1] == 1
        # Other cells should be 0
        assert summary.heatmap[0][0] == 0

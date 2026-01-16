"""Pitch analysis for trajectory fitting and summary creation."""

from __future__ import annotations

import logging
from typing import List, Optional

from configs.settings import AppConfig
from contracts import StereoObservation
from metrics.simple_metrics import compute_plate_from_observations
from metrics.strike_zone import StrikeResult, build_strike_zone, is_strike
from trajectory.physics_drag_fitter import PhysicsDragFitter, TrajectoryFitRequest

logger = logging.getLogger(__name__)


class PitchAnalyzer:
    """Analyzes pitch observations to create summary with trajectory and metrics.

    Handles:
    - Strike zone calculation
    - Plate metrics computation
    - Trajectory fitting with physics-based drag model
    - Pitch summary creation
    """

    def __init__(
        self,
        config: AppConfig,
        get_ball_radius_fn,
        radar_speed_fn,
    ):
        """Initialize pitch analyzer.

        Args:
            config: Application configuration
            get_ball_radius_fn: Function to get current ball radius in inches
            radar_speed_fn: Function to get radar speed in mph (or None)
        """
        self._config = config
        self._get_ball_radius_fn = get_ball_radius_fn
        self._radar_speed_fn = radar_speed_fn
        self._trajectory_fitter = PhysicsDragFitter()

    def analyze_pitch(
        self,
        pitch_id: str,
        start_ns: int,
        end_ns: int,
        observations: List[StereoObservation],
    ):
        """Analyze pitch observations and create summary.

        Args:
            pitch_id: Pitch ID
            start_ns: Pitch start timestamp
            end_ns: Pitch end timestamp
            observations: List of stereo observations

        Returns:
            PitchSummary object
        """
        # Import here to avoid circular dependency
        from app.pipeline_service import PitchSummary

        # Compute strike zone
        zone = build_strike_zone(
            plate_z_ft=self._config.metrics.plate_plane_z_ft,
            plate_width_in=self._config.strike_zone.plate_width_in,
            plate_length_in=self._config.strike_zone.plate_length_in,
            batter_height_in=self._config.strike_zone.batter_height_in,
            top_ratio=self._config.strike_zone.top_ratio,
            bottom_ratio=self._config.strike_zone.bottom_ratio,
        )
        radius_in = self._get_ball_radius_fn()
        strike = is_strike(observations, zone, radius_in)

        # Compute plate metrics
        metrics = compute_plate_from_observations(observations)

        # Get radar speed
        radar_speed = self._radar_speed_fn()

        # Fit trajectory
        trajectory_result = None
        if observations:
            trajectory_request = TrajectoryFitRequest(
                observations=list(observations),
                plate_plane_z_ft=self._config.metrics.plate_plane_z_ft,
                radar_speed_mph=radar_speed,
                radar_speed_ref="release",
            )
            trajectory_result = self._trajectory_fitter.fit_trajectory(trajectory_request)

        # Extract plate crossing
        crossing_xyz = trajectory_result.plate_crossing_xyz_ft if trajectory_result else None

        # Create summary
        summary = PitchSummary(
            pitch_id=pitch_id,
            t_start_ns=start_ns,
            t_end_ns=end_ns,
            is_strike=strike.is_strike,
            zone_row=strike.zone_row,
            zone_col=strike.zone_col,
            run_in=metrics.run_in,
            rise_in=metrics.rise_in,
            speed_mph=radar_speed,
            rotation_rpm=None,
            sample_count=metrics.sample_count,
            trajectory_plate_x_ft=crossing_xyz[0] if crossing_xyz else None,
            trajectory_plate_y_ft=crossing_xyz[1] if crossing_xyz else None,
            trajectory_plate_z_ft=crossing_xyz[2] if crossing_xyz else None,
            trajectory_plate_t_ns=trajectory_result.plate_crossing_t_ns if trajectory_result else None,
            trajectory_model=trajectory_result.model_name if trajectory_result else None,
            trajectory_expected_error_ft=trajectory_result.expected_plate_error_ft if trajectory_result else None,
            trajectory_confidence=trajectory_result.confidence if trajectory_result else None,
        )

        return summary

    def update_config(self, config: AppConfig) -> None:
        """Update configuration.

        Args:
            config: New application configuration
        """
        self._config = config

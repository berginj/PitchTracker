"""Configuration service for runtime configuration management."""

from __future__ import annotations

import threading
from typing import Optional

from configs.settings import AppConfig


class ConfigService:
    """Thread-safe configuration management service.

    Manages runtime configuration updates for strike zone, ball type, and
    other mutable configuration parameters. Uses immutable config updates
    to ensure thread safety.
    """

    def __init__(self, config: AppConfig):
        """Initialize configuration service.

        Args:
            config: Initial application configuration
        """
        self._config = config
        self._ball_type = config.ball.type if config.ball else "baseball"
        self._lock = threading.Lock()

    def get_config(self) -> AppConfig:
        """Get current configuration (thread-safe).

        Returns:
            Current AppConfig instance
        """
        with self._lock:
            return self._config

    def set_ball_type(self, ball_type: str) -> None:
        """Set ball type for radius lookup.

        Args:
            ball_type: Ball type identifier (e.g., "baseball", "softball")
        """
        with self._lock:
            self._ball_type = ball_type

    def get_ball_type(self) -> str:
        """Get current ball type.

        Returns:
            Current ball type identifier
        """
        with self._lock:
            return self._ball_type

    def get_ball_radius_in(self) -> float:
        """Get current ball radius in inches.

        Returns:
            Ball radius in inches based on current ball type and config
        """
        with self._lock:
            if self._config.ball is None:
                return 1.45  # Default baseball radius

            # Get radius for current ball type from config dict
            return self._config.ball.radius_in.get(self._ball_type, 1.45)

    def update_batter_height(self, height_in: float) -> None:
        """Update strike zone with new batter height.

        Creates new immutable config with updated strike zone.

        Args:
            height_in: Batter height in inches
        """
        with self._lock:
            if self._config is None or self._config.strike_zone is None:
                return

            # Create new strike zone with updated height
            updated_zone = self._config.strike_zone.__class__(
                batter_height_in=height_in,
                top_ratio=self._config.strike_zone.top_ratio,
                bottom_ratio=self._config.strike_zone.bottom_ratio,
                plate_width_in=self._config.strike_zone.plate_width_in,
                plate_length_in=self._config.strike_zone.plate_length_in,
            )

            # Create new config with updated strike zone
            self._config = self._config.__class__(
                camera=self._config.camera,
                stereo=self._config.stereo,
                tracking=self._config.tracking,
                metrics=self._config.metrics,
                recording=self._config.recording,
                ui=self._config.ui,
                telemetry=self._config.telemetry,
                detector=self._config.detector,
                strike_zone=updated_zone,
                ball=self._config.ball,
                upload=self._config.upload,
            )

    def update_strike_zone_ratios(self, top_ratio: float, bottom_ratio: float) -> None:
        """Update strike zone top/bottom ratios.

        Creates new immutable config with updated strike zone ratios.

        Args:
            top_ratio: Top of strike zone as ratio of batter height
            bottom_ratio: Bottom of strike zone as ratio of batter height
        """
        with self._lock:
            if self._config is None or self._config.strike_zone is None:
                return

            # Create new strike zone with updated ratios
            updated_zone = self._config.strike_zone.__class__(
                batter_height_in=self._config.strike_zone.batter_height_in,
                top_ratio=top_ratio,
                bottom_ratio=bottom_ratio,
                plate_width_in=self._config.strike_zone.plate_width_in,
                plate_length_in=self._config.strike_zone.plate_length_in,
            )

            # Create new config with updated strike zone
            self._config = self._config.__class__(
                camera=self._config.camera,
                stereo=self._config.stereo,
                tracking=self._config.tracking,
                metrics=self._config.metrics,
                recording=self._config.recording,
                ui=self._config.ui,
                telemetry=self._config.telemetry,
                detector=self._config.detector,
                strike_zone=updated_zone,
                ball=self._config.ball,
                upload=self._config.upload,
            )

    def update_mound_distance(self, distance_ft: float) -> None:
        """Update plate-to-mound distance (release plane).

        Creates new immutable config with updated metrics.

        Args:
            distance_ft: Distance from plate to mound in feet
        """
        with self._lock:
            if self._config is None or self._config.metrics is None:
                return

            # Create new metrics with updated release plane
            updated_metrics = self._config.metrics.__class__(
                coordinate_system=self._config.metrics.coordinate_system,
                plate_plane_z_ft=self._config.metrics.plate_plane_z_ft,
                release_plane_z_ft=distance_ft,
                approach_window_ft=self._config.metrics.approach_window_ft,
                velo_bounds_mph=self._config.metrics.velo_bounds_mph,
                hb_bounds_in=self._config.metrics.hb_bounds_in,
                ivb_bounds_in=self._config.metrics.ivb_bounds_in,
                release_height_bounds_ft=self._config.metrics.release_height_bounds_ft,
            )

            # Create new config with updated metrics
            self._config = self._config.__class__(
                camera=self._config.camera,
                stereo=self._config.stereo,
                tracking=self._config.tracking,
                metrics=updated_metrics,
                recording=self._config.recording,
                ui=self._config.ui,
                telemetry=self._config.telemetry,
                detector=self._config.detector,
                strike_zone=self._config.strike_zone,
                ball=self._config.ball,
                upload=self._config.upload,
            )

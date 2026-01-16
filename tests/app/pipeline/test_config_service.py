"""Tests for app.pipeline.config_service module."""

from __future__ import annotations

import pytest
from dataclasses import replace

from app.pipeline.config_service import ConfigService
from configs.settings import AppConfig, StrikeZoneConfig, BallConfig


class TestConfigService:
    """Tests for ConfigService."""

    @pytest.fixture
    def config(self):
        """Create test config."""
        return AppConfig(
            camera=None,  # Not needed for config service tests
            stereo=None,
            tracking=None,
            metrics=None,
            recording=None,
            ui=None,
            telemetry=None,
            detector=None,
            strike_zone=StrikeZoneConfig(
                batter_height_in=72.0,
                top_ratio=0.5,
                bottom_ratio=0.27,
                plate_width_in=17.0,
                plate_length_in=17.0,
            ),
            ball=BallConfig(
                type="baseball",
                radius_in={"baseball": 1.45, "softball": 1.88},
            ),
            upload=None,
        )

    @pytest.fixture
    def service(self, config):
        """Create config service."""
        return ConfigService(config)

    def test_get_config_returns_current_config(self, service, config):
        """Test get_config returns current configuration."""
        result = service.get_config()
        assert result == config

    def test_update_batter_height(self, service):
        """Test updating batter height."""
        service.update_batter_height(68.0)

        config = service.get_config()
        assert config.strike_zone.batter_height_in == 68.0

    def test_update_strike_zone_ratios(self, service):
        """Test updating strike zone ratios."""
        service.update_strike_zone_ratios(top_ratio=0.6, bottom_ratio=0.3)

        config = service.get_config()
        assert config.strike_zone.top_ratio == 0.6
        assert config.strike_zone.bottom_ratio == 0.3

    def test_set_ball_type(self, service):
        """Test setting ball type."""
        service.set_ball_type("softball")

        config = service.get_config()
        assert config.ball.type == "softball"

    def test_get_ball_radius_baseball(self, service):
        """Test getting ball radius for baseball."""
        radius = service.get_ball_radius_in()
        assert radius == 1.45

    def test_get_ball_radius_softball(self, service):
        """Test getting ball radius for softball."""
        service.set_ball_type("softball")
        radius = service.get_ball_radius_in()
        assert radius == 1.88

    def test_thread_safe_updates(self, service):
        """Test multiple concurrent updates (thread safety)."""
        import threading

        def update_height():
            for _ in range(100):
                service.update_batter_height(70.0)

        def update_ratios():
            for _ in range(100):
                service.update_strike_zone_ratios(0.55, 0.28)

        threads = [
            threading.Thread(target=update_height),
            threading.Thread(target=update_ratios),
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should not raise any exceptions
        config = service.get_config()
        assert config is not None

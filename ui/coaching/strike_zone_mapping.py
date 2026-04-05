"""Helpers for mapping physical strike-zone coordinates into overlay space."""

from __future__ import annotations

from dataclasses import dataclass

from configs.settings import AppConfig
from metrics.strike_zone import build_strike_zone


@dataclass(frozen=True)
class StrikeZoneOverlayConfig:
    """Physical strike-zone settings required by coaching overlays."""

    plate_z_ft: float
    batter_height_in: float
    top_ratio: float
    bottom_ratio: float
    plate_width_in: float
    plate_length_in: float

    @classmethod
    def from_app_config(cls, config: AppConfig) -> "StrikeZoneOverlayConfig":
        """Build overlay config from app configuration."""
        return cls(
            plate_z_ft=config.metrics.plate_plane_z_ft,
            batter_height_in=config.strike_zone.batter_height_in,
            top_ratio=config.strike_zone.top_ratio,
            bottom_ratio=config.strike_zone.bottom_ratio,
            plate_width_in=config.strike_zone.plate_width_in,
            plate_length_in=config.strike_zone.plate_length_in,
        )

    def with_batter_height(self, batter_height_in: float) -> "StrikeZoneOverlayConfig":
        """Return a copy with an updated batter height."""
        return StrikeZoneOverlayConfig(
            plate_z_ft=self.plate_z_ft,
            batter_height_in=batter_height_in,
            top_ratio=self.top_ratio,
            bottom_ratio=self.bottom_ratio,
            plate_width_in=self.plate_width_in,
            plate_length_in=self.plate_length_in,
        )


@dataclass(frozen=True)
class StrikeZoneOverlayLayout:
    """Normalized overlay coordinates for the zone and latest pitch."""

    zone_left: float
    zone_right: float
    zone_top: float
    zone_bottom: float
    pitch_x: float
    pitch_y: float


def calculate_overlay_layout(
    overlay_config: StrikeZoneOverlayConfig,
    *,
    plate_x_ft: float,
    plate_y_ft: float,
) -> StrikeZoneOverlayLayout:
    """Map plate-crossing coordinates into normalized overlay space."""
    strike_zone = build_strike_zone(
        plate_z_ft=overlay_config.plate_z_ft,
        plate_width_in=overlay_config.plate_width_in,
        plate_length_in=overlay_config.plate_length_in,
        batter_height_in=overlay_config.batter_height_in,
        top_ratio=overlay_config.top_ratio,
        bottom_ratio=overlay_config.bottom_ratio,
    )

    zone_left_ft = min(point[0] for point in strike_zone.polygon_xz)
    zone_right_ft = max(point[0] for point in strike_zone.polygon_xz)
    zone_width_ft = max(zone_right_ft - zone_left_ft, 0.1)
    zone_height_ft = max(strike_zone.y_top_ft - strike_zone.y_bottom_ft, 0.1)

    horizontal_margin_ft = max(zone_width_ft * 0.8, 0.5)
    vertical_margin_ft = max(zone_height_ft * 0.35, 0.4)

    view_left_ft = zone_left_ft - horizontal_margin_ft
    view_right_ft = zone_right_ft + horizontal_margin_ft
    view_top_ft = strike_zone.y_top_ft + vertical_margin_ft
    view_bottom_ft = max(0.0, strike_zone.y_bottom_ft - vertical_margin_ft)

    view_width_ft = max(view_right_ft - view_left_ft, 0.1)
    view_height_ft = max(view_top_ft - view_bottom_ft, 0.1)

    return StrikeZoneOverlayLayout(
        zone_left=_clamp((zone_left_ft - view_left_ft) / view_width_ft),
        zone_right=_clamp((zone_right_ft - view_left_ft) / view_width_ft),
        zone_top=_clamp((view_top_ft - strike_zone.y_top_ft) / view_height_ft),
        zone_bottom=_clamp((view_top_ft - strike_zone.y_bottom_ft) / view_height_ft),
        pitch_x=_clamp((plate_x_ft - view_left_ft) / view_width_ft),
        pitch_y=_clamp((view_top_ft - plate_y_ft) / view_height_ft),
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


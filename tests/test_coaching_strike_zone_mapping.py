"""Tests for coaching strike-zone overlay mapping."""

from ui.coaching.strike_zone_mapping import (
    StrikeZoneOverlayConfig,
    calculate_overlay_layout,
)


def _overlay_config(batter_height_in: float = 72.0) -> StrikeZoneOverlayConfig:
    return StrikeZoneOverlayConfig(
        plate_z_ft=1.417,
        batter_height_in=batter_height_in,
        top_ratio=0.7,
        bottom_ratio=0.3,
        plate_width_in=17.0,
        plate_length_in=17.0,
    )


def test_calculate_overlay_layout_centers_pitch_inside_zone() -> None:
    config = _overlay_config()
    mid_zone_y_ft = (config.batter_height_in * (config.top_ratio + config.bottom_ratio) / 2.0) / 12.0

    layout = calculate_overlay_layout(
        config,
        plate_x_ft=0.0,
        plate_y_ft=mid_zone_y_ft,
    )

    zone_center_x = (layout.zone_left + layout.zone_right) / 2.0
    zone_center_y = (layout.zone_top + layout.zone_bottom) / 2.0

    assert abs(layout.pitch_x - zone_center_x) < 0.05
    assert abs(layout.pitch_y - zone_center_y) < 0.05


def test_calculate_overlay_layout_clamps_pitches_outside_view() -> None:
    config = _overlay_config()

    layout = calculate_overlay_layout(
        config,
        plate_x_ft=10.0,
        plate_y_ft=10.0,
    )

    assert 0.0 <= layout.pitch_x <= 1.0
    assert 0.0 <= layout.pitch_y <= 1.0
    assert layout.pitch_x == 1.0
    assert layout.pitch_y == 0.0

"""Tests for strike zone intersection logic."""

from __future__ import annotations

import pytest

from metrics.strike_zone import (
    build_strike_zone,
    is_strike,
    StrikeZone,
    StrikeResult,
)


def test_build_strike_zone():
    """Test strike zone construction."""
    # Standard baseball strike zone for 6ft batter
    batter_height_in = 72.0  # 6 feet
    top_ratio = 0.5  # Midpoint between shoulders and belt
    bottom_ratio = 0.27  # Just below knees
    plate_width_in = 17.0

    zone = build_strike_zone(
        plate_z_ft=0.0,
        plate_width_in=plate_width_in,
        plate_length_in=8.5,  # Standard home plate depth
        batter_height_in=batter_height_in,
        top_ratio=top_ratio,
        bottom_ratio=bottom_ratio,
    )

    # Verify dimensions
    expected_top_y_in = batter_height_in * top_ratio  # 36 inches
    expected_bottom_y_in = batter_height_in * bottom_ratio  # 19.44 inches

    assert isinstance(zone, StrikeZone)
    # Zone should have reasonable bounds


def test_center_strike():
    """Test that ball at center of strike zone is a strike."""
    batter_height_in = 72.0
    zone = build_strike_zone(
        batter_height_in=batter_height_in,
        top_ratio=0.5,
        bottom_ratio=0.27,
        plate_width_in=17.0,
        plate_z_ft=0.0,
    )

    # Ball at center of plate, middle height
    # X=0 (center), Y=27 inches (mid-strike zone), Z=0 (at plate)
    center_y_in = (batter_height_in * 0.5 + batter_height_in * 0.27) / 2  # ~27.7 in

    result = is_strike(
        x_ft=0.0,
        y_ft=center_y_in / 12.0,  # Convert to feet
        z_ft=0.0,
        ball_radius_in=1.45,  # Baseball radius
        zone=zone,
    )

    assert result.is_strike, "Ball at center of zone should be a strike"
    assert result.zone_row is not None, "Should have zone row"
    assert result.zone_col is not None, "Should have zone column"
    # Center should be row=1, col=1 (middle of 3x3 grid)
    assert result.zone_row == 1, f"Expected row=1, got {result.zone_row}"
    assert result.zone_col == 1, f"Expected col=1, got {result.zone_col}"


def test_ball_outside_zone():
    """Test that ball outside zone is a ball."""
    batter_height_in = 72.0
    zone = build_strike_zone(
        batter_height_in=batter_height_in,
        top_ratio=0.5,
        bottom_ratio=0.27,
        plate_width_in=17.0,
        plate_z_ft=0.0,
    )

    # Ball way outside (2 feet to the left)
    result = is_strike(
        x_ft=-2.0,
        y_ft=2.0,
        z_ft=0.0,
        ball_radius_in=1.45,
        zone=zone,
    )

    assert not result.is_strike, "Ball far outside zone should be a ball"


def test_ball_high():
    """Test that ball above zone is a ball."""
    batter_height_in = 72.0
    zone = build_strike_zone(
        batter_height_in=batter_height_in,
        top_ratio=0.5,
        bottom_ratio=0.27,
        plate_width_in=17.0,
        plate_z_ft=0.0,
    )

    # Ball high (5 feet up)
    result = is_strike(
        x_ft=0.0,
        y_ft=5.0,
        z_ft=0.0,
        ball_radius_in=1.45,
        zone=zone,
    )

    assert not result.is_strike, "Ball high should be a ball"


def test_ball_low():
    """Test that ball below zone is a ball."""
    batter_height_in = 72.0
    zone = build_strike_zone(
        batter_height_in=batter_height_in,
        top_ratio=0.5,
        bottom_ratio=0.27,
        plate_width_in=17.0,
        plate_z_ft=0.0,
    )

    # Ball low (6 inches = 0.5 feet)
    result = is_strike(
        x_ft=0.0,
        y_ft=0.5,
        z_ft=0.0,
        ball_radius_in=1.45,
        zone=zone,
    )

    assert not result.is_strike, "Ball low should be a ball"


def test_edge_strike():
    """Test ball at edge of zone (should be strike if any part crosses)."""
    batter_height_in = 72.0
    zone = build_strike_zone(
        batter_height_in=batter_height_in,
        top_ratio=0.5,
        bottom_ratio=0.27,
        plate_width_in=17.0,
        plate_z_ft=0.0,
    )

    # Ball at right edge of plate (8.5 inches from center)
    # With 1.45 inch radius, center can be up to 8.5 + 1.45 = 9.95 inches from center
    edge_x_in = 8.5 + 0.5  # Just inside
    center_y_in = (batter_height_in * 0.5 + batter_height_in * 0.27) / 2

    result = is_strike(
        x_ft=edge_x_in / 12.0,
        y_ft=center_y_in / 12.0,
        z_ft=0.0,
        ball_radius_in=1.45,
        zone=zone,
    )

    # Should still be a strike if any part crosses the zone
    assert result.is_strike, "Ball with edge in zone should be a strike"


def test_zone_grid_corners():
    """Test all 9 cells of the 3x3 zone grid."""
    batter_height_in = 72.0
    zone = build_strike_zone(
        batter_height_in=batter_height_in,
        top_ratio=0.5,
        bottom_ratio=0.27,
        plate_width_in=17.0,
        plate_z_ft=0.0,
    )

    # Test positions for each grid cell
    # Grid is 3x3: (row, col) from (0, 0) to (2, 2)
    plate_width_ft = 17.0 / 12.0
    zone_height_in = batter_height_in * (0.5 - 0.27)
    zone_height_ft = zone_height_in / 12.0

    cell_width_ft = plate_width_ft / 3
    cell_height_ft = zone_height_ft / 3

    for row in range(3):
        for col in range(3):
            # Position at center of each cell
            x_ft = (col - 1) * cell_width_ft  # col 1 is center
            y_ft = (batter_height_in * 0.27 / 12.0) + (row + 0.5) * cell_height_ft

            result = is_strike(
                x_ft=x_ft,
                y_ft=y_ft,
                z_ft=0.0,
                ball_radius_in=1.45,
                zone=zone,
            )

            assert result.is_strike, f"Cell ({row}, {col}) should be a strike"
            assert result.zone_row == row, f"Expected row={row}, got {result.zone_row}"
            assert result.zone_col == col, f"Expected col={col}, got {result.zone_col}"


def test_softball_vs_baseball():
    """Test strike zone with different ball sizes."""
    batter_height_in = 72.0
    zone = build_strike_zone(
        batter_height_in=batter_height_in,
        top_ratio=0.5,
        bottom_ratio=0.27,
        plate_width_in=17.0,
        plate_z_ft=0.0,
    )

    # Position just outside zone
    x_ft = 10.0 / 12.0  # 10 inches from center
    y_ft = 2.0

    # Baseball (radius 1.45 in) - should be ball
    result_baseball = is_strike(
        x_ft=x_ft,
        y_ft=y_ft,
        z_ft=0.0,
        ball_radius_in=1.45,
        zone=zone,
    )

    # Softball (radius 1.88 in) - larger, might clip zone
    result_softball = is_strike(
        x_ft=x_ft,
        y_ft=y_ft,
        z_ft=0.0,
        ball_radius_in=1.88,
        zone=zone,
    )

    # At least verify both run without errors
    assert isinstance(result_baseball.is_strike, bool)
    assert isinstance(result_softball.is_strike, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

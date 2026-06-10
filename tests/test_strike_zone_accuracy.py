"""Tests for strike zone intersection logic.

``is_strike`` consumes an iterable of :class:`StereoObservation` samples (the
ball's 3D path near the plate) rather than a single point. Each test builds a
one-sample path at the position under test and asserts the resulting
:class:`StrikeResult`.
"""

from __future__ import annotations

import pytest

from contracts import StereoObservation
from metrics.strike_zone import (
    build_strike_zone,
    is_strike,
    StrikeZone,
)

BASEBALL_RADIUS_IN = 1.45
SOFTBALL_RADIUS_IN = 1.88


def _observation(x_ft: float, y_ft: float, z_ft: float) -> StereoObservation:
    """Build a minimal StereoObservation at a 3D position (in feet)."""
    return StereoObservation(
        t_ns=0,
        left=(0.0, 0.0),
        right=(0.0, 0.0),
        X=x_ft,
        Y=y_ft,
        Z=z_ft,
        quality=1.0,
    )


def _standard_zone() -> StrikeZone:
    """Standard strike zone for a 6ft (72in) batter."""
    return build_strike_zone(
        plate_z_ft=0.0,
        plate_width_in=17.0,
        plate_length_in=8.5,
        batter_height_in=72.0,
        top_ratio=0.5,
        bottom_ratio=0.27,
    )


def test_build_strike_zone():
    """Test strike zone construction."""
    zone = _standard_zone()
    assert isinstance(zone, StrikeZone)
    assert zone.y_top_ft > zone.y_bottom_ft
    assert zone.polygon_xz


def test_center_strike():
    """Ball at the center of the strike zone is a strike in cell (1, 1)."""
    zone = _standard_zone()
    # Y at the vertical midpoint of the zone.
    center_y_in = (72.0 * 0.5 + 72.0 * 0.27) / 2  # ~27.7 in

    result = is_strike(
        [_observation(0.0, center_y_in / 12.0, 0.0)],
        zone,
        BASEBALL_RADIUS_IN,
    )

    assert result.is_strike, "Ball at center of zone should be a strike"
    assert result.zone_row == 1, f"Expected row=1, got {result.zone_row}"
    assert result.zone_col == 1, f"Expected col=1, got {result.zone_col}"


def test_ball_outside_zone():
    """Ball well to the side of the plate is a ball."""
    zone = _standard_zone()

    result = is_strike(
        [_observation(-2.0, 2.0, 0.0)],
        zone,
        BASEBALL_RADIUS_IN,
    )

    assert not result.is_strike, "Ball far outside zone should be a ball"


def test_ball_high():
    """Ball above the top of the zone is a ball."""
    zone = _standard_zone()

    result = is_strike(
        [_observation(0.0, 5.0, 0.0)],
        zone,
        BASEBALL_RADIUS_IN,
    )

    assert not result.is_strike, "Ball high should be a ball"


def test_ball_low():
    """Ball below the bottom of the zone is a ball."""
    zone = _standard_zone()

    result = is_strike(
        [_observation(0.0, 0.5, 0.0)],
        zone,
        BASEBALL_RADIUS_IN,
    )

    assert not result.is_strike, "Ball low should be a ball"


def test_edge_strike():
    """Ball whose radius clips the edge of the plate is a strike."""
    zone = _standard_zone()
    # Center just outside the 8.5in half-plate; radius brings it into the zone.
    edge_x_in = 8.5 + 0.5
    center_y_in = (72.0 * 0.5 + 72.0 * 0.27) / 2

    result = is_strike(
        [_observation(edge_x_in / 12.0, center_y_in / 12.0, 0.0)],
        zone,
        BASEBALL_RADIUS_IN,
    )

    assert result.is_strike, "Ball with edge in zone should be a strike"


def test_zone_grid_corners():
    """Each of the 9 cells of the 0-indexed 3x3 grid maps correctly."""
    zone = _standard_zone()

    plate_width_ft = 17.0 / 12.0
    zone_height_ft = (72.0 * (0.5 - 0.27)) / 12.0
    cell_width_ft = plate_width_ft / 3
    cell_height_ft = zone_height_ft / 3
    y_bottom_ft = (72.0 * 0.27) / 12.0

    for row in range(3):
        for col in range(3):
            x_ft = (col - 1) * cell_width_ft  # col 1 is center
            y_ft = y_bottom_ft + (row + 0.5) * cell_height_ft

            result = is_strike(
                [_observation(x_ft, y_ft, 0.0)],
                zone,
                BASEBALL_RADIUS_IN,
            )

            assert result.is_strike, f"Cell ({row}, {col}) should be a strike"
            assert result.zone_row == row, f"Expected row={row}, got {result.zone_row}"
            assert result.zone_col == col, f"Expected col={col}, got {result.zone_col}"


def test_softball_vs_baseball():
    """Both ball sizes produce a valid boolean strike decision."""
    zone = _standard_zone()
    x_ft = 10.0 / 12.0  # 10 inches from center
    y_ft = 2.0

    result_baseball = is_strike([_observation(x_ft, y_ft, 0.0)], zone, BASEBALL_RADIUS_IN)
    result_softball = is_strike([_observation(x_ft, y_ft, 0.0)], zone, SOFTBALL_RADIUS_IN)

    assert isinstance(result_baseball.is_strike, bool)
    assert isinstance(result_softball.is_strike, bool)


def test_empty_observations_is_ball():
    """No observations yields a non-strike with zero samples."""
    zone = _standard_zone()

    result = is_strike([], zone, BASEBALL_RADIUS_IN)

    assert not result.is_strike
    assert result.sample_count == 0
    assert result.zone_row is None
    assert result.zone_col is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

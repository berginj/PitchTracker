"""Strike zone computation from 3D observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from contracts import StereoObservation
from detect.utils import point_in_polygon

Point2D = Tuple[float, float]


@dataclass(frozen=True)
class StrikeZone:
    polygon_xz: List[Point2D]
    y_bottom_ft: float
    y_top_ft: float
    plate_z_ft: float


@dataclass(frozen=True)
class StrikeResult:
    is_strike: bool
    sample_count: int
    zone_row: int | None = None
    zone_col: int | None = None


def build_strike_zone(
    plate_z_ft: float,
    plate_width_in: float,
    plate_length_in: float,
    batter_height_in: float,
    top_ratio: float,
    bottom_ratio: float,
) -> StrikeZone:
    half_width = plate_width_in / 2.0
    back_width = half_width / 2.0
    depth = plate_length_in
    # Plate polygon in X-Z with front edge at plate_z_ft (toward catcher).
    polygon_xz = [
        (-half_width, plate_z_ft),
        (half_width, plate_z_ft),
        (back_width, plate_z_ft - depth / 2.0),
        (0.0, plate_z_ft - depth),
        (-back_width, plate_z_ft - depth / 2.0),
    ]
    y_top_ft = (batter_height_in * top_ratio) / 12.0
    y_bottom_ft = (batter_height_in * bottom_ratio) / 12.0
    return StrikeZone(
        polygon_xz=[(x / 12.0, z / 12.0) for x, z in polygon_xz],
        y_bottom_ft=y_bottom_ft,
        y_top_ft=y_top_ft,
        plate_z_ft=plate_z_ft,
    )


def is_strike(
    observations: Iterable[StereoObservation],
    strike_zone: StrikeZone,
    ball_radius_in: float,
) -> StrikeResult:
    obs_list = list(observations)
    if not obs_list:
        return StrikeResult(is_strike=False, sample_count=0)
    radius_ft = ball_radius_in / 12.0
    zone_row = None
    zone_col = None
    crossing = _find_plate_crossing(obs_list, strike_zone.plate_z_ft)
    if crossing is not None:
        zone_row, zone_col = _zone_cell(
            crossing,
            strike_zone.y_bottom_ft,
            strike_zone.y_top_ft,
            strike_zone.polygon_xz,
        )
    for obs in obs_list:
        if _sphere_intersects_zone(obs, strike_zone, radius_ft):
            return StrikeResult(
                is_strike=True,
                sample_count=len(obs_list),
                zone_row=zone_row,
                zone_col=zone_col,
            )
    return StrikeResult(
        is_strike=False,
        sample_count=len(obs_list),
        zone_row=zone_row,
        zone_col=zone_col,
    )


def _sphere_intersects_zone(
    obs: StereoObservation,
    zone: StrikeZone,
    radius_ft: float,
) -> bool:
    if obs.Y + radius_ft < zone.y_bottom_ft:
        return False
    if obs.Y - radius_ft > zone.y_top_ft:
        return False
    point = (obs.X, obs.Z)
    if point_in_polygon(point, zone.polygon_xz):
        return True
    distance = _distance_to_polygon(point, zone.polygon_xz)
    return distance <= radius_ft


def _find_plate_crossing(
    observations: List[StereoObservation],
    plate_z_ft: float,
) -> Tuple[float, float, float] | None:
    if not observations:
        return None
    for i in range(len(observations) - 1):
        a = observations[i]
        b = observations[i + 1]
        az = a.Z - plate_z_ft
        bz = b.Z - plate_z_ft
        if az == 0:
            return (a.X, a.Y, a.Z)
        if az * bz <= 0:
            t = az / (az - bz)
            x = a.X + t * (b.X - a.X)
            y = a.Y + t * (b.Y - a.Y)
            z = a.Z + t * (b.Z - a.Z)
            return (x, y, z)
    closest = min(observations, key=lambda obs: abs(obs.Z - plate_z_ft))
    return (closest.X, closest.Y, closest.Z)


def _zone_cell(
    crossing: Tuple[float, float, float],
    y_bottom_ft: float,
    y_top_ft: float,
    polygon_xz: List[Point2D],
) -> Tuple[int | None, int | None]:
    x, y, z = crossing
    width_ft = _plate_width_ft(polygon_xz)
    if width_ft <= 0:
        return None, None
    if y < y_bottom_ft or y > y_top_ft:
        return None, None
    if not point_in_polygon((x, z), polygon_xz):
        return None, None
    x_min = -width_ft / 2.0
    x_max = width_ft / 2.0
    x_third = (x_max - x_min) / 3.0
    y_third = (y_top_ft - y_bottom_ft) / 3.0
    col = int((x - x_min) / x_third) + 1
    row = int((y - y_bottom_ft) / y_third) + 1
    col = max(1, min(3, col))
    row = max(1, min(3, row))
    return row, col


def _plate_width_ft(polygon_xz: List[Point2D]) -> float:
    xs = [point[0] for point in polygon_xz]
    if not xs:
        return 0.0
    return max(xs) - min(xs)


def _distance_to_polygon(point: Point2D, polygon: List[Point2D]) -> float:
    min_dist = float("inf")
    for i in range(len(polygon)):
        a = polygon[i]
        b = polygon[(i + 1) % len(polygon)]
        min_dist = min(min_dist, _distance_to_segment(point, a, b))
    return min_dist


def _distance_to_segment(p: Point2D, a: Point2D, b: Point2D) -> float:
    px, pz = p
    ax, az = a
    bx, bz = b
    abx = bx - ax
    abz = bz - az
    apx = px - ax
    apz = pz - az
    denom = abx * abx + abz * abz
    if denom == 0:
        return ((px - ax) ** 2 + (pz - az) ** 2) ** 0.5
    t = max(0.0, min(1.0, (apx * abx + apz * abz) / denom))
    cx = ax + t * abx
    cz = az + t * abz
    return ((px - cx) ** 2 + (pz - cz) ** 2) ** 0.5

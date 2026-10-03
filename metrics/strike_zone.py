"""Strike zone computation from 3D observations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite, sqrt
from typing import Iterable, List, Tuple

from contracts import StereoObservation
from contracts.timing import TimestampEvidence
from detect.utils import point_in_polygon
from metrics.strike_uncertainty import StrikeSensitivity, strike_sensitivity

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
    available: bool = True
    reason: str | None = None
    basis: str = "piecewise_linear_swept_sphere_estimated_geometry"


def build_strike_zone(
    plate_z_ft: float,
    plate_width_in: float,
    plate_length_in: float,
    batter_height_in: float,
    top_ratio: float,
    bottom_ratio: float,
) -> StrikeZone:
    half_width = plate_width_in / 24.0
    back_width = half_width / 2.0
    depth = plate_length_in / 12.0
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
        polygon_xz=polygon_xz,
        y_bottom_ft=y_bottom_ft,
        y_top_ft=y_top_ft,
        plate_z_ft=plate_z_ft,
    )


def is_strike(
    observations: Iterable[StereoObservation],
    strike_zone: StrikeZone,
    ball_radius_in: float,
    *,
    max_gap_ms: float = 50.0,
    timing_evidence: TimestampEvidence | None = None,
) -> StrikeResult:
    """Intersect the full zone volume with an estimated piecewise-linear sphere.
    The 50 ms interpolation limit is not a physical uncertainty guarantee.
    """
    obs_list = list(observations)
    invalid_reason = _invalid_geometry_reason(obs_list, ball_radius_in, max_gap_ms)
    if invalid_reason is not None:
        return StrikeResult(False, len(obs_list), available=False, reason=invalid_reason)
    sensitivity = strike_sensitivity(obs_list, timing_evidence)
    if sensitivity.invalid_reason is not None:
        return StrikeResult(False, len(obs_list), available=False, reason=sensitivity.invalid_reason)
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
    hit = any(_sphere_intersects_zone(obs, strike_zone, radius_ft) for obs in obs_list)
    uncertain_gap = False
    for a, b in zip(obs_list, obs_list[1:]):
        gap_ms = (b.t_ns - a.t_ns) / 1e6
        if not 0 < gap_ms <= max_gap_ms:
            uncertain_gap = True
            continue
        hit = hit or _segment_distance_squared(a, b, strike_zone) <= radius_ft**2 + 1e-12
    if hit:
        result = StrikeResult(True, len(obs_list), zone_row, zone_col)
        return _conditional_call(result, obs_list, strike_zone, (radius_ft, max_gap_ms), sensitivity)
    if uncertain_gap:
        return StrikeResult(False, len(obs_list), available=False, reason="UNSUPPORTED_TIMING_GAP")
    if crossing is None:
        return StrikeResult(False, len(obs_list), available=False, reason="NO_OBSERVED_CROSSING")
    # A complete traversal is needed to exclude intersection deeper in the
    # volume. Retain the single-point API for an observation on the front plane.
    if len(obs_list) > 1 and min(obs.Z for obs in obs_list) > min(z for _, z in strike_zone.polygon_xz) - radius_ft:
        return StrikeResult(False, len(obs_list), available=False, reason="INCOMPLETE_ZONE_COVERAGE")
    result = StrikeResult(False, len(obs_list), zone_row, zone_col)
    return _conditional_call(result, obs_list, strike_zone, (radius_ft, max_gap_ms), sensitivity)


def _invalid_geometry_reason(observations: List[StereoObservation], radius_in: float, max_gap_ms: float) -> str | None:
    if not observations:
        return "NO_OBSERVATIONS"
    if not all(isfinite(value) for obs in observations for value in (obs.X, obs.Y, obs.Z)):
        return "INVALID_COORDINATES"
    if not isfinite(radius_in) or radius_in <= 0 or not isfinite(max_gap_ms) or max_gap_ms <= 0:
        return "INVALID_GEOMETRY_POLICY"
    return None


def _conditional_call(
    result: StrikeResult, observations: List[StereoObservation], zone: StrikeZone,
    geometry_policy: tuple[float, float], sensitivity: StrikeSensitivity,
) -> StrikeResult:
    radius_ft, max_gap_ms = geometry_policy
    if sensitivity.radius_ft > 0:
        clearance = min(_signed_distance(obs.X, obs.Y, obs.Z, zone) for obs in observations)
        for a, b in zip(observations, observations[1:]):
            if (b.t_ns - a.t_ns) / 1e6 <= max_gap_ms:
                clearance = min(clearance, _minimum_segment_clearance(a, b, zone))
        robust = (
            clearance <= radius_ft - sensitivity.radius_ft
            if result.is_strike else clearance > radius_ft + sensitivity.radius_ft
        )
        if not robust:
            return replace(result, is_strike=False, available=False, reason="STRIKE_BOUNDARY_UNCERTAIN", basis=sensitivity.basis)
    return replace(result, reason=sensitivity.reason, basis=sensitivity.basis)


def _signed_distance(x: float, y: float, z: float, zone: StrikeZone) -> float:
    if zone.y_bottom_ft <= y <= zone.y_top_ft and point_in_polygon((x, z), zone.polygon_xz):
        return -min(y - zone.y_bottom_ft, zone.y_top_ft - y, _distance_to_polygon((x, z), zone.polygon_xz))
    return sqrt(_point_distance_squared(x, y, z, zone))


def _minimum_segment_clearance(a: StereoObservation, b: StereoObservation, zone: StrikeZone) -> float:
    """Minimize signed distance to the convex strike prism along a segment."""
    def distance(t: float) -> float:
        return _signed_distance(a.X + t * (b.X - a.X), a.Y + t * (b.Y - a.Y), a.Z + t * (b.Z - a.Z), zone)

    lo, hi = 0.0, 1.0
    ratio = (5.0**0.5 - 1.0) / 2.0
    left, right = hi - ratio, lo + ratio
    f_left, f_right = distance(left), distance(right)
    for _ in range(60):
        if f_left <= f_right:
            hi, right, f_right = right, left, f_left
            left = hi - ratio * (hi - lo)
            f_left = distance(left)
        else:
            lo, left, f_left = left, right, f_right
            right = lo + ratio * (hi - lo)
            f_right = distance(right)
    return min(distance(0.0), distance(1.0), f_left, f_right)


def _sphere_intersects_zone(
    obs: StereoObservation,
    zone: StrikeZone,
    radius_ft: float,
) -> bool:
    return _point_distance_squared(obs.X, obs.Y, obs.Z, zone) <= radius_ft**2 + 1e-12


def _point_distance_squared(x: float, y: float, z: float, zone: StrikeZone) -> float:
    vertical = max(zone.y_bottom_ft - y, y - zone.y_top_ft, 0.0)
    horizontal = 0.0 if point_in_polygon((x, z), zone.polygon_xz) else _distance_to_polygon((x, z), zone.polygon_xz)
    return vertical**2 + horizontal**2


def _segment_distance_squared(a: StereoObservation, b: StereoObservation, zone: StrikeZone) -> float:
    """Minimize convex squared distance from a segment to a convex prism.

    Golden-section minimization avoids expanding polygon half-spaces, which
    would incorrectly count square corners as spherical ball contact.
    """

    def distance(t: float) -> float:
        return _point_distance_squared(a.X + t * (b.X - a.X), a.Y + t * (b.Y - a.Y), a.Z + t * (b.Z - a.Z), zone)

    lo, hi = 0.0, 1.0
    ratio = (5.0**0.5 - 1.0) / 2.0
    left, right = hi - ratio, lo + ratio
    f_left, f_right = distance(left), distance(right)
    for _ in range(60):
        if f_left <= f_right:
            hi, right, f_right = right, left, f_left
            left = hi - ratio * (hi - lo)
            f_left = distance(left)
        else:
            lo, left, f_left = left, right, f_right
            right = lo + ratio * (hi - lo)
            f_right = distance(right)
    return min(distance(0.0), distance(1.0), f_left, f_right)


def _find_plate_crossing(
    observations: List[StereoObservation],
    plate_z_ft: float,
) -> Tuple[float, float, float] | None:
    if not observations:
        return None
    for obs in observations:
        if obs.Z == plate_z_ft:
            return (obs.X, obs.Y, obs.Z)
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
    return None


def _zone_cell(
    crossing: Tuple[float, float, float],
    y_bottom_ft: float,
    y_top_ft: float,
    polygon_xz: List[Point2D],
) -> Tuple[int | None, int | None]:
    x, y, _z = crossing
    width_ft = _plate_width_ft(polygon_xz)
    if width_ft <= 0:
        return None, None
    if y < y_bottom_ft or y > y_top_ft:
        return None, None
    x_min = -width_ft / 2.0
    x_max = width_ft / 2.0
    if x < x_min or x > x_max:
        return None, None
    x_third = (x_max - x_min) / 3.0
    y_third = (y_top_ft - y_bottom_ft) / 3.0
    # 0-indexed 3x3 grid: row/col in {0, 1, 2}. Consumers index 3x3
    # arrays directly (heatmaps, scoring games), so indices must start at 0.
    col = int((x - x_min) / x_third)
    row = int((y - y_bottom_ft) / y_third)
    col = max(0, min(2, col))
    row = max(0, min(2, row))
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
        return float(((px - ax) ** 2 + (pz - az) ** 2) ** 0.5)
    t = max(0.0, min(1.0, (apx * abx + apz * abz) / denom))
    cx = ax + t * abx
    cz = az + t * abz
    return float(((px - cx) ** 2 + (pz - cz) ** 2) ** 0.5)

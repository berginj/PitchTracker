"""Trajectory fitter registry and mode validation."""

from __future__ import annotations


from trajectory.physics import PhysicsDragFitter
from trajectory.ray_fit import RayGraphFitter, RayReprojectionFitter


TRAJECTORY_MODES = ("stereo_3d", "ray_reprojection", "ray_graph")


class TrajectoryFitterRegistry:
    def __init__(self) -> None:
        self._fitters = {
            "stereo_3d": PhysicsDragFitter,
            "ray_reprojection": RayReprojectionFitter,
            "ray_graph": RayGraphFitter,
        }

    def create(self, mode: str):
        if mode not in self._fitters:
            raise ValueError(f"Unknown trajectory mode: {mode}")
        return self._fitters[mode]()

    def available_modes(self) -> tuple[str, ...]:
        return tuple(self._fitters.keys())


def validate_trajectory_modes(primary_mode: str, compare_modes: tuple[str, ...] | list[str]) -> None:
    known = set(TRAJECTORY_MODES)
    modes = [primary_mode, *list(compare_modes)]
    unknown = sorted({mode for mode in modes if mode not in known})
    if unknown:
        raise ValueError(f"Unknown trajectory mode(s): {', '.join(unknown)}")

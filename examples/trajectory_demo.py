"""Synthetic trajectory demo."""

from __future__ import annotations

import json

from trajectory.physics import PhysicsDragFitter
from trajectory.radar import PhysicsDragRadarFitter
from trajectory.contracts import TrajectoryFitRequest
from trajectory.sim import SimConfig, simulate_ballistic


def main() -> None:
    observations = simulate_ballistic(SimConfig())
    request = TrajectoryFitRequest(
        observations=observations,
        plate_plane_z_ft=0.0,
        radar_speed_mph=90.0,
        radar_speed_ref="release",
    )
    physics = PhysicsDragFitter()
    radar = PhysicsDragRadarFitter()
    result_physics = physics.fit_trajectory(request)
    result_radar = radar.fit_trajectory(request)
    payload = {
        "physics": result_physics.to_dict(),
        "radar": result_radar.to_dict(),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

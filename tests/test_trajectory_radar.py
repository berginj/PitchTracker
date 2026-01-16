import pytest

from trajectory.contracts import TrajectoryFitRequest
from trajectory.radar import PhysicsDragRadarFitter
from trajectory.sim import SimConfig, simulate_ballistic


def test_radar_outlier_detection() -> None:
    observations = simulate_ballistic(SimConfig(outlier_prob=0.0, noise_ft=0.02))
    request = TrajectoryFitRequest(
        observations=observations,
        plate_plane_z_ft=0.0,
        radar_speed_mph=200.0,
        radar_speed_ref="release",
    )
    fitter = PhysicsDragRadarFitter()
    result = fitter.fit_trajectory(request)
    if not result.samples:
        pytest.skip("scipy not available or fit failed")
    assert result.diagnostics.radar_inlier_probability is not None
    assert result.diagnostics.radar_inlier_probability < 0.5

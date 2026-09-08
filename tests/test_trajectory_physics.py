from trajectory.contracts import TrajectoryFitRequest
from trajectory.physics import PhysicsDragFitter
from trajectory.sim import SimConfig, simulate_ballistic


def test_physics_fitter_ballistic_accuracy() -> None:
    observations = simulate_ballistic(SimConfig(outlier_prob=0.0, noise_ft=0.01))
    request = TrajectoryFitRequest(observations=observations, plate_plane_z_ft=0.0)
    fitter = PhysicsDragFitter()
    result = fitter.fit_trajectory(request)
    assert result.samples, "The required SciPy fitter must produce a result"
    assert result.diagnostics.rmse_3d_ft is not None
    assert result.diagnostics.rmse_3d_ft < 0.5

"""Trajectory fitting package."""

from trajectory.association import JointAssociator
from trajectory.camera_model import CameraModel, RayCameraModel, load_stereo_ray_camera_models
from trajectory.confidence import ConfidenceScorer
from trajectory.contracts import (
    FailureCode,
    ResidualReport,
    TrajectoryDiagnostics,
    TrajectoryFitRequest,
    TrajectoryFitResult,
)
from trajectory.ensemble import GatingModel, RuleBasedGatingModel, TrajectoryEnsembler
from trajectory.physics import PhysicsDragFitter
from trajectory.radar import PhysicsDragRadarFitter, RadarBiasEstimator
from trajectory.ray_fit import RayGraphFitter, RayReprojectionFitter
from trajectory.reprojection import ReprojectionEKF, RTSSmoother
from trajectory.registry import TRAJECTORY_MODES, TrajectoryFitterRegistry, validate_trajectory_modes

__all__ = [
    "CameraModel",
    "ConfidenceScorer",
    "FailureCode",
    "GatingModel",
    "JointAssociator",
    "PhysicsDragFitter",
    "PhysicsDragRadarFitter",
    "RadarBiasEstimator",
    "RayCameraModel",
    "RayGraphFitter",
    "RayReprojectionFitter",
    "ResidualReport",
    "ReprojectionEKF",
    "RTSSmoother",
    "RuleBasedGatingModel",
    "TRAJECTORY_MODES",
    "TrajectoryDiagnostics",
    "TrajectoryEnsembler",
    "TrajectoryFitRequest",
    "TrajectoryFitResult",
    "TrajectoryFitterRegistry",
    "load_stereo_ray_camera_models",
    "validate_trajectory_modes",
]

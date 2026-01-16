"""Trajectory fitting package."""

from trajectory.association import JointAssociator
from trajectory.camera_model import CameraModel
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
from trajectory.reprojection import ReprojectionEKF, RTSSmoother

__all__ = [
    "CameraModel",
    "ConfidenceScorer",
    "FailureCode",
    "GatingModel",
    "JointAssociator",
    "PhysicsDragFitter",
    "PhysicsDragRadarFitter",
    "RadarBiasEstimator",
    "ResidualReport",
    "ReprojectionEKF",
    "RTSSmoother",
    "RuleBasedGatingModel",
    "TrajectoryDiagnostics",
    "TrajectoryEnsembler",
    "TrajectoryFitRequest",
    "TrajectoryFitResult",
]

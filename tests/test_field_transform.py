from __future__ import annotations

import numpy as np
import pytest

from calib.field_transform import FieldTransform, estimate_field_transform
from app.services.orchestrator import PipelineOrchestrator
from app.services.rig_profile_models import RigProfile
from contracts import StereoObservation


def test_estimate_field_transform_recovers_rigid_pose() -> None:
    camera = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
    translation = np.array([2.0, 3.0, 4.0])
    field = (rotation @ camera.T).T + translation
    transform = estimate_field_transform(camera, field, fixture_id="plate-fixture")
    assert transform.rms_residual_ft == pytest.approx(0.0, abs=1e-10)
    assert transform.apply((0.25, 0.5, 0.75)) == pytest.approx(
        tuple(rotation @ np.array([0.25, 0.5, 0.75]) + translation)
    )


def test_field_transform_rejects_non_rigid_matrix() -> None:
    matrix = np.eye(4)
    matrix[0, 0] = 2.0
    with pytest.raises(ValueError, match="orthonormal"):
        FieldTransform(tuple(tuple(row) for row in matrix), 0.0, "bad")


def test_orchestrator_converts_camera_observation_to_active_field_frame() -> None:
    orchestrator = PipelineOrchestrator(backend="sim")
    transform = FieldTransform(
        ((1, 0, 0, 2), (0, 1, 0, 3), (0, 0, 1, 4), (0, 0, 0, 1)),
        0.0,
        "fixture",
    )
    orchestrator._active_rig_profile = RigProfile.from_dict(
        {
            "profile_id": "rig",
            "backend": "sim",
            "field_transform": transform.to_payload(),
        }
    )
    raw = StereoObservation(1, (1, 2), (1, 2), 0.5, 1.0, 2.0, 0.9, confidence=0.8)
    converted = orchestrator._to_field_coordinates(raw)
    assert (converted.X, converted.Y, converted.Z) == pytest.approx((2.5, 4.0, 6.0))


def test_orchestrator_rotates_observation_covariance_into_field_frame() -> None:
    orchestrator = PipelineOrchestrator(backend="sim")
    transform = FieldTransform(
        ((0, -1, 0, 2), (1, 0, 0, 3), (0, 0, 1, 4), (0, 0, 0, 1)),
        0.0,
        "fixture",
    )
    orchestrator._active_rig_profile = RigProfile.from_dict(
        {
            "profile_id": "rig",
            "backend": "sim",
            "field_transform": transform.to_payload(),
        }
    )
    raw = StereoObservation(
        1,
        (1, 2),
        (1, 2),
        0.5,
        1.0,
        2.0,
        0.9,
        covariance=((1.0, 0.0, 0.0), (0.0, 4.0, 0.0), (0.0, 0.0, 9.0)),
        confidence=0.8,
    )

    converted = orchestrator._to_field_coordinates(raw)

    assert (converted.X, converted.Y, converted.Z) == pytest.approx((1.0, 3.5, 6.0))
    assert np.asarray(converted.covariance) == pytest.approx(np.diag([4.0, 1.0, 9.0]))

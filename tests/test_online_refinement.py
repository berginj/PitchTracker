"""Unit tests for online calibration refinement."""

import numpy as np
import pytest
from pathlib import Path
import tempfile
import yaml
from datetime import datetime

# Import the online refinement classes
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from calib.online_refinement import (  # noqa: E402
    RefinementState,
    TrajectoryStats,
    OnlineCalibrationRefiner,
)


@pytest.fixture
def temp_config():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {
            "camera": {"width": 1280, "height": 720},
            "stereo": {
                "baseline_ft": 1.625,
                "focal_length_px": 1200.0,
                "time_sync_offset_ns": 0,
            },
            "metrics": {
                "drag_k0_default": 0.1,
                "plate_plane_z_ft": 0.0,
                "last_refinement_date": None,
                "online_refinement_enabled": True,
            },
        }
        yaml.dump(config, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


def create_high_quality_trajectory(
    drag_k0: float = 0.1,
    time_sync_residual_ns: float = 0.0,
    plate_z: float = 0.0,
    epipolar_error: float = 1.0,
) -> dict:
    """Create a high-quality trajectory result for testing."""
    return {
        "timestamp_ns": int(datetime.now().timestamp() * 1e9),
        "drag_k0_fit": drag_k0,
        "time_sync_residual_ns": time_sync_residual_ns,
        "plate_crossing_z_ft": plate_z,
        "mean_epipolar_error_px": epipolar_error,
        "max_epipolar_error_px": epipolar_error * 1.5,
        "num_observations": 15,
        "confidence_score": 0.85,
    }


def create_low_quality_trajectory() -> dict:
    """Create a low-quality trajectory that should be rejected."""
    return {
        "timestamp_ns": int(datetime.now().timestamp() * 1e9),
        "drag_k0_fit": 0.1,
        "time_sync_residual_ns": 0.0,
        "plate_crossing_z_ft": 0.0,
        "mean_epipolar_error_px": 5.0,  # High error
        "max_epipolar_error_px": 10.0,
        "num_observations": 5,  # Too few observations
        "confidence_score": 0.5,  # Low confidence
    }


def test_refinement_state_initialization():
    """Test RefinementState initialization."""
    state = RefinementState()

    assert state.drag_k0 == 0.1
    assert state.time_sync_offset_ns == 0
    assert state.plate_plane_z_ft == 0.0
    assert state.num_trajectories_accumulated == 0
    assert len(state.trajectories_buffer) == 0
    assert len(state.epipolar_error_trend) == 0
    assert state.refinement_confidence == 0.0
    assert state.last_refinement_date is None
    assert state.refinement_count == 0


def test_refiner_load_state(temp_config):
    """Test loading refinement state from config."""
    refiner = OnlineCalibrationRefiner(temp_config)

    assert refiner.state.drag_k0 == 0.1
    assert refiner.state.time_sync_offset_ns == 0
    assert refiner.state.plate_plane_z_ft == 0.0


def test_refiner_save_state(temp_config):
    """Test saving refinement state to config."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Modify state
    refiner.state.drag_k0 = 0.15
    refiner.state.time_sync_offset_ns = 1000000
    refiner.state.plate_plane_z_ft = 2.5
    refiner.state.last_refinement_date = datetime.now().isoformat()

    # Save
    refiner._save_state()

    # Load in new refiner
    refiner2 = OnlineCalibrationRefiner(temp_config)

    assert refiner2.state.drag_k0 == 0.15
    assert refiner2.state.time_sync_offset_ns == 1000000
    assert refiner2.state.plate_plane_z_ft == 2.5
    assert refiner2.state.last_refinement_date is not None


def test_accumulate_high_quality_trajectory(temp_config):
    """Test accumulating a high-quality trajectory."""
    refiner = OnlineCalibrationRefiner(temp_config)

    trajectory = create_high_quality_trajectory()
    accepted = refiner.accumulate_trajectory(trajectory)

    assert accepted is True
    assert refiner.state.num_trajectories_accumulated == 1
    assert len(refiner.state.trajectories_buffer) == 1
    assert len(refiner.state.epipolar_error_trend) == 1


def test_accumulate_low_quality_trajectory(temp_config):
    """Test rejecting a low-quality trajectory."""
    refiner = OnlineCalibrationRefiner(temp_config)

    trajectory = create_low_quality_trajectory()
    accepted = refiner.accumulate_trajectory(trajectory)

    assert accepted is False
    assert refiner.state.num_trajectories_accumulated == 0
    assert len(refiner.state.trajectories_buffer) == 0


def test_accumulate_multiple_trajectories(temp_config):
    """Test accumulating multiple trajectories."""
    refiner = OnlineCalibrationRefiner(temp_config)

    for i in range(25):
        trajectory = create_high_quality_trajectory()
        accepted = refiner.accumulate_trajectory(trajectory)
        assert accepted is True

    assert refiner.state.num_trajectories_accumulated == 25
    assert len(refiner.state.trajectories_buffer) == 25
    assert len(refiner.state.epipolar_error_trend) == 25


def test_should_refine_insufficient_data(temp_config):
    """Test that refinement is not triggered with insufficient data."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate less than MIN_TRAJECTORIES
    for i in range(30):
        trajectory = create_high_quality_trajectory()
        refiner.accumulate_trajectory(trajectory)

    assert refiner.should_refine() is False


def test_should_refine_sufficient_data(temp_config):
    """Test that refinement is triggered with sufficient data."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate MIN_TRAJECTORIES (50)
    for i in range(50):
        trajectory = create_high_quality_trajectory()
        refiner.accumulate_trajectory(trajectory)

    assert refiner.should_refine() is True


def test_refine_drag_coefficient_no_bias(temp_config):
    """Test drag coefficient refinement with no significant bias."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with drag_k0 close to default (0.1)
    for i in range(50):
        trajectory = create_high_quality_trajectory(drag_k0=0.1 + np.random.normal(0, 0.005))
        refiner.accumulate_trajectory(trajectory)

    result = refiner.refine_parameters()

    # Should not refine (bias < 10%)
    assert result["refined"] is False or abs(result["drag_k0_new"] - result["drag_k0_old"]) < 0.01
    assert "No significant biases" in result["reason"] or result["refined"] is False


def test_refine_drag_coefficient_with_bias(temp_config):
    """Test drag coefficient refinement with significant bias."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with drag_k0 significantly higher (0.15 vs 0.1 = 50% change)
    for i in range(50):
        trajectory = create_high_quality_trajectory(drag_k0=0.15 + np.random.normal(0, 0.005))
        refiner.accumulate_trajectory(trajectory)

    result = refiner.refine_parameters()

    # Tracker-derived bias produces a shadow proposal, never an applied mutation.
    assert result["refined"] is False
    assert result["proposed"] is True
    assert result["drag_k0_old"] == 0.1
    assert abs(result["drag_k0_new"] - 0.15) < 0.01
    assert "drag_k0" in result["reason"]


def test_refine_time_sync_offset_no_bias(temp_config):
    """Test time sync refinement with no significant bias."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with small time sync residuals (< 5ms threshold)
    for i in range(50):
        trajectory = create_high_quality_trajectory(time_sync_residual_ns=np.random.normal(0, 1e6))  # ±1ms noise
        refiner.accumulate_trajectory(trajectory)

    result = refiner.refine_parameters()

    # Should not refine (bias < 5ms)
    assert result["time_sync_offset_old"] == 0
    # Time sync might change slightly, but should be small
    assert abs(result["time_sync_offset_new"]) < 5e6  # Less than 5ms


def test_refine_time_sync_offset_with_bias(temp_config):
    """Test time sync refinement with significant bias."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with systematic +10ms bias
    for i in range(50):
        trajectory = create_high_quality_trajectory(time_sync_residual_ns=10e6 + np.random.normal(0, 1e6))  # 10ms ± 1ms
        refiner.accumulate_trajectory(trajectory)

    result = refiner.refine_parameters()

    assert result["refined"] is False
    assert result["proposed"] is True
    assert result["time_sync_offset_old"] == 0
    assert abs(result["time_sync_offset_new"] - 10e6) < 2e6  # Within 2ms of expected


def test_refine_plate_plane_z_no_bias(temp_config):
    """Test plate plane Z refinement with no significant bias."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with plate_z close to default (0.0)
    for i in range(50):
        trajectory = create_high_quality_trajectory(plate_z=0.0 + np.random.normal(0, 0.3))  # Small variation
        refiner.accumulate_trajectory(trajectory)

    result = refiner.refine_parameters()

    # Should not refine (change < 1 foot)
    assert abs(result["plate_z_new"] - result["plate_z_old"]) < 1.0


def test_refine_plate_plane_z_with_bias(temp_config):
    """Test plate plane Z refinement with significant bias."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with plate_z at 2.5 feet (vs 0.0 default)
    for i in range(50):
        trajectory = create_high_quality_trajectory(plate_z=2.5 + np.random.normal(0, 0.2))
        refiner.accumulate_trajectory(trajectory)

    result = refiner.refine_parameters()

    assert result["refined"] is False
    assert result["proposed"] is True
    assert result["plate_z_old"] == 0.0
    assert abs(result["plate_z_new"] - 2.5) < 0.5


def test_refine_proposal_does_not_update_applied_metadata_or_config(temp_config):
    """Shadow refinement must leave the approval-bearing build unchanged."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with bias
    for i in range(50):
        trajectory = create_high_quality_trajectory(drag_k0=0.15)
        refiner.accumulate_trajectory(trajectory)

    before_count = refiner.state.refinement_count
    original = temp_config.read_bytes()
    result = refiner.refine_parameters()

    assert result["proposed"] is True
    assert result["proposal"]["requires_new_rig_revision"] is True
    assert result["proposal"]["invalidates_accuracy_approvals"] is True
    assert refiner.state.last_refinement_date is None
    assert refiner.state.refinement_count == before_count
    assert refiner.state.refinement_confidence > 0.0
    assert temp_config.read_bytes() == original


def test_refine_clears_buffer(temp_config):
    """Test that refinement clears the trajectory buffer."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories
    for i in range(50):
        trajectory = create_high_quality_trajectory()
        refiner.accumulate_trajectory(trajectory)

    assert len(refiner.state.trajectories_buffer) == 50
    assert refiner.state.num_trajectories_accumulated == 50

    refiner.refine_parameters()

    # Buffer should be cleared
    assert len(refiner.state.trajectories_buffer) == 0
    assert refiner.state.num_trajectories_accumulated == 0


def test_trajectory_stats_dataclass():
    """Test TrajectoryStats dataclass."""
    stats = TrajectoryStats(
        timestamp_ns=123456789,
        drag_k0_fit=0.12,
        time_sync_residual_ns=1000000,
        plate_crossing_z_ft=2.5,
        mean_epipolar_error_px=1.5,
        max_epipolar_error_px=2.5,
        num_observations=20,
        confidence_score=0.9,
    )

    assert stats.timestamp_ns == 123456789
    assert stats.drag_k0_fit == 0.12
    assert stats.confidence_score == 0.9


def test_refine_with_mixed_quality_trajectories(temp_config):
    """Test refinement with mix of accepted and rejected trajectories."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate mix of high and low quality
    accepted_count = 0
    for i in range(80):
        if i % 3 == 0:
            # Low quality (will be rejected)
            trajectory = create_low_quality_trajectory()
        else:
            # High quality (will be accepted)
            trajectory = create_high_quality_trajectory(drag_k0=0.15)
            accepted_count += 1

        refiner.accumulate_trajectory(trajectory)

    # Should only accumulate high quality ones
    assert refiner.state.num_trajectories_accumulated == accepted_count
    assert refiner.state.num_trajectories_accumulated >= 50  # Enough for refinement

    result = refiner.refine_parameters()
    assert result["refined"] is False
    assert result["proposed"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

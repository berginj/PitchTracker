"""Unit tests for online calibration refinement."""

import pytest
from pathlib import Path
import tempfile
import yaml
from datetime import datetime, timedelta

# Import the online refinement classes
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from calib.online_refinement import (  # noqa: E402
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


def test_validate_calibration_health_insufficient_data(temp_config):
    """Test calibration health with insufficient data."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Only 5 trajectories
    for i in range(5):
        trajectory = create_high_quality_trajectory()
        refiner.accumulate_trajectory(trajectory)

    health = refiner.validate_calibration_health()

    assert health["healthy"] is True
    assert health["trend"] == "unknown"
    assert health["alert"] is False
    assert "Insufficient data" in health["reason"]


def test_validate_calibration_health_stable(temp_config):
    """Test calibration health with stable errors."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with consistent low error
    for i in range(30):
        trajectory = create_high_quality_trajectory(epipolar_error=1.0)
        refiner.accumulate_trajectory(trajectory)

    health = refiner.validate_calibration_health()

    assert health["healthy"] is True
    assert health["mean_error_px"] < 2.0
    assert health["trend"] == "stable"
    assert health["alert"] is False


def test_validate_calibration_health_improving(temp_config):
    """Test calibration health with improving trend."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with clearly decreasing error
    # Use steeper slope to ensure clear 'improving' classification
    for i in range(30):
        error = 5.0 - (i * 0.15)  # Error decreases from 5.0 to 0.5 (slope=-0.15)
        trajectory = create_high_quality_trajectory(epipolar_error=error)
        refiner.accumulate_trajectory(trajectory)

    health = refiner.validate_calibration_health()

    assert health["trend"] == "improving"


def test_validate_calibration_health_degrading(temp_config):
    """Test calibration health with degrading trend."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with clearly increasing error. Errors must stay
    # within MAX_EPIPOLAR_ERROR (2.0px) to be accepted; using a per-step slope of
    # 0.125 keeps the regression slope comfortably above the 0.1 "degrading"
    # threshold rather than landing exactly on it (a floating-point knife-edge).
    for i in range(13):
        error = 0.5 + (i * 0.125)  # 0.5 -> 2.0 over 13 points, slope 0.125
        trajectory = create_high_quality_trajectory(epipolar_error=error)
        refiner.accumulate_trajectory(trajectory)

    health = refiner.validate_calibration_health()

    assert health["trend"] == "degrading"


def test_validate_calibration_health_high_error_alert(temp_config):
    """Test calibration health alert for high error."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate trajectories with high error (> 5px threshold)
    for i in range(30):
        trajectory = create_high_quality_trajectory(epipolar_error=6.0)
        # Override quality check
        trajectory["mean_epipolar_error_px"] = 6.0
        trajectory["confidence_score"] = 0.75  # Still high enough
        refiner.state.trajectories_buffer.append(trajectory)
        refiner.state.num_trajectories_accumulated += 1
        refiner.state.epipolar_error_trend.append(6.0)

    health = refiner.validate_calibration_health()

    assert health["healthy"] is False
    assert health["alert"] is True
    assert health["mean_error_px"] > 5.0
    assert "Alert" in health["reason"] or "Recalibration" in health["reason"]


def test_validate_calibration_health_recalibration_interval(temp_config):
    """Test calibration health alert for recalibration interval."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Set last refinement to 40 days ago (> 30 day threshold)
    old_date = datetime.now() - timedelta(days=40)
    refiner.state.last_refinement_date = old_date.isoformat()

    # Accumulate some trajectories with low error
    for i in range(20):
        trajectory = create_high_quality_trajectory(epipolar_error=1.0)
        refiner.accumulate_trajectory(trajectory)

    health = refiner.validate_calibration_health()

    # Should alert due to interval, even with low error
    assert health["alert"] is True
    assert "40 days" in health["reason"] or "Recalibration" in health["reason"]


def test_get_refinement_summary(temp_config):
    """Test getting refinement summary."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate some trajectories
    for i in range(25):
        trajectory = create_high_quality_trajectory()
        refiner.accumulate_trajectory(trajectory)

    summary = refiner.get_refinement_summary()

    assert "drag_k0" in summary
    assert "time_sync_offset_ns" in summary
    assert "plate_plane_z_ft" in summary
    assert summary["trajectories_accumulated"] == 25
    assert summary["refinement_count"] == 0
    assert summary["calibration_healthy"] is True
    assert "mean_epipolar_error_px" in summary
    assert "error_trend" in summary


def test_epipolar_error_trend_limit(temp_config):
    """Test that epipolar error trend is limited to last 100 trajectories."""
    refiner = OnlineCalibrationRefiner(temp_config)

    # Accumulate 150 trajectories
    for i in range(150):
        trajectory = create_high_quality_trajectory()
        refiner.accumulate_trajectory(trajectory)

    # Should only keep last 100
    assert len(refiner.state.epipolar_error_trend) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

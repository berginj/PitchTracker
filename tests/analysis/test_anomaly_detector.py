"""Tests for anomaly detection."""

import pytest
import numpy as np

from analysis.pattern_detection.anomaly_detector import detect_anomalies
from analysis.pattern_detection.schemas import Anomaly


class TestAnomalyDetection:
    """Test anomaly detection functionality."""

    def test_no_anomalies_normal_pitches(self):
        """Test that normal pitches don't trigger anomalies."""
        pitches = [
            {'pitch_id': f'p{i}', 'speed_mph': 85.0 + i * 0.5} 
            for i in range(10)
        ]

        anomalies = detect_anomalies(pitches)

        # With small variation, no Z-score > 3
        speed_anomalies = [a for a in anomalies if a.anomaly_type == "speed_outlier"]
        assert len(speed_anomalies) == 0

    def test_speed_outlier_detection_high(self):
        """Test detection of unusually fast pitch."""
        pitches = [
            {'pitch_id': f'p{i}', 'speed_mph': 85.0}
            for i in range(10)
        ]
        pitches.append({'pitch_id': 'outlier', 'speed_mph': 105.0})  # Way too fast

        anomalies = detect_anomalies(pitches)

        speed_anomalies = [a for a in anomalies if a.anomaly_type == "speed_outlier"]
        assert len(speed_anomalies) > 0
        assert speed_anomalies[0].pitch_id == 'outlier'
        assert speed_anomalies[0].severity in ["medium", "high"]

    def test_speed_outlier_detection_low(self):
        """Test detection of unusually slow pitch."""
        pitches = [
            {'pitch_id': f'p{i}', 'speed_mph': 85.0}
            for i in range(10)
        ]
        pitches.append({'pitch_id': 'outlier', 'speed_mph': 50.0})  # Way too slow

        anomalies = detect_anomalies(pitches)

        speed_anomalies = [a for a in anomalies if a.anomaly_type == "speed_outlier"]
        assert len(speed_anomalies) > 0
        assert speed_anomalies[0].pitch_id == 'outlier'

    def test_trajectory_quality_high_rmse(self):
        """Test detection of poor trajectory quality (high RMSE)."""
        pitches = [
            {
                'pitch_id': f'p{i}',
                'speed_mph': 85.0,
                'trajectory_expected_error_ft': 0.2,
                'trajectory_confidence': 0.9,
                'sample_count': 20
            }
            for i in range(5)
        ]
        # Add one with high RMSE
        pitches.append({
            'pitch_id': 'bad_traj',
            'speed_mph': 85.0,
            'trajectory_expected_error_ft': 1.5,  # High error
            'trajectory_confidence': 0.9,
            'sample_count': 20
        })

        anomalies = detect_anomalies(pitches)

        traj_anomalies = [a for a in anomalies if a.anomaly_type == "trajectory_quality"]
        assert len(traj_anomalies) > 0
        assert traj_anomalies[0].severity == "high"
        assert "high trajectory error" in traj_anomalies[0].recommendation

    def test_trajectory_quality_low_trajectory_confidence(self):
        """Test detection of low inlier ratio."""
        pitches = [
            {
                'pitch_id': f'p{i}',
                'speed_mph': 85.0,
                'trajectory_expected_error_ft': 0.2,
                'trajectory_confidence': 0.9,
                'sample_count': 20
            }
            for i in range(5)
        ]
        # Add one with low inlier ratio
        pitches.append({
            'pitch_id': 'bad_inlier',
            'speed_mph': 85.0,
            'trajectory_expected_error_ft': 0.2,
            'trajectory_confidence': 0.5,  # Low inlier ratio
            'sample_count': 20
        })

        anomalies = detect_anomalies(pitches)

        traj_anomalies = [a for a in anomalies if a.anomaly_type == "trajectory_quality"]
        assert len(traj_anomalies) > 0
        assert "low trajectory confidence" in traj_anomalies[0].recommendation

    def test_trajectory_quality_insufficient_samples(self):
        """Test detection of insufficient sample count."""
        pitches = [
            {
                'pitch_id': f'p{i}',
                'speed_mph': 85.0,
                'trajectory_expected_error_ft': 0.2,
                'trajectory_confidence': 0.9,
                'sample_count': 20
            }
            for i in range(5)
        ]
        # Add one with too few samples
        pitches.append({
            'pitch_id': 'bad_samples',
            'speed_mph': 85.0,
            'trajectory_expected_error_ft': 0.2,
            'trajectory_confidence': 0.9,
            'sample_count': 5  # Too few samples
        })

        anomalies = detect_anomalies(pitches)

        traj_anomalies = [a for a in anomalies if a.anomaly_type == "trajectory_quality"]
        assert len(traj_anomalies) > 0
        assert "insufficient samples" in traj_anomalies[0].recommendation

    def test_insufficient_data(self):
        """Test that insufficient data returns no anomalies."""
        pitches = [
            {'pitch_id': 'p1', 'speed_mph': 85.0},
            {'pitch_id': 'p2', 'speed_mph': 90.0}
        ]

        anomalies = detect_anomalies(pitches)

        # Need at least 5 pitches
        assert len(anomalies) == 0

    def test_missing_speed_data(self):
        """Test handling of missing speed data."""
        pitches = [
            {'pitch_id': 'p1'},  # No speed
            {'pitch_id': 'p2'},
            {'pitch_id': 'p3'},
            {'pitch_id': 'p4'},
            {'pitch_id': 'p5'}
        ]

        anomalies = detect_anomalies(pitches)

        # Should not crash, returns empty
        assert len(anomalies) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

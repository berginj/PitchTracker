"""Unit tests for anomaly detection algorithms."""

import unittest
from typing import List

from analysis.pattern_detection.anomaly_detector import (
    detect_speed_anomalies,
    detect_movement_anomalies,
    detect_trajectory_quality_anomalies,
    detect_all_anomalies,
)


class MockPitch:
    """Mock pitch for testing."""

    def __init__(self, pitch_id: str, speed_mph: float = None, run_in: float = None,
                 rise_in: float = None, sample_count: int = 50):
        self.pitch_id = pitch_id
        self.speed_mph = speed_mph
        self.run_in = run_in
        self.rise_in = rise_in
        self.sample_count = sample_count
        self.trajectory_expected_error_ft = 0.2  # Default good quality
        self.trajectory_confidence = 0.9


class TestAnomalyDetector(unittest.TestCase):
    """Test anomaly detection algorithms."""

    def test_detect_speed_anomalies_normal(self):
        """Test speed anomaly detection with normal pitches."""
        pitches = [
            MockPitch("p1", speed_mph=85.0),
            MockPitch("p2", speed_mph=86.0),
            MockPitch("p3", speed_mph=84.5),
            MockPitch("p4", speed_mph=85.5),
            MockPitch("p5", speed_mph=85.2),
        ]

        anomalies = detect_speed_anomalies(pitches, z_threshold=3.0, iqr_multiplier=1.5)

        self.assertEqual(len(anomalies), 0, "No anomalies should be detected in normal data")

    def test_detect_speed_anomalies_outlier(self):
        """Test speed anomaly detection with clear outlier."""
        # Create more data points for reliable statistics
        pitches = [
            MockPitch("p1", speed_mph=85.0),
            MockPitch("p2", speed_mph=86.0),
            MockPitch("p3", speed_mph=84.5),
            MockPitch("p4", speed_mph=85.5),
            MockPitch("p5", speed_mph=85.2),
            MockPitch("p6", speed_mph=84.8),
            MockPitch("p7", speed_mph=85.3),
            MockPitch("p8", speed_mph=84.7),
            MockPitch("p9", speed_mph=85.1),
            MockPitch("p10", speed_mph=100.0),  # Extreme outlier
        ]

        anomalies = detect_speed_anomalies(pitches, z_threshold=2.0, iqr_multiplier=1.5)

        self.assertGreater(len(anomalies), 0, "Outlier should be detected")
        self.assertEqual(anomalies[0].pitch_id, "p10")
        self.assertIn("speed", anomalies[0].anomaly_type.lower())

    def test_detect_speed_anomalies_insufficient_data(self):
        """Test speed anomaly detection with insufficient data."""
        pitches = [MockPitch("p1", speed_mph=85.0)]

        anomalies = detect_speed_anomalies(pitches, z_threshold=3.0, iqr_multiplier=1.5)

        self.assertEqual(len(anomalies), 0, "Single pitch should not trigger anomaly")

    def test_detect_speed_anomalies_missing_speed(self):
        """Test speed anomaly detection with missing speed data."""
        pitches = [
            MockPitch("p1", speed_mph=None),
            MockPitch("p2", speed_mph=85.0),
            MockPitch("p3", speed_mph=None),
        ]

        anomalies = detect_speed_anomalies(pitches, z_threshold=3.0, iqr_multiplier=1.5)

        self.assertEqual(len(anomalies), 0, "Missing data should be handled gracefully")

    def test_detect_movement_anomalies_normal(self):
        """Test movement anomaly detection with normal pitches."""
        pitches = [
            MockPitch("p1", run_in=2.0, rise_in=-1.0),
            MockPitch("p2", run_in=2.2, rise_in=-1.2),
            MockPitch("p3", run_in=1.8, rise_in=-0.8),
            MockPitch("p4", run_in=2.1, rise_in=-1.1),
            MockPitch("p5", run_in=1.9, rise_in=-0.9),
        ]

        anomalies = detect_movement_anomalies(pitches, z_threshold=3.0, iqr_multiplier=1.5)

        self.assertEqual(len(anomalies), 0, "No anomalies should be detected in normal data")

    def test_detect_movement_anomalies_outlier(self):
        """Test movement anomaly detection with clear outlier."""
        # Create more data points for reliable statistics
        pitches = [
            MockPitch("p1", run_in=2.0, rise_in=-1.0),
            MockPitch("p2", run_in=2.2, rise_in=-1.2),
            MockPitch("p3", run_in=2.1, rise_in=-1.1),
            MockPitch("p4", run_in=1.9, rise_in=-0.9),
            MockPitch("p5", run_in=2.0, rise_in=-1.0),
            MockPitch("p6", run_in=2.1, rise_in=-1.1),
            MockPitch("p7", run_in=2.0, rise_in=-1.0),
            MockPitch("p8", run_in=2.2, rise_in=-1.2),
            MockPitch("p9", run_in=1.9, rise_in=-0.9),
            MockPitch("p10", run_in=15.0, rise_in=-12.0),  # Extreme outlier
        ]

        anomalies = detect_movement_anomalies(pitches, z_threshold=2.0, iqr_multiplier=1.5)

        self.assertGreater(len(anomalies), 0, "Outlier should be detected")

        # Find the anomaly for p10
        p10_anomalies = [a for a in anomalies if a.pitch_id == "p10"]
        self.assertGreater(len(p10_anomalies), 0)

    def test_detect_trajectory_quality_anomalies_good_quality(self):
        """Test trajectory quality detection with good quality pitches."""
        pitches = [
            MockPitch("p1", sample_count=50),
            MockPitch("p2", sample_count=55),
            MockPitch("p3", sample_count=48),
        ]

        for pitch in pitches:
            pitch.trajectory_expected_error_ft = 0.2
            pitch.trajectory_confidence = 0.9

        anomalies = detect_trajectory_quality_anomalies(pitches)

        self.assertEqual(len(anomalies), 0, "Good quality pitches should not be flagged")

    def test_detect_trajectory_quality_anomalies_low_samples(self):
        """Test trajectory quality detection with low sample count."""
        pitches = [
            MockPitch("p1", sample_count=50),
            MockPitch("p2", sample_count=5),  # Low sample count
            MockPitch("p3", sample_count=48),
        ]

        for pitch in pitches:
            pitch.trajectory_expected_error_ft = 0.2
            pitch.trajectory_confidence = 0.9

        anomalies = detect_trajectory_quality_anomalies(pitches)

        self.assertGreater(len(anomalies), 0, "Low sample count should be detected")
        self.assertEqual(anomalies[0].pitch_id, "p2")
        # Check for trajectory quality type (includes low sample count)
        self.assertIn("trajectory", anomalies[0].anomaly_type.lower())

    def test_detect_trajectory_quality_anomalies_high_error(self):
        """Test trajectory quality detection with high trajectory error."""
        pitches = [
            MockPitch("p1", sample_count=50),
            MockPitch("p2", sample_count=50),
            MockPitch("p3", sample_count=50),
        ]

        pitches[0].trajectory_expected_error_ft = 0.2
        pitches[1].trajectory_expected_error_ft = 1.5  # High error
        pitches[2].trajectory_expected_error_ft = 0.2

        for pitch in pitches:
            pitch.trajectory_confidence = 0.9

        anomalies = detect_trajectory_quality_anomalies(pitches)

        self.assertGreater(len(anomalies), 0, "High error should be detected")

        # Find the anomaly for p2
        p2_anomalies = [a for a in anomalies if a.pitch_id == "p2"]
        self.assertGreater(len(p2_anomalies), 0)

    def test_detect_all_anomalies_normal(self):
        """Test detect_all_anomalies with normal pitches."""
        pitches = [
            MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0, sample_count=50),
            MockPitch("p2", speed_mph=86.0, run_in=2.2, rise_in=-1.2, sample_count=55),
            MockPitch("p3", speed_mph=84.5, run_in=1.8, rise_in=-0.8, sample_count=48),
            MockPitch("p4", speed_mph=85.5, run_in=2.1, rise_in=-1.1, sample_count=52),
            MockPitch("p5", speed_mph=85.2, run_in=1.9, rise_in=-0.9, sample_count=50),
        ]

        for pitch in pitches:
            pitch.trajectory_expected_error_ft = 0.2
            pitch.trajectory_confidence = 0.9

        anomalies = detect_all_anomalies(pitches, z_threshold=3.0, iqr_multiplier=1.5)

        self.assertEqual(len(anomalies), 0, "No anomalies should be detected in normal data")

    def test_detect_all_anomalies_multiple_types(self):
        """Test detect_all_anomalies with multiple anomaly types."""
        # Create more data points for reliable statistics
        pitches = [
            MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0, sample_count=50),
            MockPitch("p2", speed_mph=85.5, run_in=2.1, rise_in=-1.1, sample_count=50),
            MockPitch("p3", speed_mph=84.5, run_in=1.9, rise_in=-0.9, sample_count=50),
            MockPitch("p4", speed_mph=85.2, run_in=2.0, rise_in=-1.0, sample_count=50),
            MockPitch("p5", speed_mph=84.8, run_in=2.2, rise_in=-1.2, sample_count=50),
            MockPitch("p6", speed_mph=85.3, run_in=2.0, rise_in=-1.0, sample_count=50),
            MockPitch("p7", speed_mph=84.7, run_in=2.1, rise_in=-1.1, sample_count=50),
            MockPitch("p8", speed_mph=85.1, run_in=1.9, rise_in=-0.9, sample_count=50),
            MockPitch("p9", speed_mph=100.0, run_in=2.0, rise_in=-1.0, sample_count=55),  # Extreme speed outlier
            MockPitch("p10", speed_mph=85.0, run_in=15.0, rise_in=-12.0, sample_count=48),  # Extreme movement outlier
            MockPitch("p11", speed_mph=85.0, run_in=2.0, rise_in=-1.0, sample_count=5),  # Low samples
        ]

        for pitch in pitches:
            pitch.trajectory_expected_error_ft = 0.2
            pitch.trajectory_confidence = 0.9

        anomalies = detect_all_anomalies(pitches, z_threshold=2.0, iqr_multiplier=1.5)

        self.assertGreater(len(anomalies), 0, "Multiple anomalies should be detected")

        # Check that different anomaly types are present
        anomaly_types = {a.anomaly_type for a in anomalies}
        self.assertGreater(len(anomaly_types), 1, "Multiple anomaly types should be detected")

    def test_anomaly_severity_levels(self):
        """Test that anomaly severity levels are correctly assigned."""
        pitches = [
            MockPitch("p1", speed_mph=85.0),
            MockPitch("p2", speed_mph=86.0),
            MockPitch("p3", speed_mph=84.5),
            MockPitch("p4", speed_mph=85.5),
            MockPitch("p5", speed_mph=100.0),  # Extreme outlier
        ]

        anomalies = detect_all_anomalies(pitches, z_threshold=2.0, iqr_multiplier=1.5)

        if len(anomalies) > 0:
            # Check that severity is one of the valid values
            for anomaly in anomalies:
                self.assertIn(anomaly.severity, ["low", "medium", "high"])

    def test_anomaly_has_recommendation(self):
        """Test that detected anomalies have recommendations."""
        pitches = [
            MockPitch("p1", speed_mph=85.0, sample_count=50),
            MockPitch("p2", speed_mph=95.0, sample_count=5),  # Multiple issues
        ]

        pitches[0].trajectory_expected_error_ft = 0.2
        pitches[1].trajectory_expected_error_ft = 0.2

        for pitch in pitches:
            pitch.trajectory_confidence = 0.9

        anomalies = detect_all_anomalies(pitches, z_threshold=2.0, iqr_multiplier=1.5)

        for anomaly in anomalies:
            self.assertIsNotNone(anomaly.recommendation)
            self.assertGreater(len(anomaly.recommendation), 0, "Recommendation should not be empty")


if __name__ == '__main__':
    unittest.main()

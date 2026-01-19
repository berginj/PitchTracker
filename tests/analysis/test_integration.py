"""Integration tests for pattern detection system."""

import json
import tempfile
import unittest
from pathlib import Path

from analysis.pattern_detection.detector import PatternDetector


class TestPatternDetectionIntegration(unittest.TestCase):
    """Integration tests for the full pattern detection workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.session_dir = Path(self.temp_dir) / "test_session"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.profiles_dir = Path(self.temp_dir) / "pitcher_profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _create_session_summary(self, pitches_data):
        """Create a session_summary.json file for testing."""
        summary_path = self.session_dir / "session_summary.json"

        session_data = {
            "session_id": "test_session",
            "created_utc": "2026-01-19T12:00:00Z",
            "pitches": pitches_data
        }

        with open(summary_path, 'w') as f:
            json.dump(session_data, f, indent=2)

    def test_analyze_session_end_to_end(self):
        """Test full session analysis workflow."""
        # Create test data
        pitches_data = [
            {
                "pitch_id": "pitch_001",
                "t_start_ns": 1000000000,
                "t_end_ns": 2000000000,
                "is_strike": True,
                "zone_row": 1,
                "zone_col": 1,
                "run_in": 2.0,
                "rise_in": -1.0,
                "speed_mph": 85.0,
                "rotation_rpm": 2200,
                "sample_count": 50,
                "trajectory_expected_error_ft": 0.2,
                "trajectory_confidence": 0.9
            },
            {
                "pitch_id": "pitch_002",
                "t_start_ns": 3000000000,
                "t_end_ns": 4000000000,
                "is_strike": True,
                "zone_row": 1,
                "zone_col": 2,
                "run_in": 2.2,
                "rise_in": -1.2,
                "speed_mph": 86.0,
                "rotation_rpm": 2250,
                "sample_count": 55,
                "trajectory_expected_error_ft": 0.18,
                "trajectory_confidence": 0.92
            },
            {
                "pitch_id": "pitch_003",
                "t_start_ns": 5000000000,
                "t_end_ns": 6000000000,
                "is_strike": False,
                "zone_row": 0,
                "zone_col": 0,
                "run_in": 1.8,
                "rise_in": -0.8,
                "speed_mph": 84.5,
                "rotation_rpm": 2180,
                "sample_count": 48,
                "trajectory_expected_error_ft": 0.22,
                "trajectory_confidence": 0.88
            },
            {
                "pitch_id": "pitch_004",
                "t_start_ns": 7000000000,
                "t_end_ns": 8000000000,
                "is_strike": True,
                "zone_row": 1,
                "zone_col": 1,
                "run_in": 6.0,
                "rise_in": -2.0,
                "speed_mph": 82.0,
                "rotation_rpm": 2400,
                "sample_count": 52,
                "trajectory_expected_error_ft": 0.19,
                "trajectory_confidence": 0.91
            },
            {
                "pitch_id": "pitch_005",
                "t_start_ns": 9000000000,
                "t_end_ns": 10000000000,
                "is_strike": False,
                "zone_row": 2,
                "zone_col": 1,
                "run_in": 2.0,
                "rise_in": -5.0,
                "speed_mph": 75.0,
                "rotation_rpm": 2600,
                "sample_count": 50,
                "trajectory_expected_error_ft": 0.21,
                "trajectory_confidence": 0.89
            }
        ]

        self._create_session_summary(pitches_data)

        # Run analysis
        detector = PatternDetector(profiles_dir=self.profiles_dir)
        report = detector.analyze_session(
            self.session_dir,
            pitcher_id=None,
            output_json=True,
            output_html=True
        )

        # Verify report structure
        self.assertIsNotNone(report)
        self.assertEqual(report.session_id, "test_session")
        self.assertEqual(report.summary.total_pitches, 5)

        # Verify output files were created
        json_path = self.session_dir / "analysis_report.json"
        html_path = self.session_dir / "analysis_report.html"

        self.assertTrue(json_path.exists())
        self.assertTrue(html_path.exists())

        # Verify JSON report content
        with open(json_path, 'r') as f:
            json_report = json.load(f)

        self.assertEqual(json_report['session_id'], "test_session")
        self.assertEqual(json_report['summary']['total_pitches'], 5)
        self.assertIn('pitch_classification', json_report)
        self.assertIn('anomalies', json_report)

        # Verify pitch classification
        self.assertEqual(len(report.pitch_classification), 5)
        for classification in report.pitch_classification:
            self.assertIsNotNone(classification.heuristic_type)
            self.assertIsNotNone(classification.cluster_id)

        # Verify pitch types detected
        pitch_types = {c.heuristic_type for c in report.pitch_classification}
        self.assertGreater(len(pitch_types), 1, "Should detect multiple pitch types")

    def test_analyze_session_insufficient_data(self):
        """Test analysis with insufficient data."""
        # Create session with < 5 pitches
        pitches_data = [
            {
                "pitch_id": "pitch_001",
                "t_start_ns": 1000000000,
                "t_end_ns": 2000000000,
                "is_strike": True,
                "speed_mph": 85.0,
                "run_in": 2.0,
                "rise_in": -1.0,
                "sample_count": 50
            }
        ]

        self._create_session_summary(pitches_data)

        detector = PatternDetector(profiles_dir=self.profiles_dir)
        report = detector.analyze_session(self.session_dir, output_json=True, output_html=False)

        # Should return report with error
        self.assertEqual(report.summary.total_pitches, 1)

        # Should create error JSON
        json_path = self.session_dir / "analysis_report.json"
        self.assertTrue(json_path.exists())

        with open(json_path, 'r') as f:
            json_data = json.load(f)

        self.assertIn('error', json_data)
        self.assertEqual(json_data['error'], 'insufficient_data')

    def test_analyze_session_with_baseline(self):
        """Test session analysis with baseline comparison."""
        # Create baseline profile
        baseline_pitches_data = []
        for i in range(10):
            baseline_pitches_data.append({
                "pitch_id": f"baseline_{i}",
                "t_start_ns": i * 1000000000,
                "t_end_ns": (i + 1) * 1000000000,
                "is_strike": True,
                "speed_mph": 85.0 + (i % 3),  # 85, 86, 87 mph
                "run_in": 2.0,
                "rise_in": -1.0,
                "sample_count": 50
            })

        baseline_session_dir = Path(self.temp_dir) / "baseline_session"
        baseline_session_dir.mkdir(parents=True, exist_ok=True)

        baseline_summary_path = baseline_session_dir / "session_summary.json"
        with open(baseline_summary_path, 'w') as f:
            json.dump({"pitches": baseline_pitches_data}, f)

        # Create profile
        detector = PatternDetector(profiles_dir=self.profiles_dir)
        detector.create_pitcher_profile("test_pitcher", [baseline_session_dir])

        # Create current session with similar performance
        current_pitches_data = [
            {
                "pitch_id": f"current_{i}",
                "t_start_ns": i * 1000000000,
                "t_end_ns": (i + 1) * 1000000000,
                "is_strike": True,
                "speed_mph": 85.5 + (i % 2),  # Similar velocity
                "run_in": 2.0,
                "rise_in": -1.0,
                "sample_count": 50
            }
            for i in range(5)
        ]

        self._create_session_summary(current_pitches_data)

        # Analyze with baseline comparison
        report = detector.analyze_session(
            self.session_dir,
            pitcher_id="test_pitcher",
            output_json=True,
            output_html=False
        )

        # Verify baseline comparison exists
        self.assertIsNotNone(report.baseline_comparison)
        self.assertTrue(report.baseline_comparison.profile_exists)
        self.assertIsNotNone(report.baseline_comparison.velocity_vs_baseline)

        # Verify comparison data
        velocity_comparison = report.baseline_comparison.velocity_vs_baseline
        self.assertIn('current', velocity_comparison)
        self.assertIn('baseline', velocity_comparison)
        self.assertIn('status', velocity_comparison)

    def test_create_pitcher_profile_multiple_sessions(self):
        """Test creating pitcher profile from multiple sessions."""
        detector = PatternDetector(profiles_dir=self.profiles_dir)

        # Create multiple sessions
        session_dirs = []
        for session_num in range(3):
            session_dir = Path(self.temp_dir) / f"session_{session_num}"
            session_dir.mkdir(parents=True, exist_ok=True)

            pitches_data = []
            for i in range(10):
                pitches_data.append({
                    "pitch_id": f"s{session_num}_p{i}",
                    "t_start_ns": i * 1000000000,
                    "t_end_ns": (i + 1) * 1000000000,
                    "is_strike": True,
                    "speed_mph": 85.0 + (i % 3),
                    "run_in": 2.0,
                    "rise_in": -1.0,
                    "sample_count": 50
                })

            summary_path = session_dir / "session_summary.json"
            with open(summary_path, 'w') as f:
                json.dump({"pitches": pitches_data}, f)

            session_dirs.append(session_dir)

        # Create profile
        detector.create_pitcher_profile("multi_session_pitcher", session_dirs)

        # Verify profile was created
        profile = detector.profile_manager.load_profile("multi_session_pitcher")

        self.assertIsNotNone(profile)
        self.assertEqual(profile.sessions_analyzed, 3)
        self.assertEqual(profile.total_pitches, 30)  # 10 pitches × 3 sessions

    def test_json_report_schema_compliance(self):
        """Test that JSON report matches expected schema."""
        pitches_data = [
            {
                "pitch_id": f"pitch_{i:03d}",
                "t_start_ns": i * 1000000000,
                "t_end_ns": (i + 1) * 1000000000,
                "is_strike": True,
                "speed_mph": 85.0 + (i % 3),
                "run_in": 2.0,
                "rise_in": -1.0,
                "sample_count": 50,
                "trajectory_expected_error_ft": 0.2,
                "trajectory_confidence": 0.9
            }
            for i in range(5)
        ]

        self._create_session_summary(pitches_data)

        detector = PatternDetector(profiles_dir=self.profiles_dir)
        detector.analyze_session(self.session_dir, output_json=True, output_html=False)

        json_path = self.session_dir / "analysis_report.json"
        with open(json_path, 'r') as f:
            report = json.load(f)

        # Verify required top-level fields
        required_fields = [
            'schema_version',
            'created_utc',
            'session_id',
            'summary',
            'pitch_classification',
            'anomalies',
            'pitch_repertoire',
            'consistency_metrics'
        ]

        for field in required_fields:
            self.assertIn(field, report, f"Missing required field: {field}")

        # Verify summary structure
        summary_fields = [
            'total_pitches',
            'anomalies_detected',
            'pitch_types_detected',
            'average_velocity_mph',
            'strike_percentage'
        ]

        for field in summary_fields:
            self.assertIn(field, report['summary'], f"Missing summary field: {field}")

    def test_html_report_generation(self):
        """Test that HTML report is generated successfully."""
        pitches_data = [
            {
                "pitch_id": f"pitch_{i:03d}",
                "t_start_ns": i * 1000000000,
                "t_end_ns": (i + 1) * 1000000000,
                "is_strike": True,
                "zone_row": i % 3,
                "zone_col": i % 3,
                "speed_mph": 85.0 + (i % 3),
                "run_in": 2.0 + (i % 2),
                "rise_in": -1.0 - (i % 2),
                "sample_count": 50,
                "trajectory_expected_error_ft": 0.2,
                "trajectory_confidence": 0.9
            }
            for i in range(10)
        ]

        self._create_session_summary(pitches_data)

        detector = PatternDetector(profiles_dir=self.profiles_dir)
        detector.analyze_session(self.session_dir, output_json=False, output_html=True)

        html_path = self.session_dir / "analysis_report.html"
        self.assertTrue(html_path.exists())

        # Verify HTML content
        html_content = html_path.read_text()

        # Check for key sections
        self.assertIn("Pattern Detection Analysis Report", html_content)
        self.assertIn("Executive Summary", html_content)
        self.assertIn("Pitch Classification", html_content)
        self.assertIn("Velocity Analysis", html_content)
        self.assertIn("Movement Profile", html_content)
        self.assertIn("Strike Zone Distribution", html_content)

        # Check for embedded charts (base64 images)
        self.assertIn("data:image/png;base64,", html_content)


if __name__ == '__main__':
    unittest.main()

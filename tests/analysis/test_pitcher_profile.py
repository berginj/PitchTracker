"""Unit tests for pitcher profile management."""

import json
import tempfile
import unittest
from pathlib import Path

from analysis.pattern_detection.pitcher_profile import (
    PitcherProfile,
    PitcherProfileManager,
    ProfileMetrics,
)


class MockPitch:
    """Mock pitch for testing."""

    def __init__(self, pitch_id: str, speed_mph: float = None, run_in: float = None,
                 rise_in: float = None, is_strike: bool = False):
        self.pitch_id = pitch_id
        self.speed_mph = speed_mph
        self.run_in = run_in
        self.rise_in = rise_in
        self.is_strike = is_strike


class TestPitcherProfile(unittest.TestCase):
    """Test pitcher profile functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.profiles_dir = Path(self.temp_dir) / "pitcher_profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def test_profile_manager_initialization(self):
        """Test PitcherProfileManager initialization."""
        manager = PitcherProfileManager(self.profiles_dir)

        self.assertEqual(manager.profiles_dir, self.profiles_dir)
        self.assertTrue(self.profiles_dir.exists())

    def test_create_profile_with_valid_data(self):
        """Test creating a pitcher profile with valid data."""
        manager = PitcherProfileManager(self.profiles_dir)

        pitches = [
            MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0, is_strike=True),
            MockPitch("p2", speed_mph=86.0, run_in=2.2, rise_in=-1.2, is_strike=True),
            MockPitch("p3", speed_mph=84.5, run_in=1.8, rise_in=-0.8, is_strike=False),
            MockPitch("p4", speed_mph=85.5, run_in=2.1, rise_in=-1.1, is_strike=True),
            MockPitch("p5", speed_mph=85.2, run_in=1.9, rise_in=-0.9, is_strike=False),
        ]

        profile = manager.create_or_update_profile("test_pitcher", pitches)

        self.assertIsInstance(profile, PitcherProfile)
        self.assertEqual(profile.pitcher_id, "test_pitcher")
        self.assertEqual(profile.total_pitches, 5)
        self.assertEqual(profile.sessions_analyzed, 1)

        # Check baseline metrics exist
        self.assertIsNotNone(profile.baseline_metrics)
        self.assertIsInstance(profile.baseline_metrics, ProfileMetrics)

        # Check velocity metrics
        self.assertAlmostEqual(profile.baseline_metrics.velocity.mean, 85.24, places=1)
        self.assertGreater(profile.baseline_metrics.velocity.p50, 84.0)
        self.assertLess(profile.baseline_metrics.velocity.p50, 86.0)

    def test_save_and_load_profile(self):
        """Test saving and loading a pitcher profile."""
        manager = PitcherProfileManager(self.profiles_dir)

        pitches = [
            MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0, is_strike=True),
            MockPitch("p2", speed_mph=86.0, run_in=2.2, rise_in=-1.2, is_strike=True),
            MockPitch("p3", speed_mph=84.5, run_in=1.8, rise_in=-0.8, is_strike=False),
        ]

        # Create and save profile
        original_profile = manager.create_or_update_profile("test_pitcher", pitches)

        # Load profile
        loaded_profile = manager.load_profile("test_pitcher")

        self.assertIsNotNone(loaded_profile)
        self.assertEqual(loaded_profile.pitcher_id, original_profile.pitcher_id)
        self.assertEqual(loaded_profile.total_pitches, original_profile.total_pitches)
        self.assertEqual(loaded_profile.sessions_analyzed, original_profile.sessions_analyzed)

    def test_update_existing_profile(self):
        """Test updating an existing pitcher profile."""
        manager = PitcherProfileManager(self.profiles_dir)

        # Create initial profile
        pitches1 = [
            MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0, is_strike=True),
            MockPitch("p2", speed_mph=86.0, run_in=2.2, rise_in=-1.2, is_strike=True),
        ]
        profile1 = manager.create_or_update_profile("test_pitcher", pitches1)

        # Update with more pitches
        pitches2 = [
            MockPitch("p3", speed_mph=84.5, run_in=1.8, rise_in=-0.8, is_strike=False),
            MockPitch("p4", speed_mph=85.5, run_in=2.1, rise_in=-1.1, is_strike=True),
        ]
        profile2 = manager.create_or_update_profile("test_pitcher", pitches2)

        self.assertEqual(profile2.total_pitches, 4)  # 2 from first + 2 from second
        self.assertEqual(profile2.sessions_analyzed, 2)

    def test_list_profiles(self):
        """Test listing all pitcher profiles."""
        manager = PitcherProfileManager(self.profiles_dir)

        # Create multiple profiles
        pitches = [MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0)]

        manager.create_or_update_profile("pitcher1", pitches)
        manager.create_or_update_profile("pitcher2", pitches)
        manager.create_or_update_profile("pitcher3", pitches)

        profiles = manager.list_profiles()

        self.assertEqual(len(profiles), 3)
        self.assertIn("pitcher1", profiles)
        self.assertIn("pitcher2", profiles)
        self.assertIn("pitcher3", profiles)

    def test_load_nonexistent_profile(self):
        """Test loading a profile that doesn't exist."""
        manager = PitcherProfileManager(self.profiles_dir)

        profile = manager.load_profile("nonexistent_pitcher")

        self.assertIsNone(profile)

    def test_compare_to_baseline_normal(self):
        """Test baseline comparison with normal performance."""
        manager = PitcherProfileManager(self.profiles_dir)

        # Create baseline
        baseline_pitches = [
            MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0, is_strike=True),
            MockPitch("p2", speed_mph=86.0, run_in=2.2, rise_in=-1.2, is_strike=True),
            MockPitch("p3", speed_mph=84.5, run_in=1.8, rise_in=-0.8, is_strike=False),
            MockPitch("p4", speed_mph=85.5, run_in=2.1, rise_in=-1.1, is_strike=True),
            MockPitch("p5", speed_mph=85.2, run_in=1.9, rise_in=-0.9, is_strike=False),
        ]
        manager.create_or_update_profile("test_pitcher", baseline_pitches)

        # Compare with similar current performance
        current_pitches = [
            MockPitch("p6", speed_mph=85.3, run_in=2.0, rise_in=-1.0, is_strike=True),
            MockPitch("p7", speed_mph=85.8, run_in=2.1, rise_in=-1.1, is_strike=True),
            MockPitch("p8", speed_mph=84.9, run_in=1.9, rise_in=-0.9, is_strike=False),
        ]

        comparison = manager.compare_to_baseline("test_pitcher", current_pitches)

        self.assertTrue(comparison['profile_exists'])
        self.assertIn('velocity_vs_baseline', comparison)

        # Check that status is "normal" or similar
        velocity_comparison = comparison['velocity_vs_baseline']
        self.assertIn('status', velocity_comparison)
        self.assertEqual(velocity_comparison['status'], 'normal')

    def test_compare_to_baseline_significantly_below(self):
        """Test baseline comparison with significantly lower performance."""
        manager = PitcherProfileManager(self.profiles_dir)

        # Create baseline with high velocity
        baseline_pitches = [
            MockPitch("p1", speed_mph=90.0, run_in=2.0, rise_in=-1.0, is_strike=True),
            MockPitch("p2", speed_mph=91.0, run_in=2.2, rise_in=-1.2, is_strike=True),
            MockPitch("p3", speed_mph=89.5, run_in=1.8, rise_in=-0.8, is_strike=True),
            MockPitch("p4", speed_mph=90.5, run_in=2.1, rise_in=-1.1, is_strike=True),
            MockPitch("p5", speed_mph=90.2, run_in=1.9, rise_in=-0.9, is_strike=True),
        ]
        manager.create_or_update_profile("test_pitcher", baseline_pitches)

        # Compare with much lower velocity
        current_pitches = [
            MockPitch("p6", speed_mph=82.0, run_in=2.0, rise_in=-1.0, is_strike=True),
            MockPitch("p7", speed_mph=81.5, run_in=2.1, rise_in=-1.1, is_strike=False),
            MockPitch("p8", speed_mph=82.5, run_in=1.9, rise_in=-0.9, is_strike=False),
        ]

        comparison = manager.compare_to_baseline("test_pitcher", current_pitches)

        velocity_comparison = comparison['velocity_vs_baseline']
        self.assertIn('status', velocity_comparison)
        # Should be flagged as significantly below
        self.assertIn('below', velocity_comparison['status'].lower())

    def test_compare_to_nonexistent_baseline(self):
        """Test baseline comparison when no profile exists."""
        manager = PitcherProfileManager(self.profiles_dir)

        pitches = [MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0)]

        comparison = manager.compare_to_baseline("nonexistent_pitcher", pitches)

        self.assertFalse(comparison['profile_exists'])

    def test_profile_with_missing_data(self):
        """Test creating profile with some missing data."""
        manager = PitcherProfileManager(self.profiles_dir)

        pitches = [
            MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0, is_strike=True),
            MockPitch("p2", speed_mph=None, run_in=2.2, rise_in=-1.2, is_strike=True),  # Missing speed
            MockPitch("p3", speed_mph=84.5, run_in=None, rise_in=None, is_strike=False),  # Missing movement
        ]

        profile = manager.create_or_update_profile("test_pitcher", pitches)

        self.assertIsNotNone(profile)
        self.assertEqual(profile.total_pitches, 3)

        # Should still compute metrics for available data
        self.assertIsNotNone(profile.baseline_metrics.velocity)

    def test_profile_filename_sanitization(self):
        """Test that pitcher IDs are sanitized for filenames."""
        manager = PitcherProfileManager(self.profiles_dir)

        pitches = [MockPitch("p1", speed_mph=85.0, run_in=2.0, rise_in=-1.0)]

        # Create profile with special characters
        profile = manager.create_or_update_profile("John Doe/Jr.", pitches)

        # Check that file was created with sanitized name
        profile_path = manager._get_profile_path("John Doe/Jr.")
        self.assertTrue(profile_path.exists())

        # Filename should not contain special characters
        self.assertNotIn('/', profile_path.name)
        self.assertNotIn('\\', profile_path.name)


if __name__ == '__main__':
    unittest.main()

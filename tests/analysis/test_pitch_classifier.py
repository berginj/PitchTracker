"""Tests for pitch classification."""

import pytest

from analysis.pattern_detection.pitch_classifier import (
    classify_pitch_heuristic,
    classify_pitches,
)
from analysis.pattern_detection.schemas import PitchClassification


class TestPitchClassifierHeuristics:
    """Test heuristic pitch classification."""

    def test_fastball_4seam_classification(self):
        """Test 4-seam fastball classification."""
        pitch = {
            'pitch_id': 'pitch_001',
            'speed_mph': 92.0,
            'run_in': 1.5,
            'rise_in': -0.5
        }

        result = classify_pitch_heuristic(pitch)

        assert result.heuristic_type == "Fastball (4-seam)"
        assert result.confidence >= 0.8
        assert result.features['speed_mph'] == 92.0

    def test_sinker_classification(self):
        """Test sinker classification."""
        pitch = {
            'pitch_id': 'pitch_003',
            'speed_mph': 89.0,
            'run_in': 2.0,
            'rise_in': -3.5
        }

        result = classify_pitch_heuristic(pitch)

        assert result.heuristic_type == "Sinker"
        assert result.confidence >= 0.7

    def test_slider_classification(self):
        """Test slider classification."""
        pitch = {
            'pitch_id': 'pitch_004',
            'speed_mph': 84.0,
            'run_in': 6.0,
            'rise_in': -1.0
        }

        result = classify_pitch_heuristic(pitch)

        assert result.heuristic_type == "Slider"
        assert result.confidence >= 0.75

    def test_curveball_classification(self):
        """Test curveball classification."""
        pitch = {
            'pitch_id': 'pitch_007',
            'speed_mph': 75.0,
            'run_in': 1.0,
            'rise_in': -6.0
        }

        result = classify_pitch_heuristic(pitch)

        assert result.heuristic_type == "Curveball"
        assert result.confidence >= 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

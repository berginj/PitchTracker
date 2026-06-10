"""Unit tests for FocusMonitorController.

Tests the extracted FocusMonitorController class from MainWindow refactoring.
Covers focus score tracking, peak values, and display updates.
"""

from __future__ import annotations

from unittest.mock import Mock, patch
import numpy as np

import pytest

from ui.controllers.focus_monitor import (
    FocusMonitorController,
    focus_quality_tone,
    FOCUS_GOOD_THRESHOLD,
    FOCUS_FAIR_THRESHOLD,
    TONE_GOOD,
    TONE_FAIR,
    TONE_POOR,
)


class TestFocusQualityTone:
    """Tests for focus_quality_tone function."""

    def test_good_quality(self):
        """Score >= 200 should return the success tone."""
        assert focus_quality_tone(200) == TONE_GOOD
        assert focus_quality_tone(250) == TONE_GOOD
        assert focus_quality_tone(500) == TONE_GOOD

    def test_fair_quality(self):
        """Score 100-199 should return the warning tone."""
        assert focus_quality_tone(100) == TONE_FAIR
        assert focus_quality_tone(150) == TONE_FAIR
        assert focus_quality_tone(199) == TONE_FAIR

    def test_poor_quality(self):
        """Score < 100 should return the error tone."""
        assert focus_quality_tone(0) == TONE_POOR
        assert focus_quality_tone(50) == TONE_POOR
        assert focus_quality_tone(99) == TONE_POOR


class TestFocusMonitorControllerInit:
    """Tests for FocusMonitorController initialization."""

    def test_initialization(self):
        """FocusMonitorController should initialize with provided labels."""
        left_label = Mock()
        right_label = Mock()

        fm = FocusMonitorController(
            focus_left_label=left_label,
            focus_right_label=right_label,
        )

        assert fm.peak_left == 0.0
        assert fm.peak_right == 0.0
        assert fm.current_left == 0.0
        assert fm.current_right == 0.0


class TestComputeScores:
    """Tests for focus score computation."""

    @pytest.fixture
    def focus_monitor(self):
        """Create FocusMonitorController with mock labels."""
        return FocusMonitorController(
            focus_left_label=Mock(),
            focus_right_label=Mock(),
        )

    @patch("ui.controllers.focus_monitor.compute_focus_score")
    def test_compute_scores(self, mock_compute, focus_monitor):
        """compute_scores should compute and cache scores."""
        mock_compute.side_effect = [150.0, 180.0]
        left_image = np.zeros((100, 100), dtype=np.uint8)
        right_image = np.zeros((100, 100), dtype=np.uint8)

        left_score, right_score = focus_monitor.compute_scores(left_image, right_image)

        assert left_score == 150.0
        assert right_score == 180.0
        assert focus_monitor.current_left == 150.0
        assert focus_monitor.current_right == 180.0


class TestUpdateDisplay:
    """Tests for focus display updates."""

    @pytest.fixture
    def focus_monitor(self):
        """Create FocusMonitorController with mock labels."""
        left_label = Mock()
        right_label = Mock()
        return FocusMonitorController(
            focus_left_label=left_label,
            focus_right_label=right_label,
        )

    def test_update_display_updates_labels(self, focus_monitor):
        """update_display should style both focus labels via the helper."""
        with patch("ui.controllers.focus_monitor.style_status_label") as mock_style:
            focus_monitor.update_display(150.0, 180.0)

        assert mock_style.call_count == 2
        styled_labels = [call.args[0] for call in mock_style.call_args_list]
        assert focus_monitor._focus_left_label in styled_labels
        assert focus_monitor._focus_right_label in styled_labels

    def test_update_display_tracks_peaks(self, focus_monitor):
        """update_display should track peak values."""
        focus_monitor.update_display(100.0, 120.0)
        assert focus_monitor.peak_left == 100.0
        assert focus_monitor.peak_right == 120.0

        # Higher values should update peaks
        focus_monitor.update_display(150.0, 180.0)
        assert focus_monitor.peak_left == 150.0
        assert focus_monitor.peak_right == 180.0

        # Lower values should not update peaks
        focus_monitor.update_display(80.0, 90.0)
        assert focus_monitor.peak_left == 150.0
        assert focus_monitor.peak_right == 180.0


class TestResetPeaks:
    """Tests for resetting peak values."""

    @pytest.fixture
    def focus_monitor(self):
        """Create FocusMonitorController with mock labels."""
        return FocusMonitorController(
            focus_left_label=Mock(),
            focus_right_label=Mock(),
        )

    def test_reset_peaks(self, focus_monitor):
        """reset_peaks should zero out peak values."""
        # Set some peaks first
        focus_monitor.update_display(200.0, 250.0)
        assert focus_monitor.peak_left == 200.0
        assert focus_monitor.peak_right == 250.0

        focus_monitor.reset_peaks()

        assert focus_monitor.peak_left == 0.0
        assert focus_monitor.peak_right == 0.0

    def test_reset_peaks_updates_labels(self, focus_monitor):
        """reset_peaks should update labels to show reset state."""
        focus_monitor.reset_peaks()

        # Should have called setText with reset indicator
        focus_monitor._focus_left_label.setText.assert_called()
        focus_monitor._focus_right_label.setText.assert_called()


class TestGetOverlayScores:
    """Tests for overlay score retrieval."""

    @pytest.fixture
    def focus_monitor(self):
        """Create FocusMonitorController with mock labels."""
        return FocusMonitorController(
            focus_left_label=Mock(),
            focus_right_label=Mock(),
        )

    @patch("ui.controllers.focus_monitor.compute_focus_score")
    def test_get_overlay_scores_enabled(self, mock_compute, focus_monitor):
        """get_overlay_scores should return scores when overlay enabled."""
        mock_compute.side_effect = [150.0, 180.0]
        focus_monitor.compute_scores(
            np.zeros((10, 10), dtype=np.uint8),
            np.zeros((10, 10), dtype=np.uint8),
        )

        left, right = focus_monitor.get_overlay_scores(show_overlay=True)

        assert left == 150.0
        assert right == 180.0

    def test_get_overlay_scores_disabled(self, focus_monitor):
        """get_overlay_scores should return None when overlay disabled."""
        left, right = focus_monitor.get_overlay_scores(show_overlay=False)

        assert left is None
        assert right is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

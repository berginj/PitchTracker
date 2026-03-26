"""Focus quality monitoring controller.

Extracted from MainWindow to reduce god class complexity.
Manages focus score tracking, peak values, and health display.
"""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

import numpy as np
from PySide6 import QtWidgets

from detect.utils import compute_focus_score
from log_config.logger import get_logger
from ui.themes import style_status_label

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Focus quality thresholds (empirical)
FOCUS_GOOD_THRESHOLD = 200
FOCUS_FAIR_THRESHOLD = 100

# Focus quality tones
TONE_GOOD = "success"
TONE_FAIR = "warning"
TONE_POOR = "error"


def focus_quality_tone(score: float) -> str:
    """Get semantic tone for focus quality score.

    Args:
        score: Focus quality score

    Returns:
        Semantic tone for the quality level
    """
    if score >= FOCUS_GOOD_THRESHOLD:
        return TONE_GOOD
    if score >= FOCUS_FAIR_THRESHOLD:
        return TONE_FAIR
    return TONE_POOR


class FocusMonitorController:
    """Manages focus quality monitoring.

    Responsibilities:
    - Computing focus scores from frames
    - Tracking peak focus values
    - Updating focus quality display labels
    - Color-coding based on quality thresholds
    """

    def __init__(
        self,
        focus_left_label: QtWidgets.QLabel,
        focus_right_label: QtWidgets.QLabel,
    ):
        """Initialize focus monitor controller.

        Args:
            focus_left_label: Label for left camera focus display
            focus_right_label: Label for right camera focus display
        """
        self._focus_left_label = focus_left_label
        self._focus_right_label = focus_right_label

        # Peak tracking
        self._peak_left = 0.0
        self._peak_right = 0.0

        # Current scores (cached for overlay use)
        self._current_left = 0.0
        self._current_right = 0.0

        logger.debug("FocusMonitorController initialized")

    @property
    def peak_left(self) -> float:
        """Get left camera peak focus score."""
        return self._peak_left

    @property
    def peak_right(self) -> float:
        """Get right camera peak focus score."""
        return self._peak_right

    @property
    def current_left(self) -> float:
        """Get current left camera focus score."""
        return self._current_left

    @property
    def current_right(self) -> float:
        """Get current right camera focus score."""
        return self._current_right

    def compute_scores(
        self, left_image: np.ndarray, right_image: np.ndarray
    ) -> tuple[float, float]:
        """Compute focus scores for both camera images.

        Args:
            left_image: Left camera frame
            right_image: Right camera frame

        Returns:
            Tuple of (left_score, right_score)
        """
        self._current_left = compute_focus_score(left_image)
        self._current_right = compute_focus_score(right_image)
        return self._current_left, self._current_right

    def update_display(self, focus_left: float, focus_right: float) -> None:
        """Update focus display labels with scores and color coding.

        Args:
            focus_left: Left camera focus score
            focus_right: Right camera focus score
        """
        # Update peak tracking
        if focus_left > self._peak_left:
            self._peak_left = focus_left
        if focus_right > self._peak_right:
            self._peak_right = focus_right

        # Update left label
        style_status_label(
            self._focus_left_label,
            focus_quality_tone(focus_left),
            f"L Focus: {focus_left:.0f} (peak: {self._peak_left:.0f})",
        )

        # Update right label
        style_status_label(
            self._focus_right_label,
            focus_quality_tone(focus_right),
            f"R Focus: {focus_right:.0f} (peak: {self._peak_right:.0f})",
        )

    def reset_peaks(self) -> None:
        """Reset peak focus values to zero."""
        self._peak_left = 0.0
        self._peak_right = 0.0

        # Update display to show reset
        style_status_label(self._focus_left_label, "info", "L Focus: --- (peak: ---)")
        style_status_label(self._focus_right_label, "info", "R Focus: --- (peak: ---)")

        logger.debug("Focus peaks reset")

    def get_overlay_scores(self, show_overlay: bool) -> tuple[Optional[float], Optional[float]]:
        """Get focus scores for overlay display.

        Args:
            show_overlay: Whether to show focus overlay (during calibration)

        Returns:
            Tuple of (left_score, right_score) or (None, None) if overlay disabled
        """
        if show_overlay:
            return self._current_left, self._current_right
        return None, None

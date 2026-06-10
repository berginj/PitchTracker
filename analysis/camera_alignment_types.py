"""The AlignmentResults data type and its derived guidance.

Kept in its own module so the result contract can be imported without pulling
in OpenCV/feature-matching dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class AlignmentResults:
    """Results from automatic camera alignment analysis."""

    # Raw measurements
    vertical_mean_px: float
    vertical_max_px: float
    convergence_std_px: float
    correlation: float
    rotation_deg: float
    num_matches: int
    scale_difference_percent: float  # NEW: Scale/focal length mismatch percentage

    # Quality assessment
    quality: str  # "EXCELLENT", "GOOD", "ACCEPTABLE", "POOR", "CRITICAL"
    vertical_status: str
    horizontal_status: str
    rotation_status: str
    scale_status: str  # NEW: Focal length/scale status

    # Automatic correction parameters
    rotation_correction_needed: bool
    rotation_left: float  # Degrees to rotate left image
    rotation_right: float  # Degrees to rotate right image
    vertical_offset_px: int  # Vertical shift for rectification

    # User-facing messages
    status_message: str
    warnings: list[str]
    corrections_applied: list[str]

    # Scale ratio (with default) - must be last because it has a default value
    scale_ratio: float = 1.0  # NEW: Actual scale ratio (1.0 = match, >1.0 = left zoomed, <1.0 = right zoomed)

    def can_calibrate(self) -> bool:
        """Check if calibration should be allowed with this alignment."""
        return self.quality != "CRITICAL"

    def should_warn_user(self) -> bool:
        """Check if user should be warned about alignment quality."""
        return self.quality in ["POOR", "CRITICAL"]

    def get_quality_score(self) -> int:
        """Calculate overall alignment quality score (0-100).

        Returns:
            Score where 100 = perfect alignment, 0 = unusable
        """
        # Start with perfect score
        score = 100.0

        # Penalize focal length mismatch (0-30 points)
        focal_penalty = min(30, self.scale_difference_percent * 2)
        score -= focal_penalty

        # Penalize toe-in/convergence (0-30 points)
        toin_penalty = min(30, self.convergence_std_px * 1.5)
        score -= toin_penalty

        # Penalize vertical misalignment (0-20 points)
        vertical_penalty = min(20, abs(self.vertical_mean_px) * 2)
        score -= vertical_penalty

        # Penalize rotation (0-20 points, if not auto-corrected)
        if not self.rotation_correction_needed:
            rotation_penalty = min(20, abs(self.rotation_deg) * 10)
            score -= rotation_penalty

        # Ensure score is in valid range
        score = max(0, min(100, score))

        return int(round(score))

    def get_directional_guidance(self) -> List[str]:
        """Get specific adjustment instructions based on alignment issues.

        Returns list of actionable instructions for user.
        """
        guidance = []

        # Focal length guidance (most important - put first)
        if self.scale_difference_percent > 2.0:  # Lower threshold for earlier warning
            # Estimate turn amount based on scale difference
            # Typical lens: 1/8 turn ≈ 3-5% scale change
            turn_estimate = self.scale_difference_percent / 4.0  # Rough estimate
            if turn_estimate < 0.1:
                turn_desc = "very small adjustment"
            elif turn_estimate < 0.2:
                turn_desc = "1/8 turn"
            elif turn_estimate < 0.4:
                turn_desc = "1/4 turn"
            elif turn_estimate < 0.75:
                turn_desc = "1/2 turn"
            else:
                turn_desc = "3/4 turn"

            if self.scale_ratio > 1.02:  # Left camera more zoomed (zoomed in more = higher magnification)
                guidance.append(
                    f"🔧 FOCAL LENGTH: LEFT camera {self.scale_difference_percent:.1f}% more zoomed\n"
                    f"   → Turn LEFT focus ring COUNTER-CLOCKWISE ~{turn_desc}\n"
                    f"   → Goal: Match right camera's zoom level\n"
                    f"   → After adjustment, run Quick Check to verify"
                )
            elif self.scale_ratio < 0.98:  # Right camera more zoomed
                guidance.append(
                    f"🔧 FOCAL LENGTH: RIGHT camera {self.scale_difference_percent:.1f}% more zoomed\n"
                    f"   → Turn RIGHT focus ring COUNTER-CLOCKWISE ~{turn_desc}\n"
                    f"   → Goal: Match left camera's zoom level\n"
                    f"   → After adjustment, run Quick Check to verify"
                )

        # Toe-in guidance
        if self.convergence_std_px > 10.0:
            if self.correlation > 0.3:  # Toed in
                guidance.append(
                    f"🔧 Camera Angles: Rotate BOTH cameras OUTWARD (away from each other) "
                    f"by ~2-3 degrees to fix toe-in"
                )
            elif self.correlation < -0.3:  # Toed out
                guidance.append(
                    f"🔧 Camera Angles: Rotate BOTH cameras INWARD (toward each other) "
                    f"by ~2-3 degrees to fix toe-out"
                )

        # Vertical guidance
        if abs(self.vertical_mean_px) > 10.0:
            direction = "LOWER" if self.vertical_mean_px > 0 else "RAISE"
            amount_inches = abs(self.vertical_mean_px) * 0.02  # Rough px to inches
            guidance.append(
                f"🔧 Camera Height: {direction} right camera by ~{amount_inches:.1f} inches "
                f"(currently {abs(self.vertical_mean_px):.0f}px offset)"
            )

        # Rotation guidance (if not auto-corrected)
        if abs(self.rotation_deg) > 2.0 and not self.rotation_correction_needed:
            direction = "CLOCKWISE" if self.rotation_deg > 0 else "COUNTER-CLOCKWISE"
            guidance.append(
                f"🔧 Camera Rotation: Rotate right camera {direction} by ~{abs(self.rotation_deg):.1f}° "
                f"to level with left camera"
            )

        if not guidance:
            guidance.append("✓ Alignment is good - no adjustments needed!")

        return guidance

"""Anomaly detection algorithms for pitch analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from analysis.pattern_detection.schemas import Anomaly, AnomalyDetails
from analysis.pattern_detection.utils import (
    compute_z_score,
    detect_outliers_iqr,
    detect_outliers_zscore,
)

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


def detect_speed_anomalies(
    pitches: List["PitchSummary"],
    z_threshold: float = 3.0,
    iqr_multiplier: float = 1.5
) -> List[Anomaly]:
    """Detect speed anomalies using Z-score and IQR methods.

    Args:
        pitches: List of pitch summaries
        z_threshold: Z-score threshold for outliers
        iqr_multiplier: IQR multiplier for bounds

    Returns:
        List of detected speed anomalies
    """
    anomalies = []

    # Extract speeds
    speeds = [p.speed_mph for p in pitches if p.speed_mph is not None]
    if len(speeds) < 3:
        return anomalies  # Not enough data

    # Detect using both methods
    z_outliers = detect_outliers_zscore(speeds, z_threshold)
    iqr_outliers = detect_outliers_iqr(speeds, iqr_multiplier)

    # Get indices that appear in both methods (high confidence)
    z_indices = {idx for idx, _, _ in z_outliers}
    iqr_indices = {idx for idx, _, _, _ in iqr_outliers}
    high_confidence_indices = z_indices & iqr_indices

    # Create anomalies for high-confidence outliers
    for idx in high_confidence_indices:
        pitch = pitches[idx]

        # Get z-score and bounds
        z_score = compute_z_score(pitch.speed_mph, speeds)
        _, _, lower, upper = next((x for x in iqr_outliers if x[0] == idx), (0, 0, 0, 0))

        severity = "high" if abs(z_score) > 4.0 else "medium" if abs(z_score) > 3.5 else "low"

        anomaly = Anomaly(
            pitch_id=pitch.pitch_id,
            anomaly_type="speed_outlier",
            severity=severity,
            details=AnomalyDetails(
                value=pitch.speed_mph,
                z_score=abs(z_score),
                expected_range=[float(lower), float(upper)]
            ),
            recommendation=_get_speed_anomaly_recommendation(pitch.speed_mph, speeds, z_score)
        )

        anomalies.append(anomaly)

    return anomalies


def detect_movement_anomalies(
    pitches: List["PitchSummary"],
    z_threshold: float = 3.0,
    iqr_multiplier: float = 1.5
) -> List[Anomaly]:
    """Detect movement anomalies (run_in, rise_in).

    Args:
        pitches: List of pitch summaries
        z_threshold: Z-score threshold
        iqr_multiplier: IQR multiplier

    Returns:
        List of detected movement anomalies
    """
    anomalies = []

    # Check horizontal movement (run_in)
    runs = [p.run_in for p in pitches if p.run_in is not None]
    if len(runs) >= 3:
        z_outliers = detect_outliers_zscore(runs, z_threshold)
        iqr_outliers = detect_outliers_iqr(runs, iqr_multiplier)

        z_indices = {idx for idx, _, _ in z_outliers}
        iqr_indices = {idx for idx, _, _, _ in iqr_outliers}
        high_confidence = z_indices & iqr_indices

        for idx in high_confidence:
            pitch = pitches[idx]
            z_score = compute_z_score(pitch.run_in, runs)

            anomaly = Anomaly(
                pitch_id=pitch.pitch_id,
                anomaly_type="horizontal_movement_outlier",
                severity="medium" if abs(z_score) > 3.5 else "low",
                details=AnomalyDetails(
                    value=pitch.run_in,
                    z_score=abs(z_score)
                ),
                recommendation=f"Unusual horizontal movement ({pitch.run_in:.1f} in). "
                               f"Check if this is an intentional pitch type variation."
            )
            anomalies.append(anomaly)

    # Check vertical movement (rise_in)
    rises = [p.rise_in for p in pitches if p.rise_in is not None]
    if len(rises) >= 3:
        z_outliers = detect_outliers_zscore(rises, z_threshold)
        iqr_outliers = detect_outliers_iqr(rises, iqr_multiplier)

        z_indices = {idx for idx, _, _ in z_outliers}
        iqr_indices = {idx for idx, _, _, _ in iqr_outliers}
        high_confidence = z_indices & iqr_indices

        for idx in high_confidence:
            pitch = pitches[idx]
            z_score = compute_z_score(pitch.rise_in, rises)

            anomaly = Anomaly(
                pitch_id=pitch.pitch_id,
                anomaly_type="vertical_movement_outlier",
                severity="medium" if abs(z_score) > 3.5 else "low",
                details=AnomalyDetails(
                    value=pitch.rise_in,
                    z_score=abs(z_score)
                ),
                recommendation=f"Unusual vertical movement ({pitch.rise_in:.1f} in). "
                               f"Check if this is an intentional pitch type variation."
            )
            anomalies.append(anomaly)

    return anomalies


def detect_trajectory_quality_anomalies(
    pitches: List["PitchSummary"]
) -> List[Anomaly]:
    """Detect anomalies based on trajectory quality metrics.

    Args:
        pitches: List of pitch summaries

    Returns:
        List of detected trajectory quality anomalies
    """
    anomalies = []

    for pitch in pitches:
        # Check for missing trajectory data
        if not hasattr(pitch, 'trajectory_confidence') or pitch.trajectory_confidence is None:
            continue

        pitch_anomalies = []

        # High trajectory error
        if hasattr(pitch, 'trajectory_expected_error_ft') and pitch.trajectory_expected_error_ft is not None:
            if pitch.trajectory_expected_error_ft > 0.5:
                pitch_anomalies.append(f"high RMSE ({pitch.trajectory_expected_error_ft:.2f} ft)")

        # Low confidence
        if pitch.trajectory_confidence < 0.7:
            pitch_anomalies.append(f"low confidence ({pitch.trajectory_confidence:.2f})")

        # Insufficient samples
        if pitch.sample_count < 10:
            pitch_anomalies.append(f"insufficient samples ({pitch.sample_count})")

        if pitch_anomalies:
            anomaly = Anomaly(
                pitch_id=pitch.pitch_id,
                anomaly_type="trajectory_quality",
                severity="high" if pitch.sample_count < 5 else "medium",
                details=AnomalyDetails(
                    rmse_3d_ft=getattr(pitch, 'trajectory_expected_error_ft', None),
                    inlier_ratio=pitch.trajectory_confidence if hasattr(pitch, 'trajectory_confidence') else None,
                    sample_count=pitch.sample_count
                ),
                recommendation=f"Poor trajectory quality: {', '.join(pitch_anomalies)}. "
                               f"Check camera ROIs and detection settings."
            )
            anomalies.append(anomaly)

    return anomalies


def detect_all_anomalies(
    pitches: List["PitchSummary"],
    z_threshold: float = 3.0,
    iqr_multiplier: float = 1.5
) -> List[Anomaly]:
    """Detect all types of anomalies.

    Args:
        pitches: List of pitch summaries
        z_threshold: Z-score threshold for outliers
        iqr_multiplier: IQR multiplier for bounds

    Returns:
        Combined list of all detected anomalies
    """
    anomalies = []

    # Speed anomalies
    anomalies.extend(detect_speed_anomalies(pitches, z_threshold, iqr_multiplier))

    # Movement anomalies
    anomalies.extend(detect_movement_anomalies(pitches, z_threshold, iqr_multiplier))

    # Trajectory quality anomalies
    anomalies.extend(detect_trajectory_quality_anomalies(pitches))

    return anomalies


def _get_speed_anomaly_recommendation(
    speed: float,
    all_speeds: List[float],
    z_score: float
) -> str:
    """Generate recommendation for speed anomaly.

    Args:
        speed: Anomalous speed value
        all_speeds: All speed values
        z_score: Z-score of the anomaly

    Returns:
        Human-readable recommendation
    """
    import numpy as np

    mean_speed = np.mean(all_speeds)

    if speed > mean_speed:
        return (f"Unusually fast pitch ({speed:.1f} mph vs avg {mean_speed:.1f} mph). "
                f"Verify radar calibration or check if pitcher is attempting max effort.")
    else:
        return (f"Unusually slow pitch ({speed:.1f} mph vs avg {mean_speed:.1f} mph). "
                f"Check if this is an off-speed pitch or potential fatigue indicator.")


__all__ = [
    "detect_speed_anomalies",
    "detect_movement_anomalies",
    "detect_trajectory_quality_anomalies",
    "detect_all_anomalies",
]

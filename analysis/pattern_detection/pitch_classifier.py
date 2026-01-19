"""Pitch type classification algorithms."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np
from sklearn.cluster import KMeans

from analysis.pattern_detection.schemas import PitchClassification, PitchFeatures
from analysis.pattern_detection.utils import normalize_features

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


def classify_pitch_heuristic(
    speed_mph: Optional[float],
    run_in: Optional[float],
    rise_in: Optional[float]
) -> str:
    """Classify pitch using MLB-standard heuristic rules.

    Args:
        speed_mph: Pitch velocity (mph)
        run_in: Horizontal movement (inches, positive = arm-side)
        rise_in: Vertical movement (inches, positive = rise, negative = drop)

    Returns:
        Pitch type label (e.g., "Fastball (4-seam)", "Slider", "Unknown")
    """
    # Handle missing data
    if speed_mph is None:
        return "Unknown (no velocity)"

    if run_in is None or rise_in is None:
        return f"Speed-only: {speed_mph:.1f} mph"

    # Compute total break for classification
    total_break = abs(run_in) + abs(rise_in)

    # Fastball family (88+ mph)
    if speed_mph >= 88:
        if total_break < 5:
            return "Fastball (4-seam)"
        elif rise_in < -2 and run_in > 2:
            return "Sinker (2-seam)"
        elif abs(run_in) > 4:
            return "Cutter"
        else:
            return "Fastball"

    # Slider/Cutter range (80-88 mph)
    if 80 <= speed_mph < 88:
        if abs(run_in) > 5:
            return "Slider"
        elif rise_in < -3 and abs(run_in) > 2:
            return "Curveball"
        elif total_break < 5:
            return "Changeup"
        else:
            return "Breaking Ball"

    # Curveball/Changeup range (70-85 mph)
    if 70 <= speed_mph < 85:
        if rise_in < -5:
            return "Curveball"
        elif total_break < 6:
            return "Changeup"
        else:
            return "Off-speed"

    # Slow pitches (< 70 mph)
    if speed_mph < 70:
        if rise_in < -5:
            return "Slow Curve"
        else:
            return "Eephus/Junk"

    return "Unknown"


def classify_pitches_heuristic(
    pitches: List["PitchSummary"]
) -> List[PitchClassification]:
    """Classify multiple pitches using heuristic rules.

    Args:
        pitches: List of pitch summaries

    Returns:
        List of pitch classifications
    """
    classifications = []

    for pitch in pitches:
        pitch_type = classify_pitch_heuristic(
            pitch.speed_mph,
            pitch.run_in,
            pitch.rise_in
        )

        classification = PitchClassification(
            pitch_id=pitch.pitch_id,
            heuristic_type=pitch_type,
            cluster_id=None,
            confidence=1.0 if "Unknown" not in pitch_type else 0.0,
            features=PitchFeatures(
                speed_mph=pitch.speed_mph,
                run_in=pitch.run_in,
                rise_in=pitch.rise_in
            )
        )

        classifications.append(classification)

    return classifications


def classify_pitches_kmeans(
    pitches: List["PitchSummary"],
    n_clusters: int = 3,
    random_state: int = 42
) -> Tuple[List[int], KMeans]:
    """Classify pitches using K-means clustering.

    Args:
        pitches: List of pitch summaries
        n_clusters: Number of clusters (default: 3)
        random_state: Random seed for reproducibility

    Returns:
        Tuple of (cluster_labels, kmeans_model)
    """
    # Extract features (only pitches with complete data)
    features_list = []
    valid_indices = []

    for i, pitch in enumerate(pitches):
        if pitch.speed_mph is not None and pitch.run_in is not None and pitch.rise_in is not None:
            features_list.append([pitch.speed_mph, pitch.run_in, pitch.rise_in])
            valid_indices.append(i)

    if len(features_list) < n_clusters:
        # Not enough data for clustering
        return [-1] * len(pitches), None

    # Normalize features
    features = np.array(features_list)
    features_norm = normalize_features(features)

    # Fit K-means
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    cluster_labels_valid = kmeans.fit_predict(features_norm)

    # Map back to all pitches (-1 for pitches without data)
    cluster_labels = [-1] * len(pitches)
    for i, idx in enumerate(valid_indices):
        cluster_labels[idx] = int(cluster_labels_valid[i])

    return cluster_labels, kmeans


def classify_pitches_hybrid(
    pitches: List["PitchSummary"],
    n_clusters: int = 3
) -> List[PitchClassification]:
    """Classify pitches using hybrid approach (heuristics + K-means).

    Args:
        pitches: List of pitch summaries
        n_clusters: Number of clusters for K-means

    Returns:
        List of pitch classifications with both heuristic and cluster labels
    """
    # Get heuristic classifications
    classifications = classify_pitches_heuristic(pitches)

    # Get K-means clusters
    cluster_labels, _ = classify_pitches_kmeans(pitches, n_clusters=n_clusters)

    # Merge results
    for i, classification in enumerate(classifications):
        classification.cluster_id = cluster_labels[i] if cluster_labels[i] != -1 else None

        # Update confidence based on whether both methods agree
        if classification.cluster_id is not None:
            # Both methods provided a label
            classification.confidence = 0.9
        elif "Unknown" in classification.heuristic_type:
            # Only K-means might provide insight
            classification.confidence = 0.3
        else:
            # Only heuristic provided label
            classification.confidence = 0.7

    return classifications


def compute_pitch_repertoire(
    classifications: List[PitchClassification],
    pitches: List["PitchSummary"]
) -> dict:
    """Compute pitch repertoire statistics from classifications.

    Args:
        classifications: List of pitch classifications
        pitches: List of pitch summaries (for computing averages)

    Returns:
        Dictionary mapping pitch type to statistics
    """
    from collections import defaultdict

    # Group by pitch type
    pitch_groups = defaultdict(list)

    for i, classification in enumerate(classifications):
        pitch_type = classification.heuristic_type
        pitch_groups[pitch_type].append(i)

    # Compute statistics for each type
    repertoire = {}

    for pitch_type, indices in pitch_groups.items():
        count = len(indices)
        percentage = count / len(pitches) if pitches else 0.0

        # Compute averages
        speeds = [pitches[i].speed_mph for i in indices if pitches[i].speed_mph is not None]
        runs = [pitches[i].run_in for i in indices if pitches[i].run_in is not None]
        rises = [pitches[i].rise_in for i in indices if pitches[i].rise_in is not None]

        avg_speed = float(np.mean(speeds)) if speeds else 0.0
        avg_run = float(np.mean(runs)) if runs else 0.0
        avg_rise = float(np.mean(rises)) if rises else 0.0

        repertoire[pitch_type] = {
            "count": count,
            "percentage": percentage,
            "avg_speed_mph": avg_speed,
            "avg_movement": {
                "run_in": avg_run,
                "rise_in": avg_rise
            }
        }

    return repertoire


__all__ = [
    "classify_pitch_heuristic",
    "classify_pitches_heuristic",
    "classify_pitches_kmeans",
    "classify_pitches_hybrid",
    "compute_pitch_repertoire",
]

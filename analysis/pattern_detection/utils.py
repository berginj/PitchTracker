"""Statistical utility functions for pattern detection."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


def compute_z_score(value: float, values: List[float]) -> float:
    """Compute Z-score for a value given a list of values.

    Args:
        value: Value to compute Z-score for
        values: List of values to compute statistics from

    Returns:
        Z-score (number of standard deviations from mean)
    """
    if not values or len(values) < 2:
        return 0.0

    mean = np.mean(values)
    std = np.std(values, ddof=1)

    if std == 0:
        return 0.0

    return float((value - mean) / std)


def detect_outliers_zscore(
    values: List[float],
    threshold: float = 3.0
) -> List[Tuple[int, float, float]]:
    """Detect outliers using Z-score method.

    Args:
        values: List of values to analyze
        threshold: Z-score threshold for outliers (default: 3.0)

    Returns:
        List of (index, value, z_score) tuples for outliers
    """
    if not values or len(values) < 3:
        return []

    mean = np.mean(values)
    std = np.std(values, ddof=1)

    if std == 0:
        return []

    outliers = []
    for i, value in enumerate(values):
        z_score = (value - mean) / std
        if abs(z_score) > threshold:
            outliers.append((i, value, z_score))

    return outliers


def detect_outliers_iqr(
    values: List[float],
    iqr_multiplier: float = 1.5
) -> List[Tuple[int, float, float, float]]:
    """Detect outliers using IQR (Interquartile Range) method.

    Args:
        values: List of values to analyze
        iqr_multiplier: IQR multiplier for bounds (default: 1.5)

    Returns:
        List of (index, value, lower_bound, upper_bound) tuples for outliers
    """
    if not values or len(values) < 3:
        return []

    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1

    lower_bound = q1 - iqr_multiplier * iqr
    upper_bound = q3 + iqr_multiplier * iqr

    outliers = []
    for i, value in enumerate(values):
        if value < lower_bound or value > upper_bound:
            outliers.append((i, value, lower_bound, upper_bound))

    return outliers


def compute_percentiles(
    values: List[float],
    percentiles: List[int] = [25, 50, 75]
) -> dict:
    """Compute percentiles for a list of values.

    Args:
        values: List of values
        percentiles: List of percentiles to compute (default: [25, 50, 75])

    Returns:
        Dictionary mapping percentile to value
    """
    if not values:
        return {p: 0.0 for p in percentiles}

    result = {}
    computed = np.percentile(values, percentiles)

    for p, v in zip(percentiles, computed):
        result[f"p{p}"] = float(v)

    return result


def compute_statistics(values: List[float]) -> dict:
    """Compute comprehensive statistics for a list of values.

    Args:
        values: List of values

    Returns:
        Dictionary with mean, std, min, max, and percentiles
    """
    if not values:
        return {
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
            "p25": 0.0,
            "p50": 0.0,
            "p75": 0.0,
        }

    stats = {
        "mean": float(np.mean(values)),
        "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }

    stats.update(compute_percentiles(values))

    return stats


def normalize_features(features: np.ndarray) -> np.ndarray:
    """Normalize features to zero mean and unit variance.

    Args:
        features: Array of shape (n_samples, n_features)

    Returns:
        Normalized features of same shape
    """
    if features.size == 0:
        return features

    mean = np.mean(features, axis=0)
    std = np.std(features, axis=0, ddof=1)

    # Avoid division by zero
    std[std == 0] = 1.0

    return (features - mean) / std


def compute_coefficient_of_variation(values: List[float]) -> float:
    """Compute coefficient of variation (std/mean).

    Args:
        values: List of values

    Returns:
        Coefficient of variation (0-inf, lower is more consistent)
    """
    if not values or len(values) < 2:
        return 0.0

    mean = np.mean(values)
    if mean == 0:
        return 0.0

    std = np.std(values, ddof=1)
    return float(std / abs(mean))


def linear_regression(x: List[float], y: List[float]) -> Tuple[float, float]:
    """Compute simple linear regression.

    Args:
        x: Independent variable values
        y: Dependent variable values

    Returns:
        Tuple of (slope, intercept)
    """
    if not x or not y or len(x) != len(y) or len(x) < 2:
        return (0.0, 0.0)

    x_arr = np.array(x)
    y_arr = np.array(y)

    slope, intercept = np.polyfit(x_arr, y_arr, 1)

    return (float(slope), float(intercept))


__all__ = [
    "compute_z_score",
    "detect_outliers_zscore",
    "detect_outliers_iqr",
    "compute_percentiles",
    "compute_statistics",
    "normalize_features",
    "compute_coefficient_of_variation",
    "linear_regression",
]

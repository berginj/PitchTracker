"""Analysis module for post-processing pitch data."""

from .trend_analyzer import (
    BaselineComparison,
    SessionSummary,
    TrendAnalyzer,
    TrendReport,
)

__all__ = [
    "pattern_detection",
    "BaselineComparison",
    "SessionSummary",
    "TrendAnalyzer",
    "TrendReport",
]

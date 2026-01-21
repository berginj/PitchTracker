"""Pattern detection system for pitch analysis.

Analyzes recorded pitch data to detect pitch types, anomalies, and trends.
"""

from .detector import PatternDetector
from .schemas import (
    PitchClassification,
    Anomaly,
    PitchRepertoire,
    PatternAnalysisReport,
)

__all__ = [
    "PatternDetector",
    "PitchClassification",
    "Anomaly",
    "PitchRepertoire",
    "PatternAnalysisReport",
]

"""Pattern detection for pitch classification and anomaly detection."""

from analysis.pattern_detection.detector import PatternDetector
from analysis.pattern_detection.schemas import (
    AnalysisReport,
    Anomaly,
    PitchClassification,
    PitchRepertoireEntry,
)

__all__ = [
    "PatternDetector",
    "AnalysisReport",
    "Anomaly",
    "PitchClassification",
    "PitchRepertoireEntry",
]

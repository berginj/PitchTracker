"""Data schemas for pattern detection analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class PitchFeatures:
    """Features extracted from a pitch for classification."""

    speed_mph: Optional[float] = None
    run_in: Optional[float] = None  # Horizontal movement (inches)
    rise_in: Optional[float] = None  # Vertical movement (inches)


@dataclass
class PitchClassification:
    """Classification result for a single pitch."""

    pitch_id: str
    heuristic_type: str  # e.g., "Fastball (4-seam)", "Slider", "Unknown"
    cluster_id: Optional[int] = None  # K-means cluster assignment
    confidence: float = 0.0  # Confidence score (0-1)
    features: PitchFeatures = field(default_factory=PitchFeatures)


@dataclass
class AnomalyDetails:
    """Details about a detected anomaly."""

    # For speed/movement anomalies
    value: Optional[float] = None
    z_score: Optional[float] = None
    expected_range: Optional[List[float]] = None

    # For trajectory quality anomalies
    rmse_3d_ft: Optional[float] = None
    inlier_ratio: Optional[float] = None
    condition_number: Optional[float] = None
    sample_count: Optional[int] = None
    max_gap_ms: Optional[float] = None


@dataclass
class Anomaly:
    """Detected anomaly in a pitch."""

    pitch_id: str
    anomaly_type: str  # e.g., "speed_outlier", "trajectory_quality", "movement_outlier"
    severity: str  # "low", "medium", "high"
    details: AnomalyDetails
    recommendation: str  # Human-readable recommendation


@dataclass
class PitchRepertoireEntry:
    """Statistics for one pitch type."""

    count: int
    percentage: float
    avg_speed_mph: float
    avg_movement: Dict[str, float]  # {"run_in": x, "rise_in": y}


@dataclass
class ConsistencyMetrics:
    """Consistency metrics across pitches."""

    velocity_std_mph: float
    velocity_cv: float  # Coefficient of variation
    movement_consistency_score: float  # 0-1, higher is more consistent


@dataclass
class BaselineComparison:
    """Comparison to pitcher's baseline profile."""

    profile_exists: bool
    velocity_vs_baseline: Optional[Dict[str, any]] = None  # {current, baseline, delta, status}
    strike_percentage_vs_baseline: Optional[Dict[str, any]] = None
    horizontal_movement_vs_baseline: Optional[Dict[str, any]] = None
    vertical_movement_vs_baseline: Optional[Dict[str, any]] = None


@dataclass
class Summary:
    """High-level summary of analysis."""

    total_pitches: int
    anomalies_detected: int
    pitch_types_detected: int
    average_velocity_mph: float
    strike_percentage: float


@dataclass
class AnalysisReport:
    """Complete pattern detection analysis report."""

    schema_version: str = "1.0.0"
    created_utc: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    session_id: str = ""
    pitcher_id: Optional[str] = None

    summary: Summary = field(default_factory=lambda: Summary(0, 0, 0, 0.0, 0.0))
    pitch_classification: List[PitchClassification] = field(default_factory=list)
    anomalies: List[Anomaly] = field(default_factory=list)
    pitch_repertoire: Dict[str, PitchRepertoireEntry] = field(default_factory=dict)
    consistency_metrics: Optional[ConsistencyMetrics] = None
    baseline_comparison: Optional[BaselineComparison] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        def convert_value(v):
            if isinstance(v, (Summary, ConsistencyMetrics, BaselineComparison,
                            PitchFeatures, AnomalyDetails)):
                return {k: convert_value(val) for k, val in v.__dict__.items()}
            elif isinstance(v, (PitchClassification, Anomaly)):
                return {k: convert_value(val) for k, val in v.__dict__.items()}
            elif isinstance(v, PitchRepertoireEntry):
                return {k: convert_value(val) for k, val in v.__dict__.items()}
            elif isinstance(v, list):
                return [convert_value(item) for item in v]
            elif isinstance(v, dict):
                return {k: convert_value(val) for k, val in v.items()}
            else:
                return v

        return {k: convert_value(v) for k, v in self.__dict__.items()}


__all__ = [
    "PitchFeatures",
    "PitchClassification",
    "AnomalyDetails",
    "Anomaly",
    "PitchRepertoireEntry",
    "ConsistencyMetrics",
    "BaselineComparison",
    "Summary",
    "AnalysisReport",
]

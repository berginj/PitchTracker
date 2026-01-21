"""Data schemas for pattern detection results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class PitchClassification:
    """Classification result for a single pitch."""
    
    pitch_id: str
    heuristic_type: str  # Fastball, Curveball, Slider, Changeup, etc.
    cluster_id: Optional[int]  # From K-means clustering
    confidence: float  # 0-1
    features: Dict[str, float]  # speed_mph, run_in, rise_in, etc.


@dataclass
class Anomaly:
    """Detected anomaly for a single pitch."""
    
    pitch_id: str
    anomaly_type: str  # speed_outlier, movement_anomaly, trajectory_quality, data_quality
    severity: str  # low, medium, high
    details: Dict[str, float]  # Specific metrics that triggered anomaly
    recommendation: str  # What to do about it


@dataclass
class PitchRepertoire:
    """Summary of pitch types for a session/pitcher."""
    
    pitch_type: str
    count: int
    percentage: float
    avg_speed_mph: float
    avg_run_in: float
    avg_rise_in: float


@dataclass
class ConsistencyMetrics:
    """Consistency analysis metrics."""
    
    velocity_std_mph: float
    movement_consistency_score: float  # 0-1, higher is more consistent


@dataclass
class BaselineComparison:
    """Comparison with pitcher baseline profile."""
    
    profile_exists: bool
    velocity_delta_mph: Optional[float] = None
    velocity_status: Optional[str] = None  # above, below, normal
    repertoire_changes: Optional[Dict[str, float]] = None  # % change per pitch type


@dataclass
class PatternAnalysisReport:
    """Complete pattern analysis report for a session."""
    
    schema_version: str
    created_utc: str
    session_id: str
    pitcher_id: Optional[str]
    
    # Summary
    total_pitches: int
    anomalies_detected: int
    pitch_types_detected: int
    average_velocity_mph: float
    strike_percentage: float
    
    # Detailed results
    pitch_classifications: List[PitchClassification]
    anomalies: List[Anomaly]
    pitch_repertoire: List[PitchRepertoire]
    consistency_metrics: ConsistencyMetrics
    baseline_comparison: Optional[BaselineComparison] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "created_utc": self.created_utc,
            "session_id": self.session_id,
            "pitcher_id": self.pitcher_id,
            "summary": {
                "total_pitches": self.total_pitches,
                "anomalies_detected": self.anomalies_detected,
                "pitch_types_detected": self.pitch_types_detected,
                "average_velocity_mph": self.average_velocity_mph,
                "strike_percentage": self.strike_percentage
            },
            "pitch_classification": [
                {
                    "pitch_id": p.pitch_id,
                    "heuristic_type": p.heuristic_type,
                    "cluster_id": p.cluster_id,
                    "confidence": p.confidence,
                    "features": p.features
                }
                for p in self.pitch_classifications
            ],
            "anomalies": [
                {
                    "pitch_id": a.pitch_id,
                    "anomaly_type": a.anomaly_type,
                    "severity": a.severity,
                    "details": a.details,
                    "recommendation": a.recommendation
                }
                for a in self.anomalies
            ],
            "pitch_repertoire": {
                rep.pitch_type: {
                    "count": rep.count,
                    "percentage": rep.percentage,
                    "avg_speed_mph": rep.avg_speed_mph,
                    "avg_run_in": rep.avg_run_in,
                    "avg_rise_in": rep.avg_rise_in
                }
                for rep in self.pitch_repertoire
            },
            "consistency_metrics": {
                "velocity_std_mph": self.consistency_metrics.velocity_std_mph,
                "movement_consistency_score": self.consistency_metrics.movement_consistency_score
            },
            "baseline_comparison": {
                "profile_exists": self.baseline_comparison.profile_exists if self.baseline_comparison else False,
                "velocity_vs_baseline": {
                    "delta_mph": self.baseline_comparison.velocity_delta_mph if self.baseline_comparison else None,
                    "status": self.baseline_comparison.velocity_status if self.baseline_comparison else None
                } if self.baseline_comparison else None
            } if self.baseline_comparison else None
        }

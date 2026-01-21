"""Main pattern detection facade."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np

from .anomaly_detector import detect_anomalies
from .pitch_classifier import classify_pitches
from .report_generator import generate_html_report, generate_json_report
from .schemas import (
    ConsistencyMetrics,
    PatternAnalysisReport,
    PitchRepertoire,
)


class PatternDetector:
    """Main facade for pattern detection analysis."""
    
    def analyze_session(self, session_path: Path, pitcher_id: Optional[str] = None) -> PatternAnalysisReport:
        """Analyze a single session and generate report.
        
        Args:
            session_path: Path to session directory (e.g., recordings/session-2026-01-19_001)
            pitcher_id: Optional pitcher identifier
            
        Returns:
            PatternAnalysisReport with all analysis results
        """
        # Load session summary
        summary_file = session_path / "session_summary.json"
        if not summary_file.exists():
            raise FileNotFoundError(f"Session summary not found: {summary_file}")
        
        with open(summary_file) as f:
            session_data = json.load(f)
        
        # Extract pitch data
        pitches = session_data.get("pitches", [])
        
        if len(pitches) < 5:
            raise ValueError(f"Insufficient pitches for analysis (found {len(pitches)}, need 5+)")
        
        # Classify pitches
        classifications = classify_pitches(pitches)
        
        # Detect anomalies
        anomalies = detect_anomalies(pitches)
        
        # Calculate repertoire
        repertoire = self._calculate_repertoire(classifications, pitches)
        
        # Calculate consistency metrics
        consistency = self._calculate_consistency(pitches)
        
        # Calculate summary stats
        speeds = [p.get('speed_mph', 0) for p in pitches if p.get('speed_mph')]
        avg_speed = np.mean(speeds) if speeds else 0.0
        
        strikes = sum(1 for p in pitches if p.get('result') == 'strike')
        strike_pct = (strikes / len(pitches) * 100) if pitches else 0.0
        
        # Build report
        report = PatternAnalysisReport(
            schema_version="1.0.0",
            created_utc=datetime.utcnow().isoformat() + "Z",
            session_id=session_path.name,
            pitcher_id=pitcher_id,
            total_pitches=len(pitches),
            anomalies_detected=len(anomalies),
            pitch_types_detected=len(repertoire),
            average_velocity_mph=avg_speed,
            strike_percentage=strike_pct,
            pitch_classifications=classifications,
            anomalies=anomalies,
            pitch_repertoire=repertoire,
            consistency_metrics=consistency,
            baseline_comparison=None  # Simplified - skip for now
        )
        
        return report
    
    def save_reports(self, report: PatternAnalysisReport, session_path: Path) -> None:
        """Save analysis reports to session directory.
        
        Args:
            report: PatternAnalysisReport to save
            session_path: Path to session directory
        """
        # Save JSON report
        json_path = session_path / "analysis_report.json"
        generate_json_report(report, json_path)
        
        # Save HTML report
        html_path = session_path / "analysis_report.html"
        generate_html_report(report, html_path)
    
    def _calculate_repertoire(self, classifications: list, pitches: list) -> List[PitchRepertoire]:
        """Calculate pitch repertoire statistics."""
        # Count pitch types
        type_counts = Counter(c.heuristic_type for c in classifications)
        
        # Group pitches by type
        repertoire = []
        for pitch_type, count in type_counts.items():
            # Get pitches of this type
            type_pitches = [
                p for i, p in enumerate(pitches) 
                if i < len(classifications) and classifications[i].heuristic_type == pitch_type
            ]
            
            # Calculate averages
            speeds = [p.get('speed_mph', 0) for p in type_pitches if p.get('speed_mph')]
            runs = [p.get('run_in', 0) for p in type_pitches if 'run_in' in p]
            rises = [p.get('rise_in', 0) for p in type_pitches if 'rise_in' in p]
            
            repertoire.append(PitchRepertoire(
                pitch_type=pitch_type,
                count=count,
                percentage=count / len(classifications) * 100,
                avg_speed_mph=np.mean(speeds) if speeds else 0.0,
                avg_run_in=np.mean(runs) if runs else 0.0,
                avg_rise_in=np.mean(rises) if rises else 0.0
            ))
        
        # Sort by count (most common first)
        repertoire.sort(key=lambda r: r.count, reverse=True)
        return repertoire
    
    def _calculate_consistency(self, pitches: list) -> ConsistencyMetrics:
        """Calculate consistency metrics."""
        speeds = [p.get('speed_mph', 0) for p in pitches if p.get('speed_mph')]
        runs = [p.get('run_in', 0) for p in pitches if 'run_in' in p]
        rises = [p.get('rise_in', 0) for p in pitches if 'rise_in' in p]
        
        velocity_std = np.std(speeds) if len(speeds) > 1 else 0.0
        
        # Movement consistency: inverse of combined std dev (normalized)
        if len(runs) > 1 and len(rises) > 1:
            run_std = np.std(runs)
            rise_std = np.std(rises)
            combined_std = np.sqrt(run_std**2 + rise_std**2)
            # Convert to 0-1 score (lower std = higher consistency)
            movement_consistency = max(0, 1.0 - combined_std / 10.0)
        else:
            movement_consistency = 0.0
        
        return ConsistencyMetrics(
            velocity_std_mph=velocity_std,
            movement_consistency_score=movement_consistency
        )

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
from .pitcher_profile import PitcherProfileManager
from .report_generator import generate_html_report, generate_json_report
from .schemas import (
    BaselineComparison,
    ConsistencyMetrics,
    PatternAnalysisReport,
    PitchRepertoire,
)


class PatternDetector:
    """Main facade for pattern detection analysis."""

    def __init__(self, profiles_dir: Optional[Path] = None):
        """Initialize pattern detector.

        Args:
            profiles_dir: Directory for pitcher profiles (default: configs/pitcher_profiles/)
        """
        self.profile_manager = PitcherProfileManager(profiles_dir)

    def analyze_session(
        self,
        session_path: Path,
        pitcher_id: Optional[str] = None,
        output_json: bool = False,
        output_html: bool = False
    ) -> PatternAnalysisReport:
        """Analyze a single session and generate report.

        Args:
            session_path: Path to session directory (e.g., recordings/session-2026-01-19_001)
            pitcher_id: Optional pitcher identifier for baseline comparison
            output_json: Whether to save JSON report to session directory
            output_html: Whether to save HTML report to session directory

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

        # Handle insufficient data
        if len(pitches) < 5:
            # Create error report
            report = self._create_error_report(
                session_path.name,
                pitcher_id,
                len(pitches),
                "insufficient_data"
            )

            # Save error report if requested
            if output_json:
                json_path = session_path / "analysis_report.json"
                error_data = {
                    "error": "insufficient_data",
                    "pitch_count": len(pitches),
                    "minimum_required": 5,
                    "message": "At least 5 pitches required for pattern analysis.",
                    "recommendations": ["Record more pitches", "Use cross-session analysis"]
                }
                with open(json_path, 'w') as f:
                    json.dump(error_data, f, indent=2)

            return report

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

        strikes = sum(1 for p in pitches if p.get('is_strike', False))
        strike_pct = (strikes / len(pitches) * 100) if pitches else 0.0

        # Baseline comparison if pitcher_id provided
        baseline_comparison = None
        if pitcher_id:
            baseline_comparison = self._compute_baseline_comparison(pitcher_id, pitches, avg_speed)

        # Build report
        report = PatternAnalysisReport(
            schema_version="1.0.0",
            created_utc=datetime.utcnow().isoformat() + "Z",
            session_id=session_data.get("session_id", session_path.name),
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
            baseline_comparison=baseline_comparison
        )

        # Save reports if requested
        if output_json:
            json_path = session_path / "analysis_report.json"
            generate_json_report(report, json_path)

        if output_html:
            html_path = session_path / "analysis_report.html"
            generate_html_report(report, html_path)

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

    def _compute_baseline_comparison(
        self,
        pitcher_id: str,
        pitches: list,
        avg_speed: float
    ) -> Optional[BaselineComparison]:
        """Compute baseline comparison if profile exists.

        Args:
            pitcher_id: Pitcher identifier
            pitches: List of pitch dictionaries
            avg_speed: Average velocity for current session

        Returns:
            BaselineComparison or None if no profile exists
        """
        profile = self.profile_manager.load_profile(pitcher_id)

        if profile is None or profile.baseline_metrics is None:
            return BaselineComparison(profile_exists=False)

        # Calculate velocity delta
        baseline_velocity = profile.baseline_metrics.velocity.get('mean', 0.0)
        velocity_delta = avg_speed - baseline_velocity

        # Determine status
        velocity_std = profile.baseline_metrics.velocity.get('std', 1.0)
        if abs(velocity_delta) < velocity_std:
            status = "normal"
        elif velocity_delta > 0:
            status = "above"
        else:
            status = "below"

        return BaselineComparison(
            profile_exists=True,
            velocity_delta_mph=velocity_delta,
            velocity_status=status,
            _current_velocity=avg_speed,
            _baseline_velocity=baseline_velocity
        )

    def _create_error_report(
        self,
        session_id: str,
        pitcher_id: Optional[str],
        pitch_count: int,
        error_type: str
    ) -> PatternAnalysisReport:
        """Create an error report for insufficient data.

        Args:
            session_id: Session identifier
            pitcher_id: Optional pitcher identifier
            pitch_count: Number of pitches found
            error_type: Type of error

        Returns:
            PatternAnalysisReport with minimal data
        """
        return PatternAnalysisReport(
            schema_version="1.0.0",
            created_utc=datetime.utcnow().isoformat() + "Z",
            session_id=session_id,
            pitcher_id=pitcher_id,
            total_pitches=pitch_count,
            anomalies_detected=0,
            pitch_types_detected=0,
            average_velocity_mph=0.0,
            strike_percentage=0.0,
            pitch_classifications=[],
            anomalies=[],
            pitch_repertoire=[],
            consistency_metrics=ConsistencyMetrics(
                velocity_std_mph=0.0,
                movement_consistency_score=0.0
            ),
            baseline_comparison=None
        )

    def create_pitcher_profile(self, pitcher_id: str, session_dirs: List[Path]) -> None:
        """Create a pitcher profile from multiple sessions.

        Args:
            pitcher_id: Pitcher identifier
            session_dirs: List of session directory paths to include in profile
        """
        # Load all pitches from all sessions
        all_pitches = []

        for session_dir in session_dirs:
            summary_file = session_dir / "session_summary.json"
            if not summary_file.exists():
                continue

            with open(summary_file) as f:
                session_data = json.load(f)

            pitches = session_data.get("pitches", [])
            all_pitches.extend(pitches)

        if len(all_pitches) < 10:
            raise ValueError(f"Insufficient pitches for profile (found {len(all_pitches)}, need 10+)")

        # Convert dict pitches to PitchSummary-like objects
        # Since profile_manager expects PitchSummary objects, we need to create simple objects
        from types import SimpleNamespace

        pitch_objects = []
        for p in all_pitches:
            pitch_obj = SimpleNamespace(
                speed_mph=p.get('speed_mph'),
                run_in=p.get('run_in'),
                rise_in=p.get('rise_in'),
                is_strike=p.get('is_strike', False)
            )
            pitch_objects.append(pitch_obj)

        # Create or update profile
        self.profile_manager.create_or_update_profile(
            pitcher_id=pitcher_id,
            pitches=pitch_objects,
            num_sessions=len(session_dirs)
        )

"""Main pattern detection facade."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from analysis.pattern_detection.anomaly_detector import detect_all_anomalies
from analysis.pattern_detection.pitch_classifier import (
    classify_pitches_hybrid,
    compute_pitch_repertoire,
)
from analysis.pattern_detection.pitcher_profile import PitcherProfileManager
from analysis.pattern_detection.report_generator import ReportGenerator
from analysis.pattern_detection.schemas import (
    AnalysisReport,
    BaselineComparison,
    ConsistencyMetrics,
    PitchRepertoireEntry,
    Summary,
)
from analysis.pattern_detection.utils import compute_coefficient_of_variation


class PatternDetector:
    """Main facade for pattern detection analysis."""

    def __init__(
        self,
        profiles_dir: Optional[Path] = None,
        z_threshold: float = 3.0,
        iqr_multiplier: float = 1.5
    ):
        """Initialize pattern detector.

        Args:
            profiles_dir: Directory for pitcher profiles (default: configs/pitcher_profiles/)
            z_threshold: Z-score threshold for anomaly detection
            iqr_multiplier: IQR multiplier for outlier detection
        """
        self.profile_manager = PitcherProfileManager(profiles_dir)
        self.report_generator = ReportGenerator()
        self.z_threshold = z_threshold
        self.iqr_multiplier = iqr_multiplier

    def analyze_session(
        self,
        session_dir: Path,
        pitcher_id: Optional[str] = None,
        output_json: bool = True,
        output_html: bool = True
    ) -> AnalysisReport:
        """Analyze a single session.

        Args:
            session_dir: Path to session directory
            pitcher_id: Optional pitcher ID for baseline comparison
            output_json: Generate JSON report
            output_html: Generate HTML report

        Returns:
            AnalysisReport with all detected patterns
        """
        # Load session data
        pitches = self._load_session_pitches(session_dir)

        # Check minimum data requirements
        if len(pitches) < 5:
            return self._create_insufficient_data_report(session_dir, len(pitches))

        # Run analysis
        report = self._analyze_pitches(pitches, session_dir, pitcher_id)

        # Generate output files
        if output_json:
            json_path = session_dir / "analysis_report.json"
            self.report_generator.generate_json_report(report, json_path)

        if output_html:
            html_path = session_dir / "analysis_report.html"
            self.report_generator.generate_html_report(report, pitches, html_path)

        return report

    def _analyze_pitches(
        self,
        pitches: List,
        session_dir: Path,
        pitcher_id: Optional[str] = None
    ) -> AnalysisReport:
        """Analyze pitches and generate report.

        Args:
            pitches: List of pitch summaries
            session_dir: Session directory path
            pitcher_id: Optional pitcher ID for baseline comparison

        Returns:
            Complete analysis report
        """
        # Classify pitches
        classifications = classify_pitches_hybrid(pitches, n_clusters=3)

        # Detect anomalies
        anomalies = detect_all_anomalies(pitches, self.z_threshold, self.iqr_multiplier)

        # Compute pitch repertoire
        repertoire_dict = compute_pitch_repertoire(classifications, pitches)
        repertoire = {
            pitch_type: PitchRepertoireEntry(**stats)
            for pitch_type, stats in repertoire_dict.items()
        }

        # Compute consistency metrics
        velocities = [p.speed_mph for p in pitches if p.speed_mph is not None]
        velocity_std = float(sum((v - sum(velocities)/len(velocities))**2 for v in velocities) / len(velocities))**0.5 if velocities else 0.0
        velocity_cv = compute_coefficient_of_variation(velocities)

        # Movement consistency (inverse of combined std)
        runs = [p.run_in for p in pitches if p.run_in is not None]
        rises = [p.rise_in for p in pitches if p.rise_in is not None]
        run_std = float(sum((r - sum(runs)/len(runs))**2 for r in runs) / len(runs))**0.5 if runs else 0.0
        rise_std = float(sum((r - sum(rises)/len(rises))**2 for r in rises) / len(rises))**0.5 if rises else 0.0
        movement_consistency = 1.0 / (1.0 + (run_std + rise_std) / 2.0)

        consistency = ConsistencyMetrics(
            velocity_std_mph=velocity_std,
            velocity_cv=velocity_cv,
            movement_consistency_score=movement_consistency
        )

        # Baseline comparison (if pitcher_id provided)
        baseline_comparison = None
        if pitcher_id:
            comparison_result = self.profile_manager.compare_to_baseline(pitcher_id, pitches)
            baseline_comparison = BaselineComparison(**comparison_result)

        # Compute summary
        unique_types = len(set(c.heuristic_type for c in classifications))
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0.0
        strikes = sum(1 for p in pitches if p.is_strike)
        strike_pct = strikes / len(pitches) if pitches else 0.0

        summary = Summary(
            total_pitches=len(pitches),
            anomalies_detected=len(anomalies),
            pitch_types_detected=unique_types,
            average_velocity_mph=avg_velocity,
            strike_percentage=strike_pct
        )

        # Build report
        report = AnalysisReport(
            session_id=session_dir.name,
            pitcher_id=pitcher_id,
            summary=summary,
            pitch_classification=classifications,
            anomalies=anomalies,
            pitch_repertoire=repertoire,
            consistency_metrics=consistency,
            baseline_comparison=baseline_comparison
        )

        return report

    def _load_session_pitches(self, session_dir: Path) -> List:
        """Load pitches from session directory.

        Args:
            session_dir: Path to session directory

        Returns:
            List of pitch summaries
        """
        # Load session summary
        summary_path = session_dir / "session_summary.json"

        if not summary_path.exists():
            raise FileNotFoundError(f"Session summary not found: {summary_path}")

        with open(summary_path, 'r') as f:
            summary_data = json.load(f)

        # Convert to PitchSummary objects
        from app.pipeline_service import PitchSummary

        pitches = []
        for pitch_data in summary_data.get('pitches', []):
            # Create PitchSummary from dict (simplified)
            pitch = PitchSummary(
                pitch_id=pitch_data.get('pitch_id', ''),
                t_start_ns=pitch_data.get('t_start_ns', 0),
                t_end_ns=pitch_data.get('t_end_ns', 0),
                is_strike=pitch_data.get('is_strike', False),
                zone_row=pitch_data.get('zone_row'),
                zone_col=pitch_data.get('zone_col'),
                run_in=pitch_data.get('run_in', 0.0),
                rise_in=pitch_data.get('rise_in', 0.0),
                speed_mph=pitch_data.get('speed_mph'),
                rotation_rpm=pitch_data.get('rotation_rpm'),
                sample_count=pitch_data.get('sample_count', 0),
                trajectory_plate_x_ft=pitch_data.get('trajectory_plate_x_ft'),
                trajectory_plate_y_ft=pitch_data.get('trajectory_plate_y_ft'),
                trajectory_plate_z_ft=pitch_data.get('trajectory_plate_z_ft'),
                trajectory_plate_t_ns=pitch_data.get('trajectory_plate_t_ns'),
                trajectory_model=pitch_data.get('trajectory_model'),
                trajectory_expected_error_ft=pitch_data.get('trajectory_expected_error_ft'),
                trajectory_confidence=pitch_data.get('trajectory_confidence')
            )
            pitches.append(pitch)

        return pitches

    def _create_insufficient_data_report(
        self,
        session_dir: Path,
        pitch_count: int
    ) -> AnalysisReport:
        """Create error report for insufficient data.

        Args:
            session_dir: Session directory path
            pitch_count: Number of pitches found

        Returns:
            AnalysisReport with error information
        """
        summary = Summary(
            total_pitches=pitch_count,
            anomalies_detected=0,
            pitch_types_detected=0,
            average_velocity_mph=0.0,
            strike_percentage=0.0
        )

        report = AnalysisReport(
            session_id=session_dir.name,
            summary=summary
        )

        # Write error to JSON if needed
        error_data = {
            "error": "insufficient_data",
            "pitch_count": pitch_count,
            "minimum_required": 5,
            "message": "At least 5 pitches required for pattern analysis.",
            "recommendations": [
                "Record more pitches in this session",
                "Use cross-session analysis for trends"
            ]
        }

        error_path = session_dir / "analysis_report.json"
        with open(error_path, 'w') as f:
            json.dump(error_data, f, indent=2)

        return report

    def create_pitcher_profile(
        self,
        pitcher_id: str,
        session_dirs: List[Path]
    ) -> None:
        """Create or update pitcher profile from multiple sessions.

        Args:
            pitcher_id: Pitcher identifier
            session_dirs: List of session directories to include
        """
        # Load all pitches from sessions
        all_pitches = []

        for session_dir in session_dirs:
            try:
                pitches = self._load_session_pitches(session_dir)
                all_pitches.extend(pitches)
            except Exception as e:
                print(f"Warning: Could not load session {session_dir}: {e}")
                continue

        if not all_pitches:
            raise ValueError(f"No pitches found in {len(session_dirs)} sessions")

        # Count successfully loaded sessions
        num_sessions = len([d for d in session_dirs if d.exists()])

        # Create/update profile
        profile = self.profile_manager.create_or_update_profile(
            pitcher_id,
            all_pitches,
            num_sessions=num_sessions
        )

        print(f"Profile created/updated for {pitcher_id}")
        print(f"  Sessions analyzed: {profile.sessions_analyzed}")
        print(f"  Total pitches: {len(all_pitches)}")
        print(f"  Profile saved to: {self.profile_manager._get_profile_path(pitcher_id)}")

    def analyze_sessions(
        self,
        session_dirs: List[Path],
        output_dir: Optional[Path] = None
    ) -> dict:
        """Analyze trends across multiple sessions.

        Args:
            session_dirs: List of session directories to analyze
            output_dir: Optional output directory for reports (default: recordings/)

        Returns:
            Dictionary with cross-session analysis results
        """
        from datetime import datetime

        if output_dir is None:
            output_dir = Path("recordings")

        print(f"Analyzing {len(session_dirs)} sessions for trends...")

        # Load all sessions
        session_data = []
        for session_dir in session_dirs:
            try:
                pitches = self._load_session_pitches(session_dir)
                if len(pitches) >= 5:  # Only include sessions with sufficient data
                    session_data.append({
                        'session_dir': session_dir,
                        'session_id': session_dir.name,
                        'pitches': pitches
                    })
            except Exception as e:
                print(f"Warning: Could not load session {session_dir}: {e}")
                continue

        if len(session_data) < 2:
            raise ValueError(f"Need at least 2 sessions with sufficient data (found {len(session_data)})")

        # Analyze velocity trends
        velocity_trends = self._analyze_velocity_trends(session_data)

        # Analyze strike consistency
        strike_consistency = self._analyze_strike_consistency(session_data)

        # Analyze pitch mix evolution
        pitch_mix = self._analyze_pitch_mix(session_data)

        # Build report
        report = {
            'analysis_type': 'cross_session',
            'created_utc': datetime.utcnow().isoformat(),
            'sessions_analyzed': len(session_data),
            'total_pitches': sum(len(s['pitches']) for s in session_data),
            'velocity_trends': velocity_trends,
            'strike_consistency': strike_consistency,
            'pitch_mix_evolution': pitch_mix
        }

        # Save JSON report
        timestamp = datetime.utcnow().strftime('%Y-%m-%d')
        json_path = output_dir / f"cross_session_analysis_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✓ Cross-session analysis complete!")
        print(f"  Sessions analyzed: {len(session_data)}")
        print(f"  Total pitches: {report['total_pitches']}")
        print(f"  JSON report: {json_path}")

        return report

    def _analyze_velocity_trends(self, session_data: List[dict]) -> dict:
        """Analyze velocity trends across sessions.

        Args:
            session_data: List of session dictionaries

        Returns:
            Dictionary with velocity trend analysis
        """
        from analysis.pattern_detection.utils import linear_regression

        session_stats = []

        for i, session in enumerate(session_data):
            pitches = session['pitches']
            velocities = [p.speed_mph for p in pitches if p.speed_mph is not None]

            if velocities:
                import numpy as np
                session_stats.append({
                    'session_id': session['session_id'],
                    'session_index': i,
                    'avg_speed': float(np.mean(velocities)),
                    'std_speed': float(np.std(velocities, ddof=1)) if len(velocities) > 1 else 0.0,
                    'pitch_count': len(pitches)
                })

        # Compute trend
        if len(session_stats) >= 2:
            indices = [s['session_index'] for s in session_stats]
            speeds = [s['avg_speed'] for s in session_stats]

            slope, intercept = linear_regression(indices, speeds)

            # Determine trend direction
            if slope > 0.1:
                trend_direction = 'increasing'
            elif slope < -0.1:
                trend_direction = 'decreasing'
            else:
                trend_direction = 'stable'

            return {
                'sessions': session_stats,
                'trend_slope_mph_per_session': float(slope),
                'trend_direction': trend_direction,
                'trend_intercept': float(intercept)
            }

        return {'sessions': session_stats}

    def _analyze_strike_consistency(self, session_data: List[dict]) -> dict:
        """Analyze strike consistency across sessions.

        Args:
            session_data: List of session dictionaries

        Returns:
            Dictionary with strike consistency analysis
        """
        session_stats = []

        for session in session_data:
            pitches = session['pitches']
            strikes = sum(1 for p in pitches if p.is_strike)
            strike_pct = strikes / len(pitches) if pitches else 0.0

            # Create heatmap (3x3 grid)
            heatmap = [[0]*3 for _ in range(3)]
            for p in pitches:
                if p.zone_row is not None and p.zone_col is not None:
                    if 0 <= p.zone_row < 3 and 0 <= p.zone_col < 3:
                        heatmap[p.zone_row][p.zone_col] += 1

            session_stats.append({
                'session_id': session['session_id'],
                'strike_percentage': strike_pct,
                'zone_distribution': heatmap,
                'pitch_count': len(pitches)
            })

        # Compute average strike percentage
        if session_stats:
            avg_strike_pct = sum(s['strike_percentage'] for s in session_stats) / len(session_stats)
        else:
            avg_strike_pct = 0.0

        return {
            'sessions': session_stats,
            'average_strike_percentage': avg_strike_pct
        }

    def _analyze_pitch_mix(self, session_data: List[dict]) -> dict:
        """Analyze pitch mix evolution across sessions.

        Args:
            session_data: List of session dictionaries

        Returns:
            Dictionary with pitch mix analysis
        """
        from collections import defaultdict
        from analysis.pattern_detection.pitch_classifier import classify_pitches_hybrid

        session_stats = []

        for session in session_data:
            pitches = session['pitches']

            # Classify pitches
            classifications = classify_pitches_hybrid(pitches, n_clusters=3)

            # Count by type
            pitch_counts = defaultdict(int)
            for classification in classifications:
                pitch_counts[classification.heuristic_type] += 1

            # Convert to percentages
            pitch_mix = {
                pitch_type: count / len(pitches) if pitches else 0.0
                for pitch_type, count in pitch_counts.items()
            }

            # Find primary pitch
            primary_pitch = max(pitch_counts, key=pitch_counts.get) if pitch_counts else "Unknown"

            session_stats.append({
                'session_id': session['session_id'],
                'pitch_mix': pitch_mix,
                'primary_pitch': primary_pitch,
                'pitch_count': len(pitches)
            })

        return {
            'sessions': session_stats
        }


__all__ = ["PatternDetector"]

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

        # Create/update profile
        profile = self.profile_manager.create_or_update_profile(pitcher_id, all_pitches)

        print(f"Profile created/updated for {pitcher_id}")
        print(f"  Sessions analyzed: {len(session_dirs)}")
        print(f"  Total pitches: {len(all_pitches)}")
        print(f"  Profile saved to: {self.profile_manager._get_profile_path(pitcher_id)}")


__all__ = ["PatternDetector"]

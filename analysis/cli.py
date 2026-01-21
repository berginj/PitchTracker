"""CLI interface for pattern detection analysis."""

import argparse
import sys
from pathlib import Path

from analysis.pattern_detection import PatternDetector


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze pitch patterns from recorded sessions"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # analyze-session command
    analyze_parser = subparsers.add_parser(
        'analyze-session',
        help='Analyze a single session'
    )
    analyze_parser.add_argument(
        '--session',
        required=True,
        help='Path to session directory (e.g., recordings/session-2026-01-19_001)'
    )
    analyze_parser.add_argument(
        '--pitcher',
        help='Pitcher ID/name (optional)'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'analyze-session':
        return analyze_session(args)
    
    return 0


def analyze_session(args):
    """Analyze a single session."""
    session_path = Path(args.session)
    
    if not session_path.exists():
        print(f"Error: Session directory not found: {session_path}")
        return 1
    
    print(f"Analyzing session: {session_path}")
    print("=" * 60)
    
    try:
        detector = PatternDetector()
        
        # Run analysis
        report = detector.analyze_session(session_path, pitcher_id=args.pitcher)
        
        # Save reports
        detector.save_reports(report, session_path)
        
        # Print summary
        print(f"\n✓ Analysis complete!")
        print(f"\nSummary:")
        print(f"  Total Pitches: {report.total_pitches}")
        print(f"  Pitch Types: {report.pitch_types_detected}")
        print(f"  Avg Velocity: {report.average_velocity_mph:.1f} mph")
        print(f"  Strike %: {report.strike_percentage:.1f}%")
        print(f"  Anomalies: {report.anomalies_detected}")
        
        print(f"\nPitch Repertoire:")
        for rep in report.pitch_repertoire:
            print(f"  {rep.pitch_type}: {rep.count} ({rep.percentage:.1f}%) - {rep.avg_speed_mph:.1f} mph")
        
        if report.anomalies:
            print(f"\nAnomalies Detected:")
            for anomaly in report.anomalies[:5]:  # Show first 5
                print(f"  [{anomaly.severity.upper()}] {anomaly.anomaly_type}: {anomaly.recommendation[:80]}...")
        
        print(f"\nReports saved to:")
        print(f"  {session_path / 'analysis_report.json'}")
        print(f"  {session_path / 'analysis_report.html'}")
        
        return 0
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

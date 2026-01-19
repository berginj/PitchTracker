"""Command-line interface for pattern detection analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from analysis.pattern_detection.detector import PatternDetector


def analyze_session_command(args):
    """Handle analyze-session command.

    Args:
        args: Parsed command-line arguments
    """
    session_dir = Path(args.session)

    if not session_dir.exists():
        print(f"Error: Session directory not found: {session_dir}", file=sys.stderr)
        return 1

    print(f"Analyzing session: {session_dir}")

    detector = PatternDetector()

    try:
        report = detector.analyze_session(
            session_dir,
            pitcher_id=args.pitcher,
            output_json=not args.no_json,
            output_html=not args.no_html
        )

        print(f"\n✓ Analysis complete!")
        print(f"  Total pitches: {report.summary.total_pitches}")
        print(f"  Anomalies detected: {report.summary.anomalies_detected}")
        print(f"  Pitch types detected: {report.summary.pitch_types_detected}")
        print(f"  Average velocity: {report.summary.average_velocity_mph:.1f} mph")
        print(f"  Strike percentage: {report.summary.strike_percentage:.1%}")

        if not args.no_json:
            print(f"\n  JSON report: {session_dir / 'analysis_report.json'}")
        if not args.no_html:
            print(f"  HTML report: {session_dir / 'analysis_report.html'}")

        if report.baseline_comparison and report.baseline_comparison.profile_exists:
            print(f"\n  Baseline comparison included (pitcher: {args.pitcher})")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def create_profile_command(args):
    """Handle create-profile command.

    Args:
        args: Parsed command-line arguments
    """
    print(f"Creating/updating pitcher profile: {args.pitcher}")

    # Parse session paths (can be glob patterns)
    session_dirs = []

    for pattern in args.sessions:
        # Handle glob patterns
        if '*' in pattern or '?' in pattern:
            matched = list(Path('.').glob(pattern))
            session_dirs.extend([p for p in matched if p.is_dir()])
        else:
            path = Path(pattern)
            if path.exists() and path.is_dir():
                session_dirs.append(path)

    if not session_dirs:
        print(f"Error: No session directories found matching: {args.sessions}", file=sys.stderr)
        return 1

    print(f"Found {len(session_dirs)} sessions:")
    for session_dir in session_dirs:
        print(f"  - {session_dir}")

    detector = PatternDetector()

    try:
        detector.create_pitcher_profile(args.pitcher, session_dirs)
        return 0
    except Exception as e:
        print(f"Error creating profile: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def list_profiles_command(args):
    """Handle list-profiles command.

    Args:
        args: Parsed command-line arguments
    """
    detector = PatternDetector()
    profiles = detector.profile_manager.list_profiles()

    if not profiles:
        print("No pitcher profiles found.")
        return 0

    print(f"Found {len(profiles)} pitcher profile(s):")
    for pitcher_id in sorted(profiles):
        profile = detector.profile_manager.load_profile(pitcher_id)
        if profile:
            print(f"\n  {pitcher_id}")
            print(f"    Sessions: {profile.sessions_analyzed}")
            print(f"    Pitches: {profile.total_pitches}")
            print(f"    Last updated: {profile.last_updated_utc}")

    return 0


def analyze_sessions_command(args):
    """Handle analyze-sessions command.

    Args:
        args: Parsed command-line arguments
    """
    print(f"Analyzing cross-session trends...")

    # Parse session paths (can be glob patterns)
    session_dirs = []

    for pattern in args.sessions:
        # Handle glob patterns
        if '*' in pattern or '?' in pattern:
            matched = list(Path('.').glob(pattern))
            session_dirs.extend([p for p in matched if p.is_dir()])
        else:
            path = Path(pattern)
            if path.exists() and path.is_dir():
                session_dirs.append(path)

    if not session_dirs:
        print(f"Error: No session directories found matching: {args.sessions}", file=sys.stderr)
        return 1

    if len(session_dirs) < 2:
        print(f"Error: Need at least 2 sessions for cross-session analysis (found {len(session_dirs)})", file=sys.stderr)
        return 1

    print(f"Found {len(session_dirs)} sessions to analyze")

    # Determine output directory
    output_dir = Path(args.output) if args.output else Path("recordings")

    detector = PatternDetector()

    try:
        report = detector.analyze_sessions(session_dirs, output_dir=output_dir)
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during cross-session analysis: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PitchTracker Pattern Detection Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a single session
  python -m analysis.cli analyze-session --session recordings/session-2026-01-19_001

  # Analyze with baseline comparison
  python -m analysis.cli analyze-session --session recordings/session-2026-01-19_001 --pitcher john_doe

  # Create pitcher profile from multiple sessions
  python -m analysis.cli create-profile --pitcher john_doe --sessions "recordings/session-2026-01-*"

  # Analyze trends across multiple sessions
  python -m analysis.cli analyze-sessions --sessions "recordings/session-2026-01-*"

  # List all profiles
  python -m analysis.cli list-profiles
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # analyze-session command
    analyze_parser = subparsers.add_parser(
        'analyze-session',
        help='Analyze a single session'
    )
    analyze_parser.add_argument(
        '--session',
        required=True,
        help='Path to session directory'
    )
    analyze_parser.add_argument(
        '--pitcher',
        help='Pitcher ID for baseline comparison (optional)'
    )
    analyze_parser.add_argument(
        '--no-json',
        action='store_true',
        help='Skip JSON report generation'
    )
    analyze_parser.add_argument(
        '--no-html',
        action='store_true',
        help='Skip HTML report generation'
    )

    # create-profile command
    profile_parser = subparsers.add_parser(
        'create-profile',
        help='Create or update pitcher profile'
    )
    profile_parser.add_argument(
        '--pitcher',
        required=True,
        help='Pitcher ID'
    )
    profile_parser.add_argument(
        '--sessions',
        nargs='+',
        required=True,
        help='Session directories or glob patterns'
    )

    # list-profiles command
    subparsers.add_parser(
        'list-profiles',
        help='List all pitcher profiles'
    )

    # analyze-sessions command
    sessions_parser = subparsers.add_parser(
        'analyze-sessions',
        help='Analyze trends across multiple sessions'
    )
    sessions_parser.add_argument(
        '--sessions',
        nargs='+',
        required=True,
        help='Session directories or glob patterns'
    )
    sessions_parser.add_argument(
        '--output',
        help='Output directory for reports (default: recordings/)'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to command handler
    if args.command == 'analyze-session':
        return analyze_session_command(args)
    elif args.command == 'create-profile':
        return create_profile_command(args)
    elif args.command == 'list-profiles':
        return list_profiles_command(args)
    elif args.command == 'analyze-sessions':
        return analyze_sessions_command(args)

    return 0


if __name__ == '__main__':
    sys.exit(main())

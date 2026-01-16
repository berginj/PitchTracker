"""Export ML training submission packages for cloud upload.

Creates ZIP packages containing session data for ML model training.
Supports two variants:
  - full: Videos + all ML data (4-5 GB, enables all 5 models)
  - telemetry_only: JSON metadata only (50-100 MB, enables 2 of 5 models)

Usage:
    # Full package (videos + telemetry)
    python export_ml_submission.py \\
        --session-dir "recordings/session-2026-01-16_001" \\
        --output "ml-submission-full.zip" \\
        --type full \\
        --pitcher-id "anonymous-123" \\
        --location "Indoor Facility A"

    # Telemetry-only (no videos)
    python export_ml_submission.py \\
        --session-dir "recordings/session-2026-01-16_001" \\
        --output "ml-submission-telemetry.zip" \\
        --type telemetry_only \\
        --pitcher-id "anonymous-123" \\
        --location "Indoor Facility A" \\
        --reason privacy_preserving
"""

import argparse
import hashlib
import json
import time
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List

from contracts.versioning import APP_VERSION, SCHEMA_VERSION


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Export ML training submission package",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        required=True,
        help="Session directory path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output ZIP file path",
    )
    parser.add_argument(
        "--type",
        choices=["full", "telemetry_only"],
        required=True,
        help="Submission type: 'full' (with videos) or 'telemetry_only' (no videos)",
    )
    parser.add_argument(
        "--rig-id",
        default=None,
        help="Unique rig identifier",
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Recording location",
    )
    parser.add_argument(
        "--pitcher-id",
        default=None,
        help="Anonymous pitcher identifier",
    )
    parser.add_argument(
        "--operator",
        default=None,
        help="Operator/coach identifier",
    )
    parser.add_argument(
        "--player-consent",
        action="store_true",
        default=False,
        help="Player consent obtained for data sharing",
    )
    parser.add_argument(
        "--anonymized",
        action="store_true",
        default=True,
        help="Data has been anonymized",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=730,
        help="Data retention period (days)",
    )
    parser.add_argument(
        "--reason",
        choices=["privacy_preserving", "bandwidth", "storage"],
        default="privacy_preserving",
        help="Reason for telemetry-only (if applicable)",
    )
    return parser.parse_args()


def collect_files_to_package(
    session_dir: Path, submission_type: str
) -> Dict[str, List[Path]]:
    """Collect files to include in submission package.

    Args:
        session_dir: Session directory
        submission_type: "full" or "telemetry_only"

    Returns:
        Dictionary mapping category to list of file paths
    """
    files: Dict[str, List[Path]] = {
        "session_metadata": [],
        "session_videos": [],
        "calibration": [],
        "pitch_metadata": [],
        "pitch_videos": [],
        "detections": [],
        "observations": [],
        "frames": [],
    }

    # Session-level files (always included)
    session_manifest = session_dir / "manifest.json"
    session_summary = session_dir / "session_summary.json"
    if session_manifest.exists():
        files["session_metadata"].append(session_manifest)
    if session_summary.exists():
        files["session_metadata"].append(session_summary)

    # Session videos (full package only)
    if submission_type == "full":
        session_left = session_dir / "session_left.avi"
        session_right = session_dir / "session_right.avi"
        left_ts = session_dir / "session_left_timestamps.csv"
        right_ts = session_dir / "session_right_timestamps.csv"
        for f in [session_left, session_right, left_ts, right_ts]:
            if f.exists():
                files["session_videos"].append(f)

    # Calibration metadata (always included)
    calib_dir = session_dir / "calibration"
    if calib_dir.exists():
        files["calibration"].extend(calib_dir.glob("*.json"))

    # Pitch-level files
    pitch_dirs = [d for d in session_dir.iterdir() if d.is_dir() and "-pitch-" in d.name]

    for pitch_dir in sorted(pitch_dirs):
        # Pitch manifest (always included)
        pitch_manifest = pitch_dir / "manifest.json"
        if pitch_manifest.exists():
            files["pitch_metadata"].append(pitch_manifest)

        # Pitch videos (full package only)
        if submission_type == "full":
            left_video = pitch_dir / "left.avi"
            right_video = pitch_dir / "right.avi"
            left_ts = pitch_dir / "left_timestamps.csv"
            right_ts = pitch_dir / "right_timestamps.csv"
            for f in [left_video, right_video, left_ts, right_ts]:
                if f.exists():
                    files["pitch_videos"].append(f)

        # Detections (always included if present)
        detections_dir = pitch_dir / "detections"
        if detections_dir.exists():
            files["detections"].extend(detections_dir.glob("*.json"))

        # Observations (always included if present)
        observations_dir = pitch_dir / "observations"
        if observations_dir.exists():
            files["observations"].extend(observations_dir.glob("*.json"))

        # Key frames (full package only)
        if submission_type == "full":
            frames_dir = pitch_dir / "frames"
            if frames_dir.exists():
                files["frames"].extend(frames_dir.rglob("*.png"))

    return files


def calculate_total_size(files: Dict[str, List[Path]]) -> int:
    """Calculate total size of all files in bytes.

    Args:
        files: Dictionary of file lists

    Returns:
        Total size in bytes
    """
    total = 0
    for file_list in files.values():
        for f in file_list:
            if f.exists():
                total += f.stat().st_size
    return total


def create_submission_manifest(
    session_dir: Path,
    submission_type: str,
    source: Dict[str, Any],
    privacy: Dict[str, Any],
    intended_use: List[str],
    size_bytes: int,
    checksum: str,
    telemetry_only_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Create submission manifest.

    Args:
        session_dir: Session directory
        submission_type: "full" or "telemetry_only"
        source: Source metadata
        privacy: Privacy settings
        intended_use: List of intended ML use cases
        size_bytes: Total package size
        checksum: Package checksum
        telemetry_only_reason: Reason for telemetry-only (if applicable)

    Returns:
        Submission manifest dictionary
    """
    # Load session summary for metadata
    session_summary_path = session_dir / "session_summary.json"
    session_summary = {}
    if session_summary_path.exists():
        session_summary = json.loads(session_summary_path.read_text())

    submission_id = f"ml-submission-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}"

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "submission_id": submission_id,
        "submission_type": submission_type,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session": {
            "session_id": session_summary.get("session_id", session_dir.name),
            "started_utc": session_summary.get("started_utc"),
            "ended_utc": session_summary.get("ended_utc"),
            "pitch_count": session_summary.get("pitch_count", 0),
        },
        "source": source,
        "data_manifest": {
            "videos": {
                "session_videos": submission_type == "full",
                "pitch_videos": submission_type == "full",
                "key_frames": submission_type == "full",
            },
            "telemetry": {
                "detections": True,
                "observations": True,
                "calibration": True,
                "performance_metrics": True,
            },
        },
        "size_bytes": size_bytes,
        "checksum_sha256": checksum,
        "intended_use": intended_use,
        "privacy": privacy,
    }

    if submission_type == "telemetry_only" and telemetry_only_reason:
        manifest["telemetry_only_reason"] = telemetry_only_reason

    return manifest


def create_ml_submission(
    session_dir: Path,
    output_path: Path,
    submission_type: str,
    source: Optional[Dict[str, Any]] = None,
    privacy: Optional[Dict[str, Any]] = None,
    telemetry_only_reason: Optional[str] = None,
) -> None:
    """Create ML training submission package.

    Args:
        session_dir: Session directory path
        output_path: Output ZIP file path
        submission_type: "full" or "telemetry_only"
        source: Source metadata (rig_id, location, pitcher_id, operator)
        privacy: Privacy settings (player_consent, anonymized, retention_days)
        telemetry_only_reason: Reason for telemetry-only (if applicable)
    """
    if not session_dir.exists():
        raise FileNotFoundError(f"Session directory not found: {session_dir}")

    # Default source metadata
    if source is None:
        source = {
            "app": "PitchTracker",
            "rig_id": None,
            "location": None,
            "pitcher_id": None,
            "operator": None,
        }
    else:
        source.setdefault("app", "PitchTracker")

    # Default privacy settings
    if privacy is None:
        privacy = {
            "player_consent": False,
            "anonymized": True,
            "retention_days": 730,
        }

    # Intended use cases based on submission type
    if submission_type == "full":
        intended_use = [
            "ball_detector_training",
            "field_segmentation_training",
            "pose_estimation_training",
            "trajectory_model_training",
            "self_calibration_training",
        ]
    else:  # telemetry_only
        intended_use = [
            "trajectory_model_training",
            "self_calibration_training",
        ]

    print(f"Collecting files for {submission_type} submission...")
    files = collect_files_to_package(session_dir, submission_type)

    # Calculate total size
    size_bytes = calculate_total_size(files)
    print(f"Total size: {size_bytes / 1024 / 1024:.1f} MB")

    # Count files
    total_files = sum(len(file_list) for file_list in files.values())
    print(f"Total files: {total_files}")

    # Create ZIP package
    print(f"Creating ZIP package: {output_path}")
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        # Add all files
        file_count = 0
        for category, file_list in files.items():
            for file_path in file_list:
                if file_path.exists():
                    # Create relative path within ZIP
                    rel_path = file_path.relative_to(session_dir)

                    # Organize by category
                    if category in ["session_metadata", "session_videos"]:
                        zip_path = f"session/{rel_path}"
                    elif category == "calibration":
                        zip_path = f"session/calibration/{rel_path.name}"
                    else:
                        # Pitch files go under pitches/{pitch-id}/
                        zip_path = f"pitches/{rel_path}"

                    archive.write(file_path, zip_path)
                    file_count += 1
                    if file_count % 100 == 0:
                        print(f"  Added {file_count}/{total_files} files...")

    print(f"Package created: {output_path}")

    # Calculate checksum
    print("Calculating checksum...")
    sha256 = hashlib.sha256()
    with open(output_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    checksum = sha256.hexdigest()
    print(f"SHA256: {checksum}")

    # Create submission manifest
    print("Creating submission manifest...")
    submission_manifest = create_submission_manifest(
        session_dir=session_dir,
        submission_type=submission_type,
        source=source,
        privacy=privacy,
        intended_use=intended_use,
        size_bytes=size_bytes,
        checksum=checksum,
        telemetry_only_reason=telemetry_only_reason,
    )

    # Add manifest to ZIP
    print("Adding submission manifest to package...")
    with zipfile.ZipFile(output_path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest_json = json.dumps(submission_manifest, indent=2)
        archive.writestr("submission_manifest.json", manifest_json)

    # Save manifest as separate file for reference
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(submission_manifest, indent=2))
    print(f"Submission manifest saved: {manifest_path}")

    print("\n✓ ML submission package complete!")
    print(f"  Type: {submission_type}")
    print(f"  Size: {size_bytes / 1024 / 1024:.1f} MB")
    print(f"  Files: {total_files}")
    print(f"  Package: {output_path}")
    print(f"  Manifest: {manifest_path}")

    if submission_type == "full":
        print("\n  Enables: All 5 ML models (100% of automation roadmap)")
        print("    ✓ Ball detector")
        print("    ✓ Field segmentation")
        print("    ✓ Batter pose estimation")
        print("    ✓ Trajectory models")
        print("    ✓ Self-calibration")
    else:
        print("\n  Enables: 2 of 5 ML models (40% of automation roadmap)")
        print("    ✓ Trajectory models")
        print("    ✓ Self-calibration")
        print("    ✗ Ball detector (requires videos)")
        print("    ✗ Field segmentation (requires videos)")
        print("    ✗ Batter pose estimation (requires videos)")


def main() -> None:
    """Main entry point."""
    args = parse_args()

    source = {
        "app": "PitchTracker",
        "rig_id": args.rig_id,
        "location": args.location,
        "pitcher_id": args.pitcher_id,
        "operator": args.operator,
    }

    privacy = {
        "player_consent": args.player_consent,
        "anonymized": args.anonymized,
        "retention_days": args.retention_days,
    }

    create_ml_submission(
        session_dir=args.session_dir,
        output_path=args.output,
        submission_type=args.type,
        source=source,
        privacy=privacy,
        telemetry_only_reason=args.reason if args.type == "telemetry_only" else None,
    )


if __name__ == "__main__":
    main()

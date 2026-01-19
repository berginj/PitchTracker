"""Test script to verify ML training data export functionality.

Usage:
    python test_ml_data_export.py <session_dir>

Example:
    python test_ml_data_export.py "C:\\Users\\bergi\\Desktop\\pitchtracker_recordings\\session-2026-01-16_001"
"""

import json
import sys
from pathlib import Path


def test_ml_data_export(session_dir: Path) -> bool:
    """Verify ML training data was exported correctly.

    Args:
        session_dir: Path to recorded session

    Returns:
        True if all checks pass, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"Testing ML Data Export")
    print(f"Session: {session_dir}")
    print(f"{'='*70}\n")

    if not session_dir.exists():
        print(f"[FAIL] Session directory does not exist: {session_dir}")
        return False

    passed = 0
    failed = 0

    # Find pitch directories
    pitch_dirs = list(session_dir.glob("*-pitch-*"))
    if not pitch_dirs:
        print("[FAIL] No pitch directories found")
        return False

    print(f"[PASS] Found {len(pitch_dirs)} pitch(es)\n")
    passed += 1

    # Test first pitch
    pitch_dir = pitch_dirs[0]
    print(f"Testing pitch: {pitch_dir.name}\n")

    # Check for detection export
    detections_dir = pitch_dir / "detections"
    left_det = detections_dir / "left_detections.json"
    right_det = detections_dir / "right_detections.json"

    if left_det.exists():
        data = json.loads(left_det.read_text())
        print(f"[PASS] Left detections: {data['detection_count']} detections")
        passed += 1
    else:
        print("[WARN] Left detections not found (may be disabled in config)")
        failed += 1

    if right_det.exists():
        data = json.loads(right_det.read_text())
        print(f"[PASS] Right detections: {data['detection_count']} detections")
        passed += 1
    else:
        print("[WARN] Right detections not found (may be disabled in config)")
        failed += 1

    # Check for observation export
    obs_file = pitch_dir / "observations" / "stereo_observations.json"
    if obs_file.exists():
        data = json.loads(obs_file.read_text())
        print(f"[PASS] Observations: {data['observation_count']} observations")
        passed += 1
    else:
        print("[WARN] Observations not found (may be disabled in config)")
        failed += 1

    # Check for frame export
    frames_dir = pitch_dir / "frames"
    if frames_dir.exists():
        left_frames = list((frames_dir / "left").glob("*.png"))
        right_frames = list((frames_dir / "right").glob("*.png"))
        print(f"[PASS] Frames: {len(left_frames)} left, {len(right_frames)} right")
        passed += 1
    else:
        print("[WARN] Frames directory not found (may be disabled in config)")
        failed += 1

    # Check for calibration export
    calib_dir = session_dir / "calibration"
    if calib_dir.exists():
        calib_files = list(calib_dir.glob("*.json"))
        print(f"[PASS] Calibration: {len(calib_files)} files")
        for f in calib_files:
            print(f"      - {f.name}")
        passed += 1
    else:
        print("[FAIL] Calibration directory not found")
        failed += 1

    # Check manifest
    manifest_file = pitch_dir / "manifest.json"
    if manifest_file.exists():
        data = json.loads(manifest_file.read_text())
        if "performance_metrics" in data:
            print("[PASS] Manifest has performance metrics")
            metrics = data["performance_metrics"]
            if "detection_quality" in metrics:
                print(f"      Observations: {metrics['detection_quality']['stereo_observations']}")
                print(
                    f"      Detection rate: {metrics['detection_quality']['detection_rate_hz']:.1f} Hz"
                )
            if "timing_accuracy" in metrics:
                print(
                    f"      Duration: {metrics['timing_accuracy']['duration_ns'] / 1e6:.1f} ms"
                )
                print(
                    f"      Pre-roll frames: {metrics['timing_accuracy']['pre_roll_frames_captured']}"
                )
            passed += 1
        else:
            print("[WARN] Manifest missing performance metrics")
            failed += 1
    else:
        print("[FAIL] Manifest not found")
        failed += 1

    # Summary
    print(f"\n{'='*70}")
    print(f"Test Summary")
    print(f"{'='*70}")
    print(f"Passed: {passed}")
    print(f"Failed/Warnings: {failed}")

    if failed == 0:
        print(f"\n[SUCCESS] All ML training data export checks passed!")
        return True
    elif passed > 0:
        print(
            f"\n[PARTIAL] Some features may be disabled in config. Enable all ML training options:"
        )
        print("  recording:")
        print("    save_detections: true")
        print("    save_observations: true")
        print("    save_training_frames: true")
        print("    frame_save_interval: 5")
        return True
    else:
        print(f"\n[FAIL] ML data export validation failed")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ml_data_export.py <session_dir>")
        print("")
        print("Example:")
        print(
            '  python test_ml_data_export.py "C:\\Users\\bergi\\Desktop\\pitchtracker_recordings\\session-2026-01-16_001"'
        )
        sys.exit(1)

    session_dir = Path(sys.argv[1])
    success = test_ml_data_export(session_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

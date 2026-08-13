#!/usr/bin/env python3
"""Check stereo camera alignment from a single frame pair.

Analyzes vertical alignment, convergence (toe-in), and rotation differences
to diagnose calibration issues BEFORE attempting checkerboard calibration.

Usage:
    python scripts/check_camera_alignment.py --left path/to/left.png --right path/to/right.png

Or capture frames directly from cameras:
    python scripts/check_camera_alignment.py --capture --backend opencv

Hardware capture is a manual setup boundary; automated validation uses saved
local image pairs and does not claim physical calibration validity.
"""

# CRITICAL: Setup file logging BEFORE any other imports
import sys
from pathlib import Path
from datetime import datetime

# Add project root to Python path so we can import capture module
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Save original stdout/stderr for console messages
_original_stdout = sys.stdout
_original_stderr = sys.stderr

# Create log file immediately with UTF-8 encoding (Windows compatible)
log_file_path = Path("alignment_check_log.txt")
log_file = open(log_file_path, "w", encoding="utf-8", buffering=1)  # Line buffered, UTF-8

# Print to console first
_original_stdout.write(f"\n{'='*70}\n")
_original_stdout.write("CAMERA ALIGNMENT CHECKER\n")
_original_stdout.write(f"{'='*70}\n\n")
_original_stdout.write(f"All output is being logged to: {log_file_path.absolute()}\n")
_original_stdout.write("If the window closes immediately, check this log file for errors.\n\n")
_original_stdout.flush()

# Now redirect to log file
sys.stdout = log_file
sys.stderr = log_file
print(f"=== ALIGNMENT CHECKER LOG === {datetime.now()}")
print(f"Log file: {log_file_path.absolute()}")
print("Script starting...\n")
sys.stdout.flush()

import argparse  # noqa: E402
from typing import Tuple  # noqa: E402

print("Importing cv2...")
sys.stdout.flush()
import cv2  # noqa: E402

print("Importing numpy...")
sys.stdout.flush()
import numpy as np  # noqa: E402

print("Imports successful!\n")
sys.stdout.flush()


from scripts.camera_alignment_support import (  # noqa: E402
    analyze_horizontal_alignment,
    analyze_rotation,
    analyze_vertical_alignment,
    find_feature_matches,
    load_frame,
    print_alignment_report,
)
from exceptions import CalibrationError, CalibrationExecutionError, CalibrationInputError  # noqa: E402


def capture_frame_pair(
    backend: str = "opencv", left_camera: str = "0", right_camera: str = "1"
) -> Tuple[np.ndarray, np.ndarray]:
    """Capture a single frame pair from cameras.

    Args:
        backend: Camera backend ("opencv" or "uvc")
        left_camera: Left camera identifier (index for opencv, serial for uvc)
        right_camera: Right camera identifier (index for opencv, serial for uvc)

    Returns:
        Tuple of (left_frame, right_frame) as BGR images
    """
    print("\n=== CAPTURING FRAMES ===")
    print(f"Using cameras: Left={left_camera}, Right={right_camera}")
    print("Point cameras at a textured scene (not blank wall)")
    print("Press ENTER when ready...")
    sys.stdout.flush()

    # Temporarily restore console for user input
    sys.stdout = _original_stdout
    sys.stderr = _original_stderr
    print("\n" + "=" * 70)
    print("Point cameras at a textured scene (posters, books, NOT blank wall)")
    print("Make sure both cameras can see the same objects")
    print("=" * 70)
    input("Press ENTER to capture frames...")

    # Restore log file output
    sys.stdout = log_file
    sys.stderr = log_file
    print("User pressed ENTER, continuing...")

    if backend == "opencv":
        from capture.opencv_backend import OpenCVCamera

        print("Opening cameras...")
        left_cam = OpenCVCamera()
        right_cam = OpenCVCamera()

        try:
            print(f"Opening left camera: {left_camera}")
            left_cam.open(left_camera)

            print(f"Opening right camera: {right_camera}")
            right_cam.open(right_camera)

            print("Configuring camera modes...")
            left_cam.set_mode(1280, 720, 30, "YUYV")
            right_cam.set_mode(1280, 720, 30, "YUYV")

            print("Warming up cameras (3 seconds)...")
            import time

            time.sleep(3)

            # Capture frames
            print("Capturing...")
            left_frame = left_cam.read_frame(timeout_ms=1000)
            right_frame = right_cam.read_frame(timeout_ms=1000)

            return left_frame.image, right_frame.image

        except Exception as exc:
            print(f"Error capturing frames: {exc}")
            raise CalibrationExecutionError("Could not capture an alignment frame pair") from exc
        finally:
            left_cam.close()
            right_cam.close()
    else:
        raise CalibrationInputError(f"Backend {backend} is not supported for auto-capture; use saved images")


def main():
    # Print header immediately so user knows script started
    print("\n" + "=" * 70)
    print("CAMERA ALIGNMENT CHECKER")
    print("=" * 70 + "\n")

    parser = argparse.ArgumentParser(
        description="Check stereo camera alignment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture from cameras 0 and 1 (default)
  python scripts/check_camera_alignment.py --capture

  # Capture from specific cameras
  python scripts/check_camera_alignment.py --capture --left-camera 0 --right-camera 1

  # Capture and save frames
  python scripts/check_camera_alignment.py --capture --save

  # Check existing images
  python scripts/check_camera_alignment.py --left left.png --right right.png
        """,
    )
    parser.add_argument("--left", type=Path, help="Path to left camera image")
    parser.add_argument("--right", type=Path, help="Path to right camera image")
    parser.add_argument("--capture", action="store_true", help="Capture frames from cameras directly")
    parser.add_argument("--backend", default="opencv", choices=["opencv", "uvc"], help="Camera backend for capture")
    parser.add_argument("--left-camera", default="0", help="Left camera identifier (default: 0)")
    parser.add_argument("--right-camera", default="1", help="Right camera identifier (default: 1)")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save captured frames to alignment_check_left.png and alignment_check_right.png",
    )

    args = parser.parse_args()

    print(f"Arguments received: {args}\n")

    try:
        # Get frames
        if args.capture:
            print("Capturing frames from cameras...")
            left_img, right_img = capture_frame_pair(args.backend, args.left_camera, args.right_camera)

            if args.save:
                cv2.imwrite("alignment_check_left.png", left_img)
                cv2.imwrite("alignment_check_right.png", right_img)
                print("Saved frames to alignment_check_left.png and alignment_check_right.png")
        elif args.left and args.right:
            print(f"Loading frames from {args.left} and {args.right}...")
            left_img = load_frame(args.left)
            right_img = load_frame(args.right)
        else:
            print("Error: Must provide either --capture or both --left and --right")
            print("\nExamples:")
            print("  python scripts/check_camera_alignment.py --capture")
            print("  python scripts/check_camera_alignment.py --capture --left-camera 0 --right-camera 1")
            print("  python scripts/check_camera_alignment.py --left left.png --right right.png")
            input("\nPress ENTER to exit...")
            sys.exit(1)

        # Find feature matches
        print("Finding feature matches...")
        pts1, pts2 = find_feature_matches(left_img, right_img, max_features=1000)
        print(f"Found {len(pts1)} matched features")

        # Analyze alignment
        print("Analyzing alignment...")
        vertical = analyze_vertical_alignment(pts1, pts2)
        horizontal = analyze_horizontal_alignment(pts1, pts2)
        rotation = analyze_rotation(pts1, pts2)

        # Print report
        overall_pass = print_alignment_report(vertical, horizontal, rotation, len(pts1))

        # Pause before exit on Windows so user can read results
        print("\n" + "=" * 70)
        print("Analysis complete!")
        print("=" * 70)

        # Restore console output
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr
        log_file.close()

        # Print to console
        print(f"\n{'='*70}")
        print("ALIGNMENT CHECK COMPLETE")
        print(f"{'='*70}")
        print(f"\nFull report saved to: {log_file_path.absolute()}")
        print("\nPress ENTER to exit...")
        input()

        # Exit code for scripting
        sys.exit(0 if overall_pass else 1)

    except CalibrationError as e:
        print(f"\n{'='*70}")
        print(f"ERROR: {e}")
        print("=" * 70)
        print("\nTips:")
        print("  - Point cameras at textured scene (posters, furniture, etc.)")
        print("  - Avoid blank walls or low-contrast surfaces")
        print("  - Ensure good lighting")
        print("  - Make sure camera indices are correct (--left-camera 0 --right-camera 1)")
        print("\n" + "=" * 70)

        # Restore console output
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr
        log_file.close()

        # Print to console
        print(f"\n{'='*70}")
        print(f"ERROR: {e}")
        print(f"{'='*70}")
        print(f"\nFull error log saved to: {log_file_path.absolute()}")
        print("\nPress ENTER to exit...")
        input()
        sys.exit(1)
    except Exception as e:
        print(f"\n{'='*70}")
        print(f"UNEXPECTED ERROR: {e}")
        print("=" * 70)
        import traceback

        traceback.print_exc()
        print("=" * 70)

        # Restore console output
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr
        log_file.close()

        # Print to console
        print(f"\n{'='*70}")
        print(f"UNEXPECTED ERROR: {e}")
        print(f"{'='*70}")
        print(f"\nFull error log saved to: {log_file_path.absolute()}")
        print("\nPress ENTER to exit...")
        input()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        # Restore console output
        try:
            sys.stdout = _original_stdout
            sys.stderr = _original_stderr
            log_file.close()
        except Exception:
            pass
        print("\nInterrupted by user")
        input("Press ENTER to exit...")
        sys.exit(0)
    except SystemExit:
        # Don't catch sys.exit() calls
        raise
    except Exception as e:
        print("\n" + "=" * 70)
        print("FATAL ERROR - Script failed to run")
        print("=" * 70)
        print(f"\nError: {e}\n")
        import traceback

        traceback.print_exc()
        print("\n" + "=" * 70)
        print("\nIf this error persists, please report it with the error message above.")
        print("=" * 70)

        # Restore console output
        try:
            sys.stdout = _original_stdout
            sys.stderr = _original_stderr
            log_file.close()

            # Print to console
            print("\n" + "=" * 70)
            print("FATAL ERROR - Script failed to run")
            print("=" * 70)
            print(f"\nError: {e}\n")
            traceback.print_exc()
            print(f"\nFull error log saved to: {log_file_path.absolute()}")
            print("=" * 70)
        except Exception:
            pass  # If we can't restore output, at least log file has the error

        input("\nPress ENTER to exit...")
        sys.exit(1)

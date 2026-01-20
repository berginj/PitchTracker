#!/usr/bin/env python3
"""Check stereo camera alignment from a single frame pair.

Analyzes vertical alignment, convergence (toe-in), and rotation differences
to diagnose calibration issues BEFORE attempting checkerboard calibration.

Usage:
    python scripts/check_camera_alignment.py --left path/to/left.png --right path/to/right.png

Or capture frames directly from cameras:
    python scripts/check_camera_alignment.py --capture --backend opencv
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

# Create log file immediately
log_file_path = Path("alignment_check_log.txt")
log_file = open(log_file_path, "w", buffering=1)  # Line buffered

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

import argparse
from typing import Optional, Tuple

print("Importing cv2...")
sys.stdout.flush()
import cv2
print("Importing numpy...")
sys.stdout.flush()
import numpy as np
print("Imports successful!\n")
sys.stdout.flush()


def load_frame(path: Path) -> np.ndarray:
    """Load frame from file."""
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Could not load image: {path}")
    return img


def capture_frame_pair(backend: str = "opencv", left_camera: str = "0", right_camera: str = "1") -> Tuple[np.ndarray, np.ndarray]:
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
    input()

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

            left_cam.close()
            right_cam.close()

            return left_frame.image, right_frame.image

        except Exception as e:
            print(f"Error capturing frames: {e}")
            left_cam.close()
            right_cam.close()
            raise
    else:
        print(f"Backend {backend} not yet supported for auto-capture")
        print("Please capture frames manually and use --left/--right flags")
        sys.exit(1)


def find_feature_matches(img1: np.ndarray, img2: np.ndarray, max_features: int = 1000) -> Tuple[np.ndarray, np.ndarray]:
    """Find corresponding feature points between two images.

    Args:
        img1: First image (BGR or grayscale)
        img2: Second image (BGR or grayscale)
        max_features: Maximum number of features to detect

    Returns:
        Tuple of (points1, points2) as Nx2 arrays of matched coordinates
    """
    # Convert to grayscale if needed
    if img1.ndim == 3:
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    else:
        gray1 = img1

    if img2.ndim == 3:
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    else:
        gray2 = img2

    # Use ORB (fast, patent-free)
    orb = cv2.ORB_create(nfeatures=max_features)

    # Detect keypoints and compute descriptors
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        raise ValueError("Not enough features detected. Point cameras at textured scene (not blank wall).")

    # Match features using BFMatcher
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    if len(matches) < 20:
        raise ValueError(f"Not enough matches found ({len(matches)}). Need textured scene with detail.")

    # Sort by distance (quality)
    matches = sorted(matches, key=lambda x: x.distance)

    # Take best matches (top 50% or at least 50)
    num_good = max(50, len(matches) // 2)
    good_matches = matches[:num_good]

    # Extract matched point coordinates
    pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])

    return pts1, pts2


def analyze_vertical_alignment(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze vertical alignment between cameras.

    Cameras should be at same height (y-coordinates should match).

    Args:
        pts1: Nx2 array of points from left camera
        pts2: Nx2 array of corresponding points from right camera

    Returns:
        Dict with vertical alignment metrics
    """
    # Calculate vertical disparity (difference in y-coordinates)
    y1 = pts1[:, 1]
    y2 = pts2[:, 1]
    vertical_disparity = y2 - y1

    # Statistics
    mean_v_disp = np.mean(vertical_disparity)
    std_v_disp = np.std(vertical_disparity)
    max_v_disp = np.max(np.abs(vertical_disparity))

    # Thresholds (empirical, for 720p resolution)
    EXCELLENT_THRESHOLD = 2.0  # pixels
    GOOD_THRESHOLD = 5.0
    ACCEPTABLE_THRESHOLD = 10.0

    if max_v_disp < EXCELLENT_THRESHOLD:
        status = "EXCELLENT"
        severity = "ok"
        message = "Cameras are very well aligned vertically"
    elif max_v_disp < GOOD_THRESHOLD:
        status = "GOOD"
        severity = "ok"
        message = "Cameras are well aligned vertically"
    elif max_v_disp < ACCEPTABLE_THRESHOLD:
        status = "ACCEPTABLE"
        severity = "warning"
        message = "Slight vertical misalignment detected"
    else:
        status = "POOR"
        severity = "error"
        message = "Significant vertical misalignment - cameras at different heights"

    return {
        "status": status,
        "severity": severity,
        "message": message,
        "mean_vertical_disparity_px": float(mean_v_disp),
        "std_vertical_disparity_px": float(std_v_disp),
        "max_vertical_disparity_px": float(max_v_disp),
        "recommendation": "Adjust camera heights to match" if severity == "error" else None,
    }


def analyze_horizontal_alignment(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze horizontal alignment (convergence/toe-in).

    For parallel cameras, horizontal disparity should be roughly constant
    across the image. Toe-in causes disparity to vary with position.

    Args:
        pts1: Nx2 array of points from left camera
        pts2: Nx2 array of corresponding points from right camera

    Returns:
        Dict with horizontal alignment metrics
    """
    # Calculate horizontal disparity
    x1 = pts1[:, 0]
    x2 = pts2[:, 0]
    horizontal_disparity = x1 - x2  # Left - right (positive = right camera sees it more to the right)

    # For parallel cameras, disparity should be roughly constant
    # Toe-in causes disparity to vary systematically with x position
    mean_h_disp = np.mean(horizontal_disparity)
    std_h_disp = np.std(horizontal_disparity)

    # Check for systematic variation (sign of toe-in)
    # Correlation between x-position and disparity
    correlation = np.corrcoef(x1, horizontal_disparity)[0, 1]

    # Thresholds
    STD_EXCELLENT = 5.0  # pixels
    STD_GOOD = 10.0
    STD_ACCEPTABLE = 20.0

    CORR_EXCELLENT = 0.1  # Low correlation = good
    CORR_ACCEPTABLE = 0.3

    # Determine status based on both metrics
    if std_h_disp < STD_EXCELLENT and abs(correlation) < CORR_EXCELLENT:
        status = "EXCELLENT"
        severity = "ok"
        message = "Cameras are perfectly parallel (no convergence)"
    elif std_h_disp < STD_GOOD and abs(correlation) < CORR_ACCEPTABLE:
        status = "GOOD"
        severity = "ok"
        message = "Cameras are well aligned (minimal convergence)"
    elif std_h_disp < STD_ACCEPTABLE:
        status = "ACCEPTABLE"
        severity = "warning"
        message = "Slight convergence detected - cameras slightly angled"
    else:
        status = "POOR"
        severity = "error"
        if correlation > 0.3:
            message = "Cameras toed-IN (converging) - angled toward each other"
        elif correlation < -0.3:
            message = "Cameras toed-OUT (diverging) - angled away from each other"
        else:
            message = "Cameras not parallel - high disparity variation"

    return {
        "status": status,
        "severity": severity,
        "message": message,
        "mean_horizontal_disparity_px": float(mean_h_disp),
        "std_horizontal_disparity_px": float(std_h_disp),
        "position_disparity_correlation": float(correlation),
        "recommendation": "Adjust camera angles to be parallel" if severity == "error" else None,
    }


def analyze_rotation(pts1: np.ndarray, pts2: np.ndarray) -> dict:
    """Analyze rotation difference between cameras.

    Detects if one camera is rolled/tilted relative to the other.

    Args:
        pts1: Nx2 array of points from left camera
        pts2: Nx2 array of corresponding points from right camera

    Returns:
        Dict with rotation metrics
    """
    # Estimate affine transformation between point sets
    # This includes rotation, scale, and translation
    try:
        # Need at least 3 points
        if len(pts1) < 3:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Not enough points to estimate rotation",
                "rotation_deg": 0.0,
            }

        # Use RANSAC to be robust to outliers
        M, mask = cv2.estimateAffinePartial2D(pts1, pts2, method=cv2.RANSAC, ransacReprojThreshold=5.0)

        if M is None:
            return {
                "status": "UNKNOWN",
                "severity": "warning",
                "message": "Could not estimate rotation (no consistent transform found)",
                "rotation_deg": 0.0,
            }

        # Extract rotation angle from affine matrix
        # M = [cos(θ)  -sin(θ)  tx]
        #     [sin(θ)   cos(θ)  ty]
        rotation_rad = np.arctan2(M[1, 0], M[0, 0])
        rotation_deg = np.degrees(rotation_rad)

        # Thresholds
        EXCELLENT_THRESHOLD = 0.5  # degrees
        GOOD_THRESHOLD = 1.0
        ACCEPTABLE_THRESHOLD = 2.0

        abs_rotation = abs(rotation_deg)

        if abs_rotation < EXCELLENT_THRESHOLD:
            status = "EXCELLENT"
            severity = "ok"
            message = "No rotation difference detected"
        elif abs_rotation < GOOD_THRESHOLD:
            status = "GOOD"
            severity = "ok"
            message = "Minimal rotation difference"
        elif abs_rotation < ACCEPTABLE_THRESHOLD:
            status = "ACCEPTABLE"
            severity = "warning"
            message = f"Slight rotation detected ({rotation_deg:.1f}°)"
        else:
            status = "POOR"
            severity = "error"
            direction = "clockwise" if rotation_deg > 0 else "counter-clockwise"
            message = f"Significant rotation ({rotation_deg:.1f}° {direction})"

        return {
            "status": status,
            "severity": severity,
            "message": message,
            "rotation_deg": float(rotation_deg),
            "recommendation": "Adjust camera rotation to match" if severity == "error" else None,
        }

    except Exception as e:
        return {
            "status": "UNKNOWN",
            "severity": "warning",
            "message": f"Could not analyze rotation: {e}",
            "rotation_deg": 0.0,
        }


def print_alignment_report(vertical: dict, horizontal: dict, rotation: dict, num_features: int) -> None:
    """Print formatted alignment report."""

    # Header
    print("\n" + "=" * 70)
    print("CAMERA ALIGNMENT REPORT")
    print("=" * 70)

    print(f"\nFeatures matched: {num_features}")

    # Vertical alignment
    print("\n--- VERTICAL ALIGNMENT (Height) ---")
    severity_symbol = {
        "ok": "[OK]",
        "warning": "[!]",
        "error": "[X]",
    }

    symbol = severity_symbol.get(vertical["severity"], "[?]")
    print(f"{symbol} Status: {vertical['status']}")
    print(f"    {vertical['message']}")
    print(f"    Mean vertical disparity: {vertical['mean_vertical_disparity_px']:.2f} px")
    print(f"    Max vertical disparity: {vertical['max_vertical_disparity_px']:.2f} px")
    if vertical["recommendation"]:
        print(f"    → {vertical['recommendation']}")

    # Horizontal alignment
    print("\n--- HORIZONTAL ALIGNMENT (Convergence) ---")
    symbol = severity_symbol.get(horizontal["severity"], "[?]")
    print(f"{symbol} Status: {horizontal['status']}")
    print(f"    {horizontal['message']}")
    print(f"    Disparity std dev: {horizontal['std_horizontal_disparity_px']:.2f} px")
    print(f"    Position correlation: {horizontal['position_disparity_correlation']:.3f}")
    if horizontal["recommendation"]:
        print(f"    → {horizontal['recommendation']}")

    # Rotation
    print("\n--- ROTATION ALIGNMENT (Roll) ---")
    symbol = severity_symbol.get(rotation["severity"], "[?]")
    print(f"{symbol} Status: {rotation['status']}")
    print(f"    {rotation['message']}")
    print(f"    Rotation difference: {rotation['rotation_deg']:.2f}°")
    if rotation.get("recommendation"):
        print(f"    → {rotation['recommendation']}")

    # Overall assessment
    print("\n--- OVERALL ASSESSMENT ---")

    all_severities = [vertical["severity"], horizontal["severity"], rotation["severity"]]

    if all(s == "ok" for s in all_severities):
        print("[OK] Cameras are well aligned!")
        print("     You can proceed with checkerboard calibration.")
        overall_pass = True
    elif any(s == "error" for s in all_severities):
        print("[X] Camera alignment issues detected!")
        print("    Fix the issues above before attempting calibration.")
        print("    High calibration errors (>5px) are expected with this alignment.")
        overall_pass = False
    else:
        print("[!] Camera alignment acceptable but not optimal.")
        print("    Consider improving alignment for best calibration results.")
        print("    Expected calibration error: 1-5 px")
        overall_pass = True

    print("=" * 70 + "\n")

    return overall_pass


def main():
    # Print header immediately so user knows script started
    print("\n" + "="*70)
    print("CAMERA ALIGNMENT CHECKER")
    print("="*70 + "\n")

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
        """
    )
    parser.add_argument("--left", type=Path, help="Path to left camera image")
    parser.add_argument("--right", type=Path, help="Path to right camera image")
    parser.add_argument("--capture", action="store_true", help="Capture frames from cameras directly")
    parser.add_argument("--backend", default="opencv", choices=["opencv", "uvc"], help="Camera backend for capture")
    parser.add_argument("--left-camera", default="0", help="Left camera identifier (default: 0)")
    parser.add_argument("--right-camera", default="1", help="Right camera identifier (default: 1)")
    parser.add_argument("--save", action="store_true", help="Save captured frames to alignment_check_left.png and alignment_check_right.png")

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
        print("\n" + "="*70)
        print("Analysis complete!")
        print("="*70)

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

    except ValueError as e:
        print(f"\n{'='*70}")
        print(f"ERROR: {e}")
        print("="*70)
        print("\nTips:")
        print("  - Point cameras at textured scene (posters, furniture, etc.)")
        print("  - Avoid blank walls or low-contrast surfaces")
        print("  - Ensure good lighting")
        print("  - Make sure camera indices are correct (--left-camera 0 --right-camera 1)")
        print("\n" + "="*70)

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
        print("="*70)
        import traceback
        traceback.print_exc()
        print("="*70)

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
        except:
            pass
        print("\nInterrupted by user")
        input("Press ENTER to exit...")
        sys.exit(0)
    except SystemExit:
        # Don't catch sys.exit() calls
        raise
    except Exception as e:
        print("\n" + "="*70)
        print("FATAL ERROR - Script failed to run")
        print("="*70)
        print(f"\nError: {e}\n")
        import traceback
        traceback.print_exc()
        print("\n" + "="*70)
        print("\nIf this error persists, please report it with the error message above.")
        print("="*70)

        # Restore console output
        try:
            sys.stdout = _original_stdout
            sys.stderr = _original_stderr
            log_file.close()

            # Print to console
            print("\n" + "="*70)
            print("FATAL ERROR - Script failed to run")
            print("="*70)
            print(f"\nError: {e}\n")
            traceback.print_exc()
            print(f"\nFull error log saved to: {log_file_path.absolute()}")
            print("="*70)
        except:
            pass  # If we can't restore output, at least log file has the error

        input("\nPress ENTER to exit...")
        sys.exit(1)

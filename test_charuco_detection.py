#!/usr/bin/env python3
"""Test ChArUco detection to verify dictionary and pattern size.

This script helps verify which ArUco dictionary your printed board uses
and confirms the pattern size detection is working correctly.

Usage:
    python test_charuco_detection.py              # Use webcam 0
    python test_charuco_detection.py --camera 1   # Use specific camera
    python test_charuco_detection.py --image board.jpg  # Test with image file
"""

import argparse
import sys
import cv2
import numpy as np


def test_all_dictionaries(image: np.ndarray):
    """Test all ArUco dictionaries and report which ones work.

    Args:
        image: Camera frame or loaded image

    Returns:
        List of (dict_name, marker_count, marker_ids) tuples
    """
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    DICTIONARIES = [
        ('DICT_6X6_250', cv2.aruco.DICT_6X6_250),
        ('DICT_5X5_250', cv2.aruco.DICT_5X5_250),
        ('DICT_4X4_250', cv2.aruco.DICT_4X4_250),
        ('DICT_6X6_100', cv2.aruco.DICT_6X6_100),
        ('DICT_5X5_100', cv2.aruco.DICT_5X5_100),
        ('DICT_4X4_100', cv2.aruco.DICT_4X4_100),
        ('DICT_4X4_50', cv2.aruco.DICT_4X4_50),
        ('DICT_ARUCO_ORIGINAL', cv2.aruco.DICT_ARUCO_ORIGINAL),
    ]

    results = []

    for dict_name, dict_id in DICTIONARIES:
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)

        try:
            # Try newer OpenCV API (4.7+)
            detector_params = cv2.aruco.DetectorParameters()
            detector_params.adaptiveThreshWinSizeMin = 3
            detector_params.adaptiveThreshWinSizeMax = 23
            detector_params.adaptiveThreshWinSizeStep = 10
            detector_params.adaptiveThreshConstant = 7
            detector_params.minMarkerPerimeterRate = 0.03
            detector_params.maxMarkerPerimeterRate = 4.0
            detector_params.polygonalApproxAccuracyRate = 0.05
            detector_params.minCornerDistanceRate = 0.05
            detector_params.minDistanceToBorder = 3
            detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
            detector_params.cornerRefinementWinSize = 5
            detector_params.cornerRefinementMaxIterations = 30
            detector_params.cornerRefinementMinAccuracy = 0.1

            detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
            marker_corners, marker_ids, rejected = detector.detectMarkers(gray)
        except AttributeError:
            # Fall back to older API
            detector_params = cv2.aruco.DetectorParameters_create()
            detector_params.adaptiveThreshWinSizeMin = 3
            detector_params.adaptiveThreshWinSizeMax = 23
            detector_params.adaptiveThreshWinSizeStep = 10
            detector_params.adaptiveThreshConstant = 7
            detector_params.minMarkerPerimeterRate = 0.03
            detector_params.maxMarkerPerimeterRate = 4.0
            detector_params.polygonalApproxAccuracyRate = 0.05
            detector_params.minCornerDistanceRate = 0.05
            detector_params.minDistanceToBorder = 3
            detector_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
            detector_params.cornerRefinementWinSize = 5
            detector_params.cornerRefinementMaxIterations = 30
            detector_params.cornerRefinementMinAccuracy = 0.1

            marker_corners, marker_ids, rejected = cv2.aruco.detectMarkers(
                gray, aruco_dict, parameters=detector_params
            )

        num_found = len(marker_ids) if marker_ids is not None else 0
        results.append((dict_name, num_found, marker_ids))

    return results


def infer_pattern_from_markers(marker_ids: np.ndarray):
    """Infer ChArUco pattern size from detected marker IDs.

    ChArUco boards have (cols-1)*(rows-1) markers numbered sequentially.
    """
    if marker_ids is None or len(marker_ids) == 0:
        return None

    max_id = int(np.max(marker_ids))
    num_markers = max_id + 1

    # Common ChArUco patterns
    COMMON_PATTERNS = [
        (5, 6, 20),   # 5x6, 20mm (4x5=20 markers)
        (5, 6, 30),   # 5x6, 30mm (4x5=20 markers)
        (5, 7, 30),   # 5x7, 30mm (4x6=24 markers)
        (7, 5, 25),   # 7x5, 25mm (6x4=24 markers)
        (6, 8, 25),   # 6x8, 25mm (5x7=35 markers)
    ]

    for cols, rows, square_mm in COMMON_PATTERNS:
        expected_markers = (cols - 1) * (rows - 1)
        if num_markers == expected_markers:
            return (cols, rows, square_mm)

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Test ChArUco detection and identify dictionary/pattern"
    )
    parser.add_argument(
        '--camera',
        type=int,
        default=0,
        help='Camera index (default: 0)'
    )
    parser.add_argument(
        '--image',
        type=str,
        help='Test with image file instead of camera'
    )

    args = parser.parse_args()

    if args.image:
        # Load image from file
        image = cv2.imread(args.image)
        if image is None:
            print(f"Error: Could not load image '{args.image}'", file=sys.stderr)
            sys.exit(1)

        print(f"Testing with image: {args.image}")
        print("=" * 70)

        results = test_all_dictionaries(image)

        # Print results
        print("\nDictionary Detection Results:")
        print("-" * 70)
        for dict_name, count, marker_ids in sorted(results, key=lambda x: x[1], reverse=True):
            if count > 0:
                pattern = infer_pattern_from_markers(marker_ids)
                pattern_str = f" -> Pattern: {pattern[0]}x{pattern[1]}, ~{pattern[2]}mm" if pattern else ""
                print(f"  {dict_name:20s} : {count:2d} markers detected{pattern_str}")
            else:
                print(f"  {dict_name:20s} : 0 markers")

        print("\n" + "=" * 70)
        best = max(results, key=lambda x: x[1])
        if best[1] > 0:
            print(f"BEST MATCH: {best[0]} with {best[1]} markers")
            pattern = infer_pattern_from_markers(best[2])
            if pattern:
                print(f"Detected pattern: {pattern[0]} columns x {pattern[1]} rows")
                print(f"Estimated square size: {pattern[2]} mm")
        else:
            print("ERROR: No markers detected with any dictionary!")
            print("\nTroubleshooting:")
            print("  - Ensure board is well-lit and in focus")
            print("  - Check print quality (no smudges, clear black/white)")
            print("  - Verify board was printed at 100% scale")

    else:
        # Use camera
        cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            print(f"Error: Could not open camera {args.camera}", file=sys.stderr)
            sys.exit(1)

        print(f"Opening camera {args.camera}...")
        print("Hold ChArUco board in view. Press SPACE to test, Q to quit.")
        print("=" * 70)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Show preview
            cv2.imshow('ChArUco Test - Press SPACE to test, Q to quit', frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):
                # Test all dictionaries
                print("\nTesting all dictionaries...")
                print("-" * 70)

                results = test_all_dictionaries(frame)

                for dict_name, count, marker_ids in sorted(results, key=lambda x: x[1], reverse=True):
                    if count > 0:
                        pattern = infer_pattern_from_markers(marker_ids)
                        pattern_str = f" -> Pattern: {pattern[0]}x{pattern[1]}, ~{pattern[2]}mm" if pattern else ""
                        print(f"  {dict_name:20s} : {count:2d} markers{pattern_str}")

                best = max(results, key=lambda x: x[1])
                if best[1] > 0:
                    print(f"\nBEST: {best[0]} with {best[1]} markers")
                    pattern = infer_pattern_from_markers(best[2])
                    if pattern:
                        print(f"Pattern: {pattern[0]}x{pattern[1]}, ~{pattern[2]}mm squares")
                else:
                    print("\nNo markers detected! Adjust lighting/focus.")
                print("-" * 70)

        cap.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

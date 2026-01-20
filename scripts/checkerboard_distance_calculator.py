#!/usr/bin/env python3
"""Calculate optimal checkerboard detection distances and sizes.

Usage:
    python scripts/checkerboard_distance_calculator.py
"""

def calculate_max_distance(focal_length_px: float, square_size_mm: float, min_pixels_per_square: float = 20) -> float:
    """Calculate maximum distance for reliable checkerboard detection.

    Args:
        focal_length_px: Camera focal length in pixels (typically 1200 for 720p)
        square_size_mm: Checkerboard square size in millimeters
        min_pixels_per_square: Minimum pixels needed per square (default 20)

    Returns:
        Maximum distance in millimeters
    """
    return (focal_length_px * square_size_mm) / min_pixels_per_square


def calculate_required_square_size(focal_length_px: float, distance_mm: float, min_pixels_per_square: float = 20) -> float:
    """Calculate required square size for given distance.

    Args:
        focal_length_px: Camera focal length in pixels
        distance_mm: Target calibration distance in millimeters
        min_pixels_per_square: Minimum pixels needed per square (default 20)

    Returns:
        Required square size in millimeters
    """
    return (min_pixels_per_square * distance_mm) / focal_length_px


def calculate_pixels_per_square(focal_length_px: float, square_size_mm: float, distance_mm: float) -> float:
    """Calculate actual pixels per square at given distance.

    Args:
        focal_length_px: Camera focal length in pixels
        square_size_mm: Checkerboard square size in millimeters
        distance_mm: Distance to checkerboard in millimeters

    Returns:
        Pixels per square
    """
    return (focal_length_px * square_size_mm) / distance_mm


def mm_to_inches(mm: float) -> float:
    return mm / 25.4


def mm_to_feet(mm: float) -> float:
    return mm / 304.8


def feet_to_mm(feet: float) -> float:
    return feet * 304.8


def inches_to_mm(inches: float) -> float:
    return inches * 25.4


if __name__ == "__main__":
    print("=" * 70)
    print("CHECKERBOARD DETECTION CALCULATOR")
    print("=" * 70)

    # User's current setup
    focal_length = 1200  # pixels (typical for 720p)
    square_size_mm = 30  # User's 30mm checkerboard
    target_distance_ft = 20  # User wants to calibrate at 20 ft

    target_distance_mm = feet_to_mm(target_distance_ft)

    print("\nYOUR CURRENT SETUP:")
    print(f"  Checkerboard square size: {square_size_mm}mm ({mm_to_inches(square_size_mm):.1f} inches)")
    print(f"  Target calibration distance: {target_distance_ft} ft ({target_distance_mm:.0f}mm)")
    print(f"  Camera focal length: {focal_length}px (typical for 720p)")

    # Calculate actual pixels per square
    pixels_per_square = calculate_pixels_per_square(focal_length, square_size_mm, target_distance_mm)

    print(f"\nDETECTION ANALYSIS:")
    print(f"  Pixels per square at {target_distance_ft} ft: {pixels_per_square:.1f} pixels")
    print(f"  Required for reliable detection: 15-20 pixels")

    if pixels_per_square >= 20:
        print(f"  [OK] GOOD - Detection should work reliably")
    elif pixels_per_square >= 15:
        print(f"  [!] MARGINAL - Detection may be inconsistent")
    elif pixels_per_square >= 10:
        print(f"  [X] POOR - Detection will be very difficult")
    else:
        print(f"  [X] IMPOSSIBLE - Squares too small to detect")

    # Calculate max distance for current checkerboard
    max_distance_mm = calculate_max_distance(focal_length, square_size_mm, min_pixels_per_square=20)
    max_distance_ft = mm_to_feet(max_distance_mm)

    print(f"\nMAXIMUM DISTANCE FOR YOUR 30MM BOARD:")
    print(f"  Max distance (20 px/square): {max_distance_ft:.1f} ft ({max_distance_mm:.0f}mm)")
    print(f"  Max distance (15 px/square): {mm_to_feet(calculate_max_distance(focal_length, square_size_mm, 15)):.1f} ft")

    # Calculate required square size for target distance
    required_size_mm = calculate_required_square_size(focal_length, target_distance_mm, min_pixels_per_square=20)
    required_size_inches = mm_to_inches(required_size_mm)

    print(f"\nREQUIRED SQUARE SIZE FOR {target_distance_ft} FT:")
    print(f"  Required size (20 px/square): {required_size_mm:.0f}mm ({required_size_inches:.1f} inches)")
    print(f"  Required size (15 px/square): {calculate_required_square_size(focal_length, target_distance_mm, 15):.0f}mm ({mm_to_inches(calculate_required_square_size(focal_length, target_distance_mm, 15)):.1f} inches)")

    print(f"\nRECOMMENDATIONS:")
    print(f"  1. BEST: Use your 30mm board at {max_distance_ft:.0f} ft or closer")
    print(f"  2. Build larger board with {required_size_inches:.0f}\" squares for {target_distance_ft} ft")
    print(f"  3. Two-stage calibration:")
    print(f"     - Stage 1: Calibrate at {max_distance_ft:.0f} ft with 30mm board")
    print(f"     - Stage 2: Plate plane calibration at {target_distance_ft} ft")

    print("\n" + "=" * 70)
    print("DISTANCE TABLE FOR YOUR 30MM CHECKERBOARD:")
    print("=" * 70)
    print(f"{'Distance (ft)':<15} {'Pixels/Square':<20} {'Detection Quality':<30}")
    print("-" * 70)

    for dist_ft in [3, 6, 8, 10, 12, 15, 18, 20, 25, 30]:
        dist_mm = feet_to_mm(dist_ft)
        pps = calculate_pixels_per_square(focal_length, square_size_mm, dist_mm)

        if pps >= 20:
            quality = "[OK] Excellent"
        elif pps >= 15:
            quality = "[!] Marginal"
        elif pps >= 10:
            quality = "[X] Poor"
        else:
            quality = "[X] Won't work"

        print(f"{dist_ft:<15} {pps:<20.1f} {quality:<30}")

    print("\n" + "=" * 70)
    print("SQUARE SIZE REQUIREMENTS BY DISTANCE:")
    print("=" * 70)
    print(f"{'Distance (ft)':<15} {'Req Size (mm)':<20} {'Req Size (inches)':<20}")
    print("-" * 70)

    for dist_ft in [6, 10, 15, 20, 25, 30]:
        dist_mm = feet_to_mm(dist_ft)
        req_mm = calculate_required_square_size(focal_length, dist_mm, 20)
        req_in = mm_to_inches(req_mm)
        print(f"{dist_ft:<15} {req_mm:<20.0f} {req_in:<20.1f}")

    print("\n")

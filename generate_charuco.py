#!/usr/bin/env python3
"""Generate ChArUco calibration board for stereo camera calibration.

This script generates a ChArUco (Checkerboard + ArUco) pattern that can be
printed and used for stereo camera calibration. ChArUco boards are superior
to plain checkerboards because they:
- Work with partial occlusion (don't need to see the entire board)
- Auto-detect board size and orientation
- More robust to lighting conditions
- Can be used at varying distances from cameras

Usage:
    python generate_charuco.py                  # Generate default 5x6 board
    python generate_charuco.py --cols 7 --rows 5 --size 25 --output my_board.png
"""

import argparse
import sys

import cv2


def generate_charuco_board(
    cols: int = 5,
    rows: int = 6,
    square_mm: float = 30.0,
    output: str = "charuco_board.png",
    paper_size: str = "letter",
    dict_name: str = "6x6_250"
) -> None:
    """Generate ChArUco board for calibration.

    Args:
        cols: Number of columns (default: 5)
        rows: Number of rows (default: 6)
        square_mm: Square size in millimeters (default: 30)
        output: Output filename (default: charuco_board.png)
        paper_size: Paper size - 'letter' or 'a4' (default: letter)
        dict_name: ArUco dictionary name (default: 6x6_250)
    """
    # ArUco dictionary mapping
    DICT_MAP = {
        "6x6_250": cv2.aruco.DICT_6X6_250,
        "5x5_250": cv2.aruco.DICT_5X5_250,
        "4x4_250": cv2.aruco.DICT_4X4_250,
        "6x6_100": cv2.aruco.DICT_6X6_100,
        "5x5_100": cv2.aruco.DICT_5X5_100,
        "4x4_100": cv2.aruco.DICT_4X4_100,
        "4x4_50": cv2.aruco.DICT_4X4_50,
    }

    if dict_name.lower() not in DICT_MAP:
        print(f"Error: Unknown dictionary '{dict_name}'", file=sys.stderr)
        print(f"Available: {', '.join(DICT_MAP.keys())}", file=sys.stderr)
        sys.exit(1)

    dictionary = cv2.aruco.getPredefinedDictionary(DICT_MAP[dict_name.lower()])

    # Marker size is typically 73% of square size (prevents marker overlap)
    marker_mm = square_mm * 0.73

    # Create board (sizes in meters for OpenCV)
    board = cv2.aruco.CharucoBoard(
        (cols, rows),
        square_mm / 1000,  # Convert mm to meters
        marker_mm / 1000,
        dictionary
    )

    # Paper dimensions at 300 DPI
    if paper_size.lower() == "a4":
        # A4: 210mm × 297mm = 2480 × 3508 pixels at 300 DPI
        img_size = (2480, 3508)
        paper_name = "A4 (210mm × 297mm)"
    else:
        # US Letter: 8.5" × 11" = 2550 × 3300 pixels at 300 DPI
        img_size = (2550, 3300)
        paper_name = "US Letter (8.5\" × 11\")"

    # Generate image with margin
    margin = 100  # pixels
    img = board.generateImage(img_size, marginSize=margin, borderBits=1)

    # Save
    cv2.imwrite(output, img)

    # Print success message with instructions
    # Use ASCII-safe characters for Windows console compatibility
    print("=" * 70)
    print(f"[SUCCESS] ChArUco Calibration Board Generated!")
    print("=" * 70)
    print()
    print(f"File: {output}")
    print(f"Pattern: {cols} columns x {rows} rows")
    print(f"Square size: {square_mm} mm")
    print(f"Marker size: {marker_mm:.1f} mm")
    print(f"Total markers: {(cols - 1) * (rows - 1)}")
    print(f"Dictionary: {dict_name.upper()}")
    print(f"Paper size: {paper_name}")
    print()
    print("=" * 70)
    print("PRINTING INSTRUCTIONS (IMPORTANT!)")
    print("=" * 70)
    print()
    print("1. Open the generated PNG file in an image viewer")
    print()
    print("2. Print Settings:")
    print("   [X] Scale: 100% (CRITICAL - NO 'Fit to Page'!)")
    print("   [X] Quality: High/Best quality")
    print("   [X] Paper: Thick paper or cardstock")
    print("   [X] Finish: Matte (reduces glare)")
    print("   [X] Color: Black & White is fine")
    print()
    print("3. Mounting:")
    print("   - Mount on rigid surface (foam board, cardboard, wood)")
    print("   - Keep it perfectly FLAT (warping ruins calibration)")
    print("   - Optional: Laminate for durability")
    print()
    print("4. Verification:")
    print(f"   - Measure actual square size with a ruler")
    print(f"   - Should be {square_mm} mm +/- 0.5 mm")
    print(f"   - If different, adjust 'Square Size' in Advanced Settings")
    print()
    print("=" * 70)
    print("USING THE BOARD FOR CALIBRATION")
    print("=" * 70)
    print()
    print("1. Launch PitchTracker Setup Wizard")
    print("2. Complete Camera Setup (Step 1)")
    print("3. In Calibration Step (Step 2):")
    print("   - Hold board in view of both cameras")
    print("   - Wait for 'READY' status on both cameras")
    print("   - Click 'Capture Pose'")
    print("   - Move board to different positions/angles/depths")
    print("   - Capture 10-15 different poses")
    print("   - Click 'Run Calibration'")
    print()
    print("Tips:")
    print("   - Cover full camera view (near/far/left/right/top/bottom)")
    print("   - Tilt board at various angles (0, 30, 45 degrees)")
    print("   - Board can be partially out of frame - ChArUco handles it!")
    print("   - More varied poses = better calibration")
    print()
    print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate ChArUco calibration board for stereo camera calibration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate default 5x6 board with 30mm squares (6x6_250 dictionary)
  python generate_charuco.py

  # Generate board with 4x4 dictionary (smaller markers)
  python generate_charuco.py --dict 4x4_250

  # Generate 5x6 board with 20mm squares and 6x6 dictionary
  python generate_charuco.py --cols 5 --rows 6 --size 20 --dict 6x6_250

  # Generate larger 7x5 board with 25mm squares
  python generate_charuco.py --cols 7 --rows 5 --size 25

  # Generate A4 paper format
  python generate_charuco.py --paper a4

Available dictionaries:
  6x6_250, 5x5_250, 4x4_250 (recommended)
  6x6_100, 5x5_100, 4x4_100, 4x4_50 (less common)
        """
    )

    parser.add_argument(
        "--cols",
        type=int,
        default=5,
        help="Number of columns (default: 5)"
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=6,
        help="Number of rows (default: 6)"
    )
    parser.add_argument(
        "--size",
        type=float,
        default=30.0,
        help="Square size in millimeters (default: 30.0)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="charuco_board.png",
        help="Output filename (default: charuco_board.png)"
    )
    parser.add_argument(
        "--paper",
        type=str,
        choices=["letter", "a4"],
        default="letter",
        help="Paper size: 'letter' (8.5x11) or 'a4' (210x297mm) (default: letter)"
    )
    parser.add_argument(
        "--dict",
        type=str,
        default="6x6_250",
        help="ArUco dictionary: 6x6_250, 5x5_250, 4x4_250, 6x6_100, 5x5_100, 4x4_100, 4x4_50 (default: 6x6_250)"
    )

    args = parser.parse_args()

    # Validate inputs
    if args.cols < 3 or args.rows < 3:
        print("Error: Columns and rows must be at least 3", file=sys.stderr)
        sys.exit(1)

    if args.size <= 0:
        print("Error: Square size must be positive", file=sys.stderr)
        sys.exit(1)

    # Generate board
    try:
        generate_charuco_board(
            cols=args.cols,
            rows=args.rows,
            square_mm=args.size,
            output=args.output,
            paper_size=args.paper,
            dict_name=args.dict
        )
    except Exception as e:
        print(f"Error generating board: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Generate ChArUco board optimized for stereo calibration.

ChArUco boards combine checkerboard patterns with ArUco markers for
robust, accurate calibration with partial occlusion tolerance.
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def generate_charuco_board(
    output_path: Path,
    squares_x: int = 9,
    squares_y: int = 6,
    square_length: float = 30.0,  # mm
    marker_length: float = 22.5,  # mm (75% of square)
    width_mm: float = 210,  # A4 width
    height_mm: float = 297,  # A4 height
    dpi: int = 300,
    dictionary_id: int = cv2.aruco.DICT_6X6_250
) -> None:
    """Generate ChArUco board image for printing.

    Args:
        output_path: Where to save the board image
        squares_x: Number of squares in X direction
        squares_y: Number of squares in Y direction
        square_length: Length of each square in mm
        marker_length: Length of ArUco marker in mm (should be < square_length)
        width_mm: Paper width in mm
        height_mm: Paper height in mm
        dpi: Dots per inch for print quality
        dictionary_id: ArUco dictionary to use
    """
    # Convert mm to pixels
    width_px = int(width_mm / 25.4 * dpi)
    height_px = int(height_mm / 25.4 * dpi)

    # Get ArUco dictionary
    aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_id)

    # Create ChArUco board
    # Note: OpenCV 4.7+ uses different API
    try:
        # Try newer API first (OpenCV 4.7+)
        board = cv2.aruco.CharucoBoard(
            (squares_x, squares_y),
            square_length,
            marker_length,
            aruco_dict
        )
    except (AttributeError, TypeError):
        # Fall back to older API
        board = cv2.aruco.CharucoBoard_create(
            squares_x,
            squares_y,
            square_length,
            marker_length,
            aruco_dict
        )

    # Calculate board dimensions in pixels
    board_width_mm = squares_x * square_length
    board_height_mm = squares_y * square_length
    board_width_px = int(board_width_mm / 25.4 * dpi)
    board_height_px = int(board_height_mm / 25.4 * dpi)

    # Generate board image
    board_img = board.generateImage((board_width_px, board_height_px), marginSize=0, borderBits=1)

    # Create white background for full page
    full_page = np.ones((height_px, width_px), dtype=np.uint8) * 255

    # Calculate available space for board (leave margins)
    available_width = int(width_px * 0.9)  # 90% of page width
    available_height = int(height_px * 0.7)  # 70% of page height (leave space for title and instructions)

    # Scale board if necessary to fit on page
    scale_x = available_width / board_width_px
    scale_y = available_height / board_height_px
    scale = min(scale_x, scale_y, 1.0)  # Don't scale up, only down

    if scale < 1.0:
        # Need to scale down
        new_width = int(board_width_px * scale)
        new_height = int(board_height_px * scale)
        board_img = cv2.resize(board_img, (new_width, new_height), interpolation=cv2.INTER_AREA)
        board_width_px = new_width
        board_height_px = new_height

    # Calculate position to center the board
    x_offset = (width_px - board_width_px) // 2
    y_offset = int(height_px * 0.15)  # Leave space at top for title

    # Ensure board fits on page
    if y_offset + board_height_px > height_px - int(height_px * 0.15):
        y_offset = (height_px - board_height_px) // 2

    # Place board on page
    full_page[y_offset:y_offset+board_height_px, x_offset:x_offset+board_width_px] = board_img

    # Add title at top
    title_y = int(height_px * 0.08)
    cv2.putText(
        full_page,
        "PitchTracker ChArUco Calibration Board",
        (int(width_px * 0.12), title_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.8,
        0,
        4
    )

    # Add board specifications
    specs = [
        f"Squares: {squares_x}x{squares_y}  |  Square: {square_length}mm  |  Marker: {marker_length}mm",
        f"Dictionary: DICT_6X6_250"
    ]
    spec_y = title_y + 80
    for i, spec in enumerate(specs):
        cv2.putText(
            full_page,
            spec,
            (int(width_px * 0.15), spec_y + i * 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            0,
            2
        )

    # Add instructions at bottom
    instructions = [
        "INSTRUCTIONS:",
        "1. Print this page at 100% scale (no fit-to-page)",
        "2. Mount on rigid flat surface (cardboard/foam board)",
        "3. Measure one square to verify print scale is correct",
        "4. Place in overlapping camera view for calibration",
        "5. Ensure good even lighting (no glare or shadows)",
        "6. Board can be partially visible - ChArUco is robust to occlusion"
    ]

    instruction_y = y_offset + board_height_px + int(height_px * 0.03)
    if instruction_y + len(instructions) * 35 > height_px:
        instruction_y = height_px - len(instructions) * 35 - 50

    for i, instruction in enumerate(instructions):
        cv2.putText(
            full_page,
            instruction,
            (int(width_px * 0.08), instruction_y + i * 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            0,
            2
        )

    # Save image
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), full_page)

    print(f"OK: ChArUco board generated: {output_path}")
    print(f"  Paper size: {width_mm}mm x {height_mm}mm ({width_px}x{height_px} px @ {dpi} DPI)")
    print(f"  Board size: {squares_x}x{squares_y} squares ({board_width_mm:.1f}mm x {board_height_mm:.1f}mm)")
    print(f"  Square size: {square_length}mm")
    print(f"  Marker size: {marker_length}mm")
    print(f"  Print at 100% scale - measure a square to verify!")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate ChArUco calibration board for stereo camera calibration"
    )

    parser.add_argument(
        '--output',
        default='alignment_checks/charuco_board.png',
        help='Output path for board image (default: alignment_checks/charuco_board.png)'
    )

    parser.add_argument(
        '--squares-x',
        type=int,
        default=9,
        help='Number of squares in X direction (default: 9)'
    )

    parser.add_argument(
        '--squares-y',
        type=int,
        default=6,
        help='Number of squares in Y direction (default: 6)'
    )

    parser.add_argument(
        '--square-mm',
        type=float,
        default=30.0,
        help='Square size in mm (default: 30.0)'
    )

    parser.add_argument(
        '--marker-mm',
        type=float,
        default=22.5,
        help='Marker size in mm (default: 22.5, should be < square-mm)'
    )

    parser.add_argument(
        '--width-mm',
        type=float,
        default=210,
        help='Paper width in mm (default: 210 for A4)'
    )

    parser.add_argument(
        '--height-mm',
        type=float,
        default=297,
        help='Paper height in mm (default: 297 for A4)'
    )

    parser.add_argument(
        '--dpi',
        type=int,
        default=300,
        help='Print resolution in DPI (default: 300)'
    )

    args = parser.parse_args()

    # Validate marker size
    if args.marker_mm >= args.square_mm:
        print(f"Error: Marker size ({args.marker_mm}mm) must be smaller than square size ({args.square_mm}mm)")
        print(f"Recommended: marker size = 0.75 × square size = {args.square_mm * 0.75}mm")
        return 1

    try:
        generate_charuco_board(
            Path(args.output),
            squares_x=args.squares_x,
            squares_y=args.squares_y,
            square_length=args.square_mm,
            marker_length=args.marker_mm,
            width_mm=args.width_mm,
            height_mm=args.height_mm,
            dpi=args.dpi
        )
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

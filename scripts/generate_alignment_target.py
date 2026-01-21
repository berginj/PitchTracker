"""Generate custom alignment target optimized for feature matching.

Creates a printable PDF with asymmetric pattern optimized for ORB feature detection.
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def generate_alignment_target(
    output_path: Path,
    width_mm: float = 210,  # A4 width
    height_mm: float = 297,  # A4 height
    dpi: int = 300
) -> None:
    """Generate alignment target image.
    
    Args:
        output_path: Where to save the target image
        width_mm: Paper width in mm
        height_mm: Paper height in mm
        dpi: Dots per inch for print quality
    """
    # Convert mm to pixels
    width_px = int(width_mm / 25.4 * dpi)
    height_px = int(height_mm / 25.4 * dpi)
    
    # Create white background
    target = np.ones((height_px, width_px), dtype=np.uint8) * 255
    
    # Add title at top
    cv2.putText(
        target,
        "PitchTracker Alignment Target",
        (int(width_px * 0.15), int(height_px * 0.05)),
        cv2.FONT_HERSHEY_SIMPLEX,
        2.0,
        0,
        4
    )
    
    # Parameters for pattern generation
    margin = int(width_px * 0.1)
    pattern_width = width_px - 2 * margin
    pattern_height = int(height_px * 0.8)
    
    # Generate asymmetric checkerboard pattern (different sized squares)
    start_y = int(height_px * 0.1)
    
    # Large squares (good for coarse alignment)
    large_size = int(pattern_width / 8)
    for row in range(8):
        for col in range(8):
            if (row + col) % 2 == 0:
                x1 = margin + col * large_size
                y1 = start_y + row * large_size
                x2 = x1 + large_size
                y2 = y1 + large_size
                cv2.rectangle(target, (x1, y1), (x2, y2), 0, -1)
    
    # Add corner markers (circles) for orientation
    marker_radius = int(width_px * 0.02)
    cv2.circle(target, (margin, start_y), marker_radius, 0, -1)
    cv2.circle(target, (width_px - margin, start_y), marker_radius * 2, 0, -1)
    cv2.circle(target, (margin, start_y + 8 * large_size), marker_radius * 3, 0, -1)
    
    # Add random asymmetric features for robust feature matching
    np.random.seed(42)  # Reproducible
    num_features = 50
    for _ in range(num_features):
        x = np.random.randint(margin, width_px - margin)
        y = np.random.randint(start_y, start_y + 8 * large_size)
        
        # Random shape: circle, square, or triangle
        shape = np.random.choice(['circle', 'square', 'triangle'])
        size = np.random.randint(10, 30)
        
        if shape == 'circle':
            cv2.circle(target, (x, y), size, 128, -1)
        elif shape == 'square':
            cv2.rectangle(target, (x - size, y - size), (x + size, y + size), 128, -1)
        else:  # triangle
            pts = np.array([
                [x, y - size],
                [x - size, y + size],
                [x + size, y + size]
            ], dtype=np.int32)
            cv2.fillPoly(target, [pts], 128)
    
    # Add instructions at bottom
    instructions = [
        "INSTRUCTIONS:",
        "1. Print this page at 100% scale (no fit-to-page)",
        "2. Mount on rigid surface (cardboard/foam board)",
        "3. Place in overlapping camera view",
        "4. Ensure good lighting (no glare or shadows)",
        "5. Run alignment check in PitchTracker"
    ]
    
    instruction_y = start_y + 8 * large_size + int(height_px * 0.05)
    for i, instruction in enumerate(instructions):
        cv2.putText(
            target,
            instruction,
            (margin, instruction_y + i * 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            0,
            2
        )
    
    # Save image
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), target)
    
    print(f"✓ Alignment target generated: {output_path}")
    print(f"  Dimensions: {width_mm}mm x {height_mm}mm ({width_px}x{height_px} px @ {dpi} DPI)")
    print(f"  Print at 100% scale for accurate results")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate alignment target for camera alignment checks"
    )
    
    parser.add_argument(
        '--output',
        default='alignment_checks/alignment_target.png',
        help='Output path for target image (default: alignment_checks/alignment_target.png)'
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
    
    try:
        generate_alignment_target(
            Path(args.output),
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

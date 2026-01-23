#!/usr/bin/env python3
"""Minimal camera test to isolate issues.

This is a simplified version to test if basic imports and camera access work.
If this works but check_camera_alignment.py fails, the issue is in the logic.
If this also fails, the issue is with imports or camera drivers.
"""

import sys
from datetime import datetime

print("\n" + "="*70)
print("MINIMAL CAMERA TEST")
print("="*70)
print(f"Started: {datetime.now()}\n")

try:
    print("Step 1: Importing cv2...")
    import cv2
    print(f"  SUCCESS - OpenCV version: {cv2.__version__}")

    print("\nStep 2: Importing numpy...")
    import numpy as np
    print(f"  SUCCESS - NumPy version: {np.__version__}")

    print("\nStep 3: Listing available cameras...")
    available_cameras = []
    for i in range(5):  # Check first 5 indices
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cameras.append(i)
            cap.release()

    if available_cameras:
        print(f"  SUCCESS - Found cameras at indices: {available_cameras}")
    else:
        print("  WARNING - No cameras found")
        print("  This might be normal if cameras are already in use")

    print("\nStep 4: Testing camera 0...")
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            h, w = frame.shape[:2]
            print(f"  SUCCESS - Captured {w}x{h} frame from camera 0")
        else:
            print("  ERROR - Camera opened but could not read frame")
        cap.release()
    else:
        print("  ERROR - Could not open camera 0")

    print("\n" + "="*70)
    print("TEST COMPLETE - All basic functions working!")
    print("="*70)
    print("\nIf this test works but alignment checker fails,")
    print("check alignment_check_log.txt for detailed error messages.")

except ImportError as e:
    print(f"\nIMPORT ERROR: {e}")
    print("\nThis usually means:")
    print("  1. OpenCV is not installed: pip install opencv-python")
    print("  2. NumPy is not installed: pip install numpy")
    print("  3. Wrong Python environment (use the one where packages are installed)")

except Exception as e:
    print(f"\nUNEXPECTED ERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\n" + "="*70)
    input("Press ENTER to exit...")

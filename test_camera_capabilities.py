#!/usr/bin/env python
"""Camera Capability Testing Script

This script tests what resolutions and frame rates your cameras actually support.
Run this before attempting to use higher resolutions in the coaching app.

Usage:
    python test_camera_capabilities.py

Results are saved to: camera_tests/capability_report.txt
"""

import sys
import time
from pathlib import Path

import cv2
import psutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_camera_modes(camera_index: int, backend=cv2.CAP_DSHOW):
    """Test which modes a camera supports.

    Args:
        camera_index: Camera index to test (0, 1, 2, etc.)
        backend: OpenCV backend to use (CAP_DSHOW or CAP_MSMF)

    Returns:
        List of supported (width, height, fps) tuples
    """
    backend_name = "DSHOW" if backend == cv2.CAP_DSHOW else "MSMF"
    print(f"\n=== Testing Camera {camera_index} with {backend_name} ===\n")

    test_modes = [
        (640, 480, 15),
        (640, 480, 30),
        (640, 480, 60),
        (800, 600, 30),
        (1280, 720, 15),
        (1280, 720, 30),
        (1280, 720, 60),
        (1920, 1080, 15),
        (1920, 1080, 30),
        (1920, 1080, 60),
    ]

    supported = []

    try:
        cap = cv2.VideoCapture(camera_index, backend)
        if not cap.isOpened():
            print(f"❌ Failed to open camera {camera_index}")
            return []

        print(f"Testing {len(test_modes)} modes...\n")

        for width, height, fps in test_modes:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)

            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(cap.get(cv2.CAP_PROP_FPS))

            # Test if we can actually read a frame
            ret, frame = cap.read()
            can_read = ret and frame is not None

            if actual_w == width and actual_h == height and actual_fps == fps and can_read:
                print(f"✅ {width}x{height}@{fps}fps - SUPPORTED")
                supported.append((width, height, fps))
            else:
                print(f"❌ {width}x{height}@{fps}fps - NOT SUPPORTED (got {actual_w}x{actual_h}@{actual_fps}fps, read={can_read})")

        cap.release()

        print(f"\nCamera {camera_index} supports {len(supported)}/{len(test_modes)} tested modes")

    except Exception as e:
        print(f"❌ Error testing camera {camera_index}: {e}")

    return supported


def test_memory_usage(camera_index: int, width: int, height: int, fps: int, duration_sec: int = 5, backend=cv2.CAP_DSHOW):
    """Test memory usage for a specific camera mode.

    Args:
        camera_index: Camera index to test
        width: Frame width
        height: Frame height
        fps: Target frame rate
        duration_sec: How long to run test
        backend: OpenCV backend

    Returns:
        Dict with memory usage statistics
    """
    process = psutil.Process()
    baseline_mb = process.memory_info().rss / 1024 / 1024

    print(f"\n=== Memory Test: {width}x{height}@{fps}fps for {duration_sec}s ===")
    print(f"Baseline memory: {baseline_mb:.1f} MB")

    try:
        cap = cv2.VideoCapture(camera_index, backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        # Verify mode was set
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if actual_w != width or actual_h != height:
            print(f"⚠️ Warning: Requested {width}x{height} but got {actual_w}x{actual_h}")

        # Capture frames
        start = time.time()
        frames_captured = 0
        frame_times = []

        while time.time() - start < duration_sec:
            frame_start = time.time()
            ret, frame = cap.read()
            frame_end = time.time()

            if ret:
                frames_captured += 1
                frame_times.append(frame_end - frame_start)

        elapsed = time.time() - start
        effective_fps = frames_captured / elapsed

        # Memory after capture
        peak_mb = process.memory_info().rss / 1024 / 1024
        delta_mb = peak_mb - baseline_mb

        cap.release()

        avg_frame_time_ms = sum(frame_times) / len(frame_times) * 1000 if frame_times else 0

        result = {
            'resolution': f'{width}x{height}@{fps}fps',
            'frames_captured': frames_captured,
            'effective_fps': effective_fps,
            'baseline_mb': baseline_mb,
            'peak_mb': peak_mb,
            'delta_mb': delta_mb,
            'avg_frame_time_ms': avg_frame_time_ms,
            'success': True
        }

        print(f"✅ Captured {frames_captured} frames in {elapsed:.1f}s")
        print(f"   Effective FPS: {effective_fps:.1f}")
        print(f"   Memory used: {delta_mb:.1f} MB (peak: {peak_mb:.1f} MB)")
        print(f"   Avg frame time: {avg_frame_time_ms:.2f} ms")

        return result

    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            'resolution': f'{width}x{height}@{fps}fps',
            'error': str(e),
            'success': False
        }


def test_dual_camera(width: int, height: int, fps: int, duration_sec: int = 10, backend=cv2.CAP_DSHOW):
    """Test both cameras simultaneously.

    Args:
        width: Frame width
        height: Frame height
        fps: Target frame rate
        duration_sec: Test duration
        backend: OpenCV backend

    Returns:
        Dict with dual-camera test results
    """
    print(f"\n=== Dual Camera Test: {width}x{height}@{fps}fps for {duration_sec}s ===")

    try:
        left_cap = cv2.VideoCapture(0, backend)
        right_cap = cv2.VideoCapture(1, backend)

        # Configure both cameras
        for cap in [left_cap, right_cap]:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)

        if not left_cap.isOpened() or not right_cap.isOpened():
            print("❌ Failed to open both cameras")
            return {'success': False, 'error': 'Failed to open cameras'}

        # Capture from both
        start = time.time()
        frames_left = 0
        frames_right = 0
        errors = 0

        print("Capturing...")

        while time.time() - start < duration_sec:
            ret_left, frame_left = left_cap.read()
            ret_right, frame_right = right_cap.read()

            if ret_left:
                frames_left += 1
            else:
                errors += 1

            if ret_right:
                frames_right += 1
            else:
                errors += 1

            # Small delay to prevent tight loop
            time.sleep(0.001)

        elapsed = time.time() - start

        left_cap.release()
        right_cap.release()

        result = {
            'resolution': f'{width}x{height}@{fps}fps',
            'frames_left': frames_left,
            'frames_right': frames_right,
            'errors': errors,
            'effective_fps_left': frames_left / elapsed,
            'effective_fps_right': frames_right / elapsed,
            'success': True
        }

        print(f"✅ Dual camera test complete")
        print(f"   Left: {frames_left} frames ({result['effective_fps_left']:.1f} fps)")
        print(f"   Right: {frames_right} frames ({result['effective_fps_right']:.1f} fps)")
        print(f"   Errors: {errors}")

        return result

    except Exception as e:
        print(f"❌ Error: {e}")
        return {'success': False, 'error': str(e)}


def main():
    """Run camera capability tests."""
    print("=" * 70)
    print("Camera Capability Testing")
    print("=" * 70)

    # Ask user how many cameras to test
    print("\nHow many cameras do you want to test? (default: 6 for cameras 0-5)")
    try:
        num_cameras = int(input("Enter number: ") or "6")
    except ValueError:
        num_cameras = 6
        print(f"Using default: {num_cameras} cameras")

    # Create output directory
    output_dir = Path("camera_tests")
    output_dir.mkdir(exist_ok=True)

    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("CAMERA CAPABILITY TEST REPORT")
    report_lines.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Testing cameras: 0 to {num_cameras - 1}")
    report_lines.append("=" * 70)

    # Test both backends
    for backend_name, backend in [("DirectShow", cv2.CAP_DSHOW), ("Media Foundation", cv2.CAP_MSMF)]:
        report_lines.append(f"\n\n{'='*70}")
        report_lines.append(f"Backend: {backend_name}")
        report_lines.append(f"{'='*70}")

        print(f"\n\n{'='*70}")
        print(f"Testing with {backend_name} backend")
        print(f"{'='*70}")

        # Store results for all cameras
        all_supported = {}

        # Test each camera
        for cam_idx in range(num_cameras):
            supported = test_camera_modes(cam_idx, backend)
            all_supported[cam_idx] = supported
            report_lines.append(f"\nCamera {cam_idx} Supported Modes ({len(supported)}):")
            for mode in supported:
                report_lines.append(f"  - {mode[0]}x{mode[1]}@{mode[2]}fps")

        # Find modes supported by ALL cameras
        if all_supported:
            common_modes = set(all_supported[0])
            for cam_idx in range(1, num_cameras):
                if cam_idx in all_supported:
                    common_modes &= set(all_supported[cam_idx])

            # Keep the existing dual-camera test for cameras 0 and 1
            supported_0 = all_supported.get(0, [])
            supported_1 = all_supported.get(1, [])

        # If both cameras support a mode, test memory and dual-camera
        common_modes = set(supported_0) & set(supported_1)
        report_lines.append(f"\nCommon Supported Modes ({len(common_modes)}):")

        for mode in sorted(common_modes):
            width, height, fps = mode
            report_lines.append(f"\n{width}x{height}@{fps}fps:")

            # Memory test on camera 0
            mem_result = test_memory_usage(0, width, height, fps, duration_sec=5, backend=backend)
            if mem_result['success']:
                report_lines.append(f"  Memory: {mem_result['delta_mb']:.1f} MB")
                report_lines.append(f"  Effective FPS: {mem_result['effective_fps']:.1f}")

            # Dual camera test
            dual_result = test_dual_camera(width, height, fps, duration_sec=5, backend=backend)
            if dual_result['success']:
                report_lines.append(f"  Dual Camera: LEFT={dual_result['effective_fps_left']:.1f}fps, RIGHT={dual_result['effective_fps_right']:.1f}fps, Errors={dual_result['errors']}")

    # Write report
    report_path = output_dir / "capability_report.txt"
    report_path.write_text("\n".join(report_lines))

    print(f"\n\n{'='*70}")
    print(f"Report saved to: {report_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()

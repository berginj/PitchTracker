#!/usr/bin/env python
"""Camera Detection Diagnostic Tool

This script helps diagnose why ArduCam devices aren't being detected consistently.
It tests multiple detection methods and timing scenarios.

Usage:
    python diagnose_camera_detection.py
"""

import logging
import sys
import time
from pathlib import Path

import cv2

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ui.device_utils import (
    probe_uvc_devices,
    probe_opencv_indices,
    is_arducam_device,
    clear_device_cache,
)

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_uvc_enumeration(attempt: int) -> list[dict]:
    """Test UVC device enumeration."""
    logger.info(f"[Attempt {attempt}] Testing UVC enumeration...")
    try:
        devices = probe_uvc_devices(use_cache=False)
        logger.info(f"[Attempt {attempt}] Found {len(devices)} UVC devices")

        arducam_count = 0
        for i, dev in enumerate(devices):
            friendly = dev.get('friendly_name', 'Unknown')
            serial = dev.get('serial', 'N/A')
            manufacturer = dev.get('manufacturer', 'Unknown')
            is_arducam = is_arducam_device(friendly)
            if is_arducam:
                arducam_count += 1
                logger.info(f"[Attempt {attempt}]   ⭐ UVC {i}: {friendly} [Mfg: {manufacturer}] (SN: {serial}) - ARDUCAM")
            else:
                logger.info(f"[Attempt {attempt}]   UVC {i}: {friendly} [Mfg: {manufacturer}] (SN: {serial})")

        logger.info(f"[Attempt {attempt}] ArduCam devices via UVC: {arducam_count}")
        return devices
    except Exception as e:
        logger.error(f"[Attempt {attempt}] UVC enumeration failed: {e}", exc_info=True)
        return []


def test_opencv_probing(attempt: int, max_index: int = 10) -> list[int]:
    """Test OpenCV camera index probing."""
    logger.info(f"[Attempt {attempt}] Testing OpenCV probing (0-{max_index-1})...")
    try:
        indices = probe_opencv_indices(max_index=max_index, parallel=True, use_cache=False)
        logger.info(f"[Attempt {attempt}] Found {len(indices)} OpenCV indices: {indices}")
        return indices
    except Exception as e:
        logger.error(f"[Attempt {attempt}] OpenCV probing failed: {e}", exc_info=True)
        return []


def test_sequential_probing(attempt: int, max_index: int = 10) -> list[int]:
    """Test sequential OpenCV probing (non-parallel)."""
    logger.info(f"[Attempt {attempt}] Testing Sequential OpenCV probing (0-{max_index-1})...")
    try:
        indices = probe_opencv_indices(max_index=max_index, parallel=False, use_cache=False)
        logger.info(f"[Attempt {attempt}] Found {len(indices)} OpenCV indices (sequential): {indices}")
        return indices
    except Exception as e:
        logger.error(f"[Attempt {attempt}] Sequential probing failed: {e}", exc_info=True)
        return []


def test_direct_opencv_open(attempt: int, max_index: int = 10, timeout: float = 2.0):
    """Test opening cameras directly with OpenCV."""
    logger.info(f"[Attempt {attempt}] Testing direct OpenCV opening (timeout={timeout}s)...")

    results = []
    for idx in range(max_index):
        logger.debug(f"[Attempt {attempt}] Trying to open camera {idx}...")
        start = time.time()

        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            elapsed = time.time() - start

            if cap.isOpened():
                # Try to read backend info
                backend = cap.getBackendName()

                # Try to read a frame
                ret, frame = cap.read()
                can_read = ret and frame is not None

                cap.release()

                logger.info(f"[Attempt {attempt}]   Camera {idx}: OPENED in {elapsed:.2f}s (backend={backend}, can_read={can_read})")
                results.append({
                    'index': idx,
                    'opened': True,
                    'time': elapsed,
                    'backend': backend,
                    'can_read': can_read
                })
            else:
                cap.release()
                logger.debug(f"[Attempt {attempt}]   Camera {idx}: Failed to open in {elapsed:.2f}s")
                results.append({
                    'index': idx,
                    'opened': False,
                    'time': elapsed
                })

        except Exception as e:
            elapsed = time.time() - start
            logger.debug(f"[Attempt {attempt}]   Camera {idx}: Exception after {elapsed:.2f}s: {e}")
            results.append({
                'index': idx,
                'opened': False,
                'time': elapsed,
                'error': str(e)
            })

    successful = [r for r in results if r.get('opened', False)]
    logger.info(f"[Attempt {attempt}] Direct opening: {len(successful)}/{max_index} cameras opened")

    return results


def test_arducam_mapping(attempt: int, uvc_devices: list[dict], opencv_indices: list[int]):
    """Test mapping between UVC devices and OpenCV indices."""
    logger.info(f"[Attempt {attempt}] Testing ArduCam device mapping...")

    # Find ArduCam devices in UVC list
    arducam_uvc_indices = []
    for i, dev in enumerate(uvc_devices):
        if is_arducam_device(dev.get('friendly_name', '')):
            arducam_uvc_indices.append(i)
            logger.info(f"[Attempt {attempt}]   ArduCam at UVC index {i}: {dev.get('friendly_name')}")

    logger.info(f"[Attempt {attempt}] ArduCam UVC indices: {arducam_uvc_indices}")
    logger.info(f"[Attempt {attempt}] OpenCV indices available: {opencv_indices}")

    # Check if ArduCam UVC indices are in OpenCV indices
    for uvc_idx in arducam_uvc_indices:
        if uvc_idx in opencv_indices:
            logger.info(f"[Attempt {attempt}]   ✅ ArduCam UVC index {uvc_idx} is available in OpenCV")
        else:
            logger.warning(f"[Attempt {attempt}]   ❌ ArduCam UVC index {uvc_idx} NOT available in OpenCV")

    return arducam_uvc_indices


def main():
    """Run camera detection diagnostics."""
    print("=" * 80)
    print("Camera Detection Diagnostic Tool")
    print("=" * 80)
    print()

    print("This tool will test camera detection multiple times to identify")
    print("inconsistencies and timing issues with ArduCam devices.")
    print()

    num_attempts = 5
    max_cameras = 10

    print(f"Testing {num_attempts} times with up to {max_cameras} camera indices")
    print("=" * 80)
    print()

    # Store results across attempts
    all_results = {
        'uvc': [],
        'opencv_parallel': [],
        'opencv_sequential': [],
        'direct_open': [],
        'arducam_mapping': []
    }

    for attempt in range(1, num_attempts + 1):
        print(f"\n{'='*80}")
        print(f"ATTEMPT {attempt}/{num_attempts}")
        print(f"{'='*80}\n")

        # Clear cache before each attempt
        clear_device_cache()

        # Test 1: UVC enumeration
        uvc_devices = test_uvc_enumeration(attempt)
        all_results['uvc'].append(len(uvc_devices))

        # Small delay
        time.sleep(0.5)

        # Test 2: OpenCV parallel probing
        opencv_indices = test_opencv_probing(attempt, max_cameras)
        all_results['opencv_parallel'].append(len(opencv_indices))

        # Small delay
        time.sleep(0.5)

        # Test 3: OpenCV sequential probing
        opencv_seq = test_sequential_probing(attempt, max_cameras)
        all_results['opencv_sequential'].append(len(opencv_seq))

        # Small delay
        time.sleep(0.5)

        # Test 4: Direct OpenCV opening
        direct_results = test_direct_opencv_open(attempt, max_cameras, timeout=2.0)
        all_results['direct_open'].append(len([r for r in direct_results if r.get('opened', False)]))

        # Test 5: ArduCam mapping
        arducam_indices = test_arducam_mapping(attempt, uvc_devices, opencv_indices)
        all_results['arducam_mapping'].append(len(arducam_indices))

        # Wait before next attempt
        if attempt < num_attempts:
            print(f"\nWaiting 2 seconds before next attempt...")
            time.sleep(2.0)

    # Summary
    print(f"\n\n{'='*80}")
    print("DIAGNOSTIC SUMMARY")
    print(f"{'='*80}\n")

    print(f"Test ran {num_attempts} times with results:\n")

    print("UVC Device Count:")
    print(f"  Results: {all_results['uvc']}")
    print(f"  Min: {min(all_results['uvc'])}, Max: {max(all_results['uvc'])}, Avg: {sum(all_results['uvc'])/len(all_results['uvc']):.1f}")
    print(f"  Consistent: {len(set(all_results['uvc'])) == 1}")
    print()

    print("OpenCV Parallel Probe Count:")
    print(f"  Results: {all_results['opencv_parallel']}")
    print(f"  Min: {min(all_results['opencv_parallel'])}, Max: {max(all_results['opencv_parallel'])}, Avg: {sum(all_results['opencv_parallel'])/len(all_results['opencv_parallel']):.1f}")
    print(f"  Consistent: {len(set(all_results['opencv_parallel'])) == 1}")
    print()

    print("OpenCV Sequential Probe Count:")
    print(f"  Results: {all_results['opencv_sequential']}")
    print(f"  Min: {min(all_results['opencv_sequential'])}, Max: {max(all_results['opencv_sequential'])}, Avg: {sum(all_results['opencv_sequential'])/len(all_results['opencv_sequential']):.1f}")
    print(f"  Consistent: {len(set(all_results['opencv_sequential'])) == 1}")
    print()

    print("Direct OpenCV Open Count:")
    print(f"  Results: {all_results['direct_open']}")
    print(f"  Min: {min(all_results['direct_open'])}, Max: {max(all_results['direct_open'])}, Avg: {sum(all_results['direct_open'])/len(all_results['direct_open']):.1f}")
    print(f"  Consistent: {len(set(all_results['direct_open'])) == 1}")
    print()

    print("ArduCam Device Count:")
    print(f"  Results: {all_results['arducam_mapping']}")
    print(f"  Min: {min(all_results['arducam_mapping'])}, Max: {max(all_results['arducam_mapping'])}, Avg: {sum(all_results['arducam_mapping'])/len(all_results['arducam_mapping']):.1f}")
    print(f"  Consistent: {len(set(all_results['arducam_mapping'])) == 1}")
    print()

    # Analysis
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print()

    if len(set(all_results['uvc'])) > 1:
        print("⚠️ UVC enumeration is INCONSISTENT")
        print("   - PowerShell query returning different results")
        print("   - Possible USB power/enumeration issue")
        print()

    if len(set(all_results['opencv_parallel'])) > 1:
        print("⚠️ OpenCV parallel probing is INCONSISTENT")
        print("   - Timeout or race condition in parallel probing")
        print("   - Try increasing timeout or using sequential probing")
        print()

    if len(set(all_results['opencv_sequential'])) > 1:
        print("⚠️ OpenCV sequential probing is INCONSISTENT")
        print("   - Cameras not responding reliably")
        print("   - Check USB connections and power")
        print()

    if all_results['opencv_parallel'] != all_results['opencv_sequential']:
        print("⚠️ Parallel and sequential probing give DIFFERENT results")
        print("   - Parallel probing may be timing out")
        print("   - Recommendation: Use sequential probing or increase timeout")
        print()

    if len(set(all_results['arducam_mapping'])) > 1:
        print("⚠️ ArduCam device count is INCONSISTENT")
        print("   - ArduCam devices not being detected reliably")
        print("   - Check:")
        print("     - USB hub power (try powered hub)")
        print("     - USB cable quality")
        print("     - Windows Device Manager for errors")
        print("     - Other applications using cameras")
        print()

    if all(len(set(all_results[k])) == 1 for k in all_results):
        print("✅ All detection methods are CONSISTENT")
        print("   - Cameras are being detected reliably")
        print("   - If ArduCam count is 0, they may not be connected or recognized")
        print()


if __name__ == "__main__":
    main()

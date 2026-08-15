"""System-level stress tests for extreme conditions.

These tests push the system to its limits to identify breaking points
and validate behavior under extreme load conditions.
"""

import unittest
import threading
import time
import gc
import os
import tempfile
import shutil
from pathlib import Path

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@unittest.skipUnless(
    os.environ.get("PITCHTRACKER_RUN_STRESS") == "1",
    "Long-running soak/marathon stress tests. Opt in with PITCHTRACKER_RUN_STRESS=1. "
    "These run for minutes (exceeding the 120s CI per-test timeout) and need "
    "rewriting against the current Frame/AppConfig/SessionRecorder APIs.",
)
class TestSystemStressTests(unittest.TestCase):
    """Extreme stress tests for system limits."""

    def setUp(self):
        """Set up test fixtures."""
        if not PSUTIL_AVAILABLE:
            self.skipTest("psutil not available - install with: pip install psutil")

        self.process = psutil.Process()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test artifacts."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def get_memory_mb(self) -> float:
        """Get current process memory in MB."""
        return self.process.memory_info().rss / (1024 * 1024)

    def test_extended_marathon_10_minutes(self):
        """Marathon test: 10 minutes of continuous operation."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from contracts import Frame
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig, FilterConfig
        import numpy as np

        print("\n" + "=" * 70)
        print(" " * 20 + "MARATHON TEST: 10 MINUTES")
        print("=" * 70)
        print("This test validates system stability over extended operation.")
        print("Watch for: memory growth, performance degradation, errors")
        print("=" * 70)

        # Create detector
        filter_config = FilterConfig()
        detector_config = DetectorConfig(filters=filter_config)
        detector = ClassicalDetector(detector_config)

        # Start detection pool
        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: detector.detect(frame))
        pool.start(queue_size=6)

        # Initial state
        gc.collect()
        time.sleep(0.5)
        initial_memory = self.get_memory_mb()
        initial_threads = threading.active_count()

        print("\nInitial State:")
        print(f"  Memory: {initial_memory:.1f} MB")
        print(f"  Threads: {initial_threads}")
        print()

        # Run for 10 minutes
        duration = 600  # 10 minutes
        start_time = time.time()
        frame_count = 0
        error_count = 0

        # Track performance
        fps_samples = []
        last_fps_check = start_time

        # Create frame template
        image = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)

        try:
            while time.time() - start_time < duration:
                # Process frame
                timestamp = int(time.time() * 1e9)
                frame = Frame(
                    image=image,
                    t_capture_monotonic_ns=timestamp,
                    t_capture_utc_ns=timestamp,
                    t_received_monotonic_ns=timestamp,
                    width=1280,
                    height=720,
                    camera_id="marathon_test",
                )

                try:
                    pool.enqueue_frame("left", frame)
                    frame_count += 1
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:  # Log first 5 errors
                        print(f"  ⚠️ Error enqueueing frame: {e}")

                # Calculate FPS every 10 seconds
                if time.time() - last_fps_check >= 10.0:
                    elapsed = time.time() - last_fps_check
                    fps = (frame_count - len(fps_samples) * 600) / elapsed
                    fps_samples.append(fps)
                    last_fps_check = time.time()

                # Status report every 60 seconds
                if frame_count % 3600 == 0 and frame_count > 0:
                    gc.collect()
                    current_memory = self.get_memory_mb()
                    current_threads = threading.active_count()
                    elapsed_min = (time.time() - start_time) / 60
                    growth = current_memory - initial_memory
                    growth_pct = (growth / initial_memory) * 100
                    avg_fps = sum(fps_samples) / len(fps_samples) if fps_samples else 0

                    print(
                        f"  [{elapsed_min:>5.1f}m] Memory: {current_memory:>7.1f} MB "
                        f"(+{growth:>5.1f} MB, +{growth_pct:>5.1f}%) | "
                        f"Threads: {current_threads} | "
                        f"Avg FPS: {avg_fps:>6.1f} | "
                        f"Frames: {frame_count:>7,} | "
                        f"Errors: {error_count}"
                    )

                # Throttle to ~60 FPS
                time.sleep(0.016)

        finally:
            # Final statistics
            elapsed = time.time() - start_time
            gc.collect()
            time.sleep(0.5)
            final_memory = self.get_memory_mb()
            final_threads = threading.active_count()

            print(f"\n{'='*70}")
            print("Marathon Test Results:")
            print(f"{'='*70}")
            print(f"  Duration: {elapsed/60:.1f} minutes")
            print(f"  Frames Processed: {frame_count:,}")
            print(f"  Errors: {error_count}")
            print(f"  Average FPS: {frame_count/elapsed:.1f}")
            print("\n  Memory:")
            print(f"    Initial: {initial_memory:.1f} MB")
            print(f"    Final: {final_memory:.1f} MB")
            print(
                f"    Growth: +{final_memory - initial_memory:.1f} MB "
                f"(+{(final_memory - initial_memory)/initial_memory*100:.1f}%)"
            )
            print("\n  Threads:")
            print(f"    Initial: {initial_threads}")
            print(f"    Final: {final_threads}")
            print(f"    Change: {final_threads - initial_threads:+d}")

            # Stop pool
            pool.stop()

            # Assertions
            memory_growth_pct = (final_memory - initial_memory) / initial_memory * 100
            self.assertLess(memory_growth_pct, 20.0, f"Memory grew {memory_growth_pct:.1f}% over 10 minutes")

            self.assertLessEqual(
                final_threads - initial_threads, 5, f"Thread count increased by {final_threads - initial_threads}"
            )

            self.assertLess(
                error_count / frame_count if frame_count > 0 else 1.0,
                0.01,  # <1% error rate
                f"High error rate: {error_count}/{frame_count}",
            )

            print("\n✅ PASS: System stable over 10-minute marathon")

    def test_high_frame_rate_stress(self):
        """Stress test with high frame rate (120+ FPS input)."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from contracts import Frame
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig, FilterConfig
        import numpy as np

        print("\n" + "=" * 70)
        print(" " * 20 + "HIGH FRAME RATE STRESS TEST")
        print("=" * 70)
        print("Simulating 120 FPS input to test backpressure handling.")
        print("=" * 70)

        # Create detector
        filter_config = FilterConfig()
        detector_config = DetectorConfig(filters=filter_config)
        detector = ClassicalDetector(detector_config)

        # Start detection pool
        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: detector.detect(frame))
        pool.start(queue_size=6)

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"\nInitial memory: {initial_memory:.1f} MB")

        # Send frames at 120 FPS for 2 minutes
        duration = 120  # 2 minutes
        target_fps = 120
        frame_interval = 1.0 / target_fps

        start_time = time.time()
        frame_count = 0
        dropped_frames = 0

        image = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)

        print(f"Sending frames at {target_fps} FPS for {duration} seconds...")

        while time.time() - start_time < duration:
            timestamp = int(time.time() * 1e9)
            frame = Frame(
                image=image,
                t_capture_monotonic_ns=timestamp,
                t_capture_utc_ns=timestamp,
                t_received_monotonic_ns=timestamp,
                width=1280,
                height=720,
                camera_id="high_fps_test",
            )

            try:
                pool.enqueue_frame("left", frame)
                frame_count += 1
            except Exception:
                dropped_frames += 1

            # Sleep to maintain target FPS
            time.sleep(frame_interval)

            # Status every 30 seconds
            if frame_count % (target_fps * 30) == 0 and frame_count > 0:
                elapsed = time.time() - start_time
                actual_fps = frame_count / elapsed
                drop_rate = dropped_frames / (frame_count + dropped_frames) * 100
                print(
                    f"  [{elapsed:>5.0f}s] Sent: {frame_count:>6,} frames | "
                    f"Dropped: {dropped_frames:>4} ({drop_rate:.1f}%) | "
                    f"Actual: {actual_fps:.1f} FPS"
                )

        # Final check
        elapsed = time.time() - start_time
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()

        print(f"\n{'='*70}")
        print("High Frame Rate Test Results:")
        print(f"{'='*70}")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Target FPS: {target_fps}")
        print(f"  Frames Sent: {frame_count:,}")
        print(f"  Frames Dropped: {dropped_frames}")
        print(f"  Drop Rate: {dropped_frames/(frame_count+dropped_frames)*100:.2f}%")
        print(f"  Actual FPS: {frame_count/elapsed:.1f}")
        print(
            f"\n  Memory: {initial_memory:.1f} MB → {final_memory:.1f} MB " f"(+{final_memory-initial_memory:.1f} MB)"
        )

        pool.stop()

        # System should handle backpressure gracefully
        memory_growth_pct = (final_memory - initial_memory) / initial_memory * 100
        self.assertLess(memory_growth_pct, 25.0, f"Memory grew {memory_growth_pct:.1f}% under high frame rate")

        print("\n✅ PASS: System handles high frame rate with backpressure")


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)

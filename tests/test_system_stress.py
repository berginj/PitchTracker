"""System-level stress tests for extreme conditions.

These tests push the system to its limits to identify breaking points
and validate behavior under extreme load conditions.
"""

import unittest
import threading
import time
import gc
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


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

        print("\n" + "="*70)
        print(" " * 20 + "MARATHON TEST: 10 MINUTES")
        print("="*70)
        print("This test validates system stability over extended operation.")
        print("Watch for: memory growth, performance degradation, errors")
        print("="*70)

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

        print(f"\nInitial State:")
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
                    camera_id="marathon_test"
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

                    print(f"  [{elapsed_min:>5.1f}m] Memory: {current_memory:>7.1f} MB "
                          f"(+{growth:>5.1f} MB, +{growth_pct:>5.1f}%) | "
                          f"Threads: {current_threads} | "
                          f"Avg FPS: {avg_fps:>6.1f} | "
                          f"Frames: {frame_count:>7,} | "
                          f"Errors: {error_count}")

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
            print(f"\n  Memory:")
            print(f"    Initial: {initial_memory:.1f} MB")
            print(f"    Final: {final_memory:.1f} MB")
            print(f"    Growth: +{final_memory - initial_memory:.1f} MB "
                  f"(+{(final_memory - initial_memory)/initial_memory*100:.1f}%)")
            print(f"\n  Threads:")
            print(f"    Initial: {initial_threads}")
            print(f"    Final: {final_threads}")
            print(f"    Change: {final_threads - initial_threads:+d}")

            # Stop pool
            pool.stop()

            # Assertions
            memory_growth_pct = (final_memory - initial_memory) / initial_memory * 100
            self.assertLess(
                memory_growth_pct,
                20.0,
                f"Memory grew {memory_growth_pct:.1f}% over 10 minutes"
            )

            self.assertLessEqual(
                final_threads - initial_threads,
                5,
                f"Thread count increased by {final_threads - initial_threads}"
            )

            self.assertLess(
                error_count / frame_count if frame_count > 0 else 1.0,
                0.01,  # <1% error rate
                f"High error rate: {error_count}/{frame_count}"
            )

            print(f"\n✅ PASS: System stable over 10-minute marathon")

    def test_high_frame_rate_stress(self):
        """Stress test with high frame rate (120+ FPS input)."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from contracts import Frame
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig, FilterConfig
        import numpy as np

        print("\n" + "="*70)
        print(" " * 20 + "HIGH FRAME RATE STRESS TEST")
        print("="*70)
        print("Simulating 120 FPS input to test backpressure handling.")
        print("="*70)

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
                camera_id="high_fps_test"
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
                print(f"  [{elapsed:>5.0f}s] Sent: {frame_count:>6,} frames | "
                      f"Dropped: {dropped_frames:>4} ({drop_rate:.1f}%) | "
                      f"Actual: {actual_fps:.1f} FPS")

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
        print(f"\n  Memory: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{final_memory-initial_memory:.1f} MB)")

        pool.stop()

        # System should handle backpressure gracefully
        memory_growth_pct = (final_memory - initial_memory) / initial_memory * 100
        self.assertLess(
            memory_growth_pct,
            25.0,
            f"Memory grew {memory_growth_pct:.1f}% under high frame rate"
        )

        print(f"\n✅ PASS: System handles high frame rate with backpressure")

    def test_multi_session_marathon(self):
        """Stress test: 50 recording sessions back-to-back."""
        from app.pipeline.recording.session_recorder import SessionRecorder
        from app.config import AppConfig
        import numpy as np

        print("\n" + "="*70)
        print(" " * 20 + "MULTI-SESSION MARATHON TEST")
        print("="*70)
        print("Recording 50 sessions back-to-back to test session lifecycle.")
        print("="*70)

        config = AppConfig()
        config.video_fps = 60
        config.video_codec = "MJPG"

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"\nInitial memory: {initial_memory:.1f} MB")

        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        num_sessions = 50
        frames_per_session = 60  # 1 second of video

        print(f"Recording {num_sessions} sessions ({frames_per_session} frames each)...\n")

        for session_num in range(num_sessions):
            # Create recorder
            recorder = SessionRecorder(config, self.temp_dir)

            # Start session
            session_dir, _ = recorder.start_session(
                session_name=f"marathon_{session_num:03d}",
                pitch_id=f"pitch_{session_num:03d}",
                mode="test"
            )

            # Record frames
            base_timestamp = int(time.time() * 1e9)
            for i in range(frames_per_session):
                timestamp = base_timestamp + i * 16_666_667
                recorder.add_frame("left", frame, timestamp)
                recorder.add_frame("right", frame, timestamp)

            # Stop session
            recorder.stop_session()

            # Report every 10 sessions
            if (session_num + 1) % 10 == 0:
                gc.collect()
                current_memory = self.get_memory_mb()
                growth = current_memory - initial_memory
                growth_pct = (growth / initial_memory) * 100
                print(f"  Session {session_num+1:>2}/{num_sessions}: "
                      f"{current_memory:>7.1f} MB (+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()

        print(f"\n{'='*70}")
        print("Multi-Session Results:")
        print(f"{'='*70}")
        print(f"  Sessions: {num_sessions}")
        print(f"  Total Frames: {num_sessions * frames_per_session * 2:,}")
        print(f"  Memory: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{final_memory-initial_memory:.1f} MB, "
              f"+{(final_memory-initial_memory)/initial_memory*100:.1f}%)")

        memory_growth_pct = (final_memory - initial_memory) / initial_memory * 100
        self.assertLess(
            memory_growth_pct,
            25.0,
            f"Memory grew {memory_growth_pct:.1f}% after {num_sessions} sessions"
        )

        print(f"\n✅ PASS: System stable across {num_sessions} sessions")

    def test_concurrent_detection_pools(self):
        """Stress test: Multiple detection pools running concurrently."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from contracts import Frame
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig, FilterConfig
        import numpy as np

        print("\n" + "="*70)
        print(" " * 20 + "CONCURRENT POOLS STRESS TEST")
        print("="*70)
        print("Running 5 detection pools simultaneously.")
        print("="*70)

        gc.collect()
        initial_memory = self.get_memory_mb()
        initial_threads = threading.active_count()

        print(f"\nInitial state:")
        print(f"  Memory: {initial_memory:.1f} MB")
        print(f"  Threads: {initial_threads}")

        # Create 5 pools
        pools = []
        for pool_id in range(5):
            filter_config = FilterConfig()
            detector_config = DetectorConfig(filters=filter_config)
            detector = ClassicalDetector(detector_config)

            pool = DetectionThreadPool()
            pool.set_detect_callback(lambda label, frame: detector.detect(frame))
            pool.start(queue_size=6)
            pools.append((pool, detector))

        print(f"\nAll pools started. Running for 60 seconds...")

        # Process frames on all pools
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        duration = 60
        start_time = time.time()
        frame_counts = [0] * 5

        while time.time() - start_time < duration:
            timestamp = int(time.time() * 1e9)
            frame = Frame(
                image=image,
                t_capture_monotonic_ns=timestamp,
                t_capture_utc_ns=timestamp,
                t_received_monotonic_ns=timestamp,
                width=640,
                height=480,
                camera_id="concurrent_test"
            )

            # Send to all pools
            for pool_id, (pool, _) in enumerate(pools):
                try:
                    pool.enqueue_frame("left", frame)
                    frame_counts[pool_id] += 1
                except Exception:
                    pass

            time.sleep(0.016)  # ~60 FPS

        # Check state during operation
        mid_memory = self.get_memory_mb()
        mid_threads = threading.active_count()

        print(f"\nDuring operation:")
        print(f"  Memory: {mid_memory:.1f} MB (+{mid_memory-initial_memory:.1f} MB)")
        print(f"  Threads: {mid_threads} (+{mid_threads-initial_threads})")

        # Stop all pools
        for pool, _ in pools:
            pool.stop()

        time.sleep(0.5)
        gc.collect()
        time.sleep(0.5)

        final_memory = self.get_memory_mb()
        final_threads = threading.active_count()

        print(f"\nAfter cleanup:")
        print(f"  Memory: {final_memory:.1f} MB (+{final_memory-initial_memory:.1f} MB)")
        print(f"  Threads: {final_threads} (+{final_threads-initial_threads})")
        print(f"\nFrames processed per pool: {[f'{c:,}' for c in frame_counts]}")

        # Threads should return to near-initial
        self.assertLessEqual(
            final_threads - initial_threads,
            10,
            f"Thread leak: {initial_threads} → {final_threads}"
        )

        # Memory should be reasonable
        memory_growth_pct = (final_memory - initial_memory) / initial_memory * 100
        self.assertLess(
            memory_growth_pct,
            30.0,
            f"High memory growth: {memory_growth_pct:.1f}%"
        )

        print(f"\n✅ PASS: Concurrent pools handled successfully")

    def test_system_resource_limits(self):
        """Test system behavior approaching resource limits."""
        import numpy as np

        print("\n" + "="*70)
        print(" " * 20 + "SYSTEM RESOURCE LIMITS TEST")
        print("="*70)
        print("Testing behavior as system approaches resource limits.")
        print("="*70)

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"\nInitial memory: {initial_memory:.1f} MB")

        # Allocate large arrays to simulate high memory pressure
        large_arrays = []
        allocation_size_mb = 50  # 50 MB per array
        max_arrays = 20  # Up to 1 GB

        print(f"\nAllocating {max_arrays} arrays of {allocation_size_mb} MB each...")

        try:
            for i in range(max_arrays):
                # Allocate large array
                size = int(allocation_size_mb * 1024 * 1024 / 8)  # 8 bytes per float64
                arr = np.zeros(size, dtype=np.float64)
                large_arrays.append(arr)

                current_memory = self.get_memory_mb()
                print(f"  Array {i+1:>2}/{max_arrays}: "
                      f"Memory = {current_memory:>8.1f} MB "
                      f"(+{current_memory-initial_memory:>6.1f} MB)")

                # Check system memory
                system_memory = psutil.virtual_memory()
                if system_memory.percent > 90:
                    print(f"  ⚠️ System memory at {system_memory.percent:.1f}%, stopping allocation")
                    break

        except MemoryError as e:
            print(f"  ⚠️ MemoryError encountered: {e}")

        # Verify system can still operate
        print(f"\nTesting system operation under memory pressure...")

        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from contracts import Frame
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig, FilterConfig

        filter_config = FilterConfig()
        detector_config = DetectorConfig(filters=filter_config)
        detector = ClassicalDetector(detector_config)

        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: detector.detect(frame))
        pool.start(queue_size=6)

        # Process frames under memory pressure
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        errors = 0

        for i in range(100):
            try:
                timestamp = int(time.time() * 1e9)
                frame = Frame(
                    image=image,
                    t_capture_monotonic_ns=timestamp,
                    t_capture_utc_ns=timestamp,
                    t_received_monotonic_ns=timestamp,
                    width=640,
                    height=480,
                    camera_id="limit_test"
                )
                pool.enqueue_frame("left", frame)
            except Exception as e:
                errors += 1

        time.sleep(0.5)
        pool.stop()

        # Clean up large arrays
        large_arrays.clear()
        gc.collect()
        time.sleep(0.5)

        final_memory = self.get_memory_mb()

        print(f"\n{'='*70}")
        print("Resource Limits Test Results:")
        print(f"{'='*70}")
        print(f"  Peak memory: {max([initial_memory] + [self.get_memory_mb()]):.1f} MB")
        print(f"  Final memory: {final_memory:.1f} MB")
        print(f"  Errors processing frames: {errors}/100")
        print(f"  System remained operational: {'✅ YES' if errors < 10 else '❌ NO'}")

        self.assertLess(errors, 10, "Too many errors under memory pressure")

        print(f"\n✅ PASS: System handles memory pressure gracefully")


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)

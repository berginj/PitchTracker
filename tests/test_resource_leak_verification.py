"""Stress test to verify no resource leaks (threads, memory)."""

import unittest
import threading
import time
import gc


class TestResourceLeakVerification(unittest.TestCase):
    """Verify no resource leaks in timeout utilities and detection pipeline."""

    def test_timeout_utils_no_thread_leak(self):
        """Verify timeout operations don't leak threads."""
        from capture.timeout_utils import run_with_timeout

        # Get initial thread count
        gc.collect()
        initial_threads = threading.active_count()

        # Run 100 timeout operations
        def dummy_operation():
            time.sleep(0.01)
            return "success"

        for i in range(100):
            try:
                result = run_with_timeout(dummy_operation, 1.0)
                self.assertEqual(result, "success")
            except Exception as e:
                self.fail(f"Timeout operation {i} failed: {e}")

        # Force garbage collection
        gc.collect()
        time.sleep(0.2)  # Allow threads to terminate

        # Check thread count hasn't grown
        final_threads = threading.active_count()
        thread_growth = final_threads - initial_threads

        self.assertLessEqual(
            thread_growth,
            2,  # Allow 1-2 threads for test infrastructure
            f"Thread leak detected: {initial_threads} → {final_threads} "
            f"(+{thread_growth} threads after 100 operations)"
        )

    def test_timeout_utils_handles_timeouts_without_leak(self):
        """Verify timeout operations that actually timeout don't leak threads."""
        from capture.timeout_utils import run_with_timeout
        from exceptions import CameraConnectionError

        gc.collect()
        initial_threads = threading.active_count()

        # Run 50 operations that will timeout
        def slow_operation():
            time.sleep(10.0)  # Way longer than timeout
            return "shouldn't reach here"

        timeout_count = 0
        for i in range(50):
            try:
                run_with_timeout(slow_operation, 0.05, f"Operation {i}")
                self.fail("Should have timed out")
            except CameraConnectionError:
                timeout_count += 1

        self.assertEqual(timeout_count, 50, "All operations should have timed out")

        # Force garbage collection
        gc.collect()
        time.sleep(0.5)  # Allow threads to terminate

        # Check thread count
        final_threads = threading.active_count()
        thread_growth = final_threads - initial_threads

        self.assertLessEqual(
            thread_growth,
            5,  # Allow a few threads for executor cleanup
            f"Thread leak on timeout: {initial_threads} → {final_threads} "
            f"(+{thread_growth} threads after 50 timeouts)"
        )

    def test_detection_pool_no_thread_leak(self):
        """Verify detection pool start/stop doesn't leak threads."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from contracts import Frame
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode
        import numpy as np

        gc.collect()
        initial_threads = threading.active_count()

        # Create detector
        filter_config = FilterConfig()
        cv_config = CvDetectorConfig(filter=filter_config, mode=Mode.HSV_MASK)
        detector = ClassicalDetector(cv_config)

        # Start and stop detection pool 10 times
        for i in range(10):
            pool = DetectionThreadPool()
            pool.set_detect_callback(lambda label, frame: detector.detect(frame))
            pool.start(queue_size=6)

            # Process a few frames
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            frame = Frame(
                image=image,
                t_capture_monotonic_ns=int(time.time() * 1e9),
                t_capture_utc_ns=int(time.time() * 1e9),
                t_received_monotonic_ns=int(time.time() * 1e9),
                width=640,
                height=480,
                camera_id="test"
            )

            for j in range(10):
                pool.enqueue_frame("left", frame)
                pool.enqueue_frame("right", frame)

            time.sleep(0.1)  # Allow processing

            # Stop pool
            pool.stop()
            time.sleep(0.1)  # Allow cleanup

        # Force garbage collection
        gc.collect()
        time.sleep(0.3)

        # Check thread count
        final_threads = threading.active_count()
        thread_growth = final_threads - initial_threads

        self.assertLessEqual(
            thread_growth,
            3,  # Allow a few threads for test infrastructure
            f"Thread leak in detection pool: {initial_threads} → {final_threads} "
            f"(+{thread_growth} threads after 10 start/stop cycles)"
        )

    def test_detection_pool_extended_operation(self):
        """Verify detection pool doesn't leak threads during extended operation."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from contracts import Frame
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode
        import numpy as np

        gc.collect()
        initial_threads = threading.active_count()

        # Create detector
        filter_config = FilterConfig()
        cv_config = CvDetectorConfig(filter=filter_config, mode=Mode.HSV_MASK)
        detector = ClassicalDetector(cv_config)

        # Start detection pool
        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: detector.detect(frame))
        pool.start(queue_size=6)

        # Process 1000 frames
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        frame = Frame(
            image=image,
            t_capture_monotonic_ns=int(time.time() * 1e9),
            t_capture_utc_ns=int(time.time() * 1e9),
            t_received_monotonic_ns=int(time.time() * 1e9),
            width=640,
            height=480,
            camera_id="test"
        )

        for i in range(1000):
            pool.enqueue_frame("left", frame)
            pool.enqueue_frame("right", frame)

        time.sleep(0.5)  # Allow all processing to complete

        # Check threads during operation
        mid_threads = threading.active_count()

        # Stop pool
        pool.stop()
        time.sleep(0.2)

        # Force garbage collection
        gc.collect()
        time.sleep(0.3)

        # Check final thread count
        final_threads = threading.active_count()

        # Threads should return to near-initial count
        thread_growth = final_threads - initial_threads

        self.assertLessEqual(
            thread_growth,
            3,
            f"Threads not cleaned up after extended operation: "
            f"{initial_threads} → {mid_threads} (during) → {final_threads} (after)"
        )

    def test_memory_stability_during_detection(self):
        """Verify memory doesn't grow unbounded during detection."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from contracts import Frame
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode
        import numpy as np

        try:
            import psutil
            process = psutil.Process()
        except ImportError:
            self.skipTest("psutil not available")

        # Create detector
        filter_config = FilterConfig()
        cv_config = CvDetectorConfig(filter=filter_config, mode=Mode.HSV_MASK)
        detector = ClassicalDetector(cv_config)

        # Start detection pool
        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: detector.detect(frame))
        pool.start(queue_size=6)

        # Get initial memory
        gc.collect()
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB

        # Process 2000 frames
        image = np.zeros((480, 640, 3), dtype=np.uint8)

        for i in range(2000):
            frame = Frame(
                image=image,
                t_capture_monotonic_ns=int(time.time() * 1e9),
                t_capture_utc_ns=int(time.time() * 1e9),
                t_received_monotonic_ns=int(time.time() * 1e9),
                width=640,
                height=480,
                camera_id="test"
            )
            pool.enqueue_frame("left", frame)
            pool.enqueue_frame("right", frame)

            # Sample memory periodically
            if i % 500 == 0 and i > 0:
                gc.collect()
                current_memory = process.memory_info().rss / (1024 * 1024)
                growth = current_memory - initial_memory
                print(f"  Frame {i}: Memory {current_memory:.1f}MB (+{growth:.1f}MB)")

        time.sleep(1.0)  # Allow all processing

        # Final memory check
        gc.collect()
        final_memory = process.memory_info().rss / (1024 * 1024)
        memory_growth = final_memory - initial_memory
        growth_percent = (memory_growth / initial_memory) * 100

        print(f"  Memory: {initial_memory:.1f}MB → {final_memory:.1f}MB "
              f"(+{memory_growth:.1f}MB, +{growth_percent:.1f}%)")

        # Stop pool
        pool.stop()

        # Allow memory growth up to 20% (some growth is normal)
        self.assertLess(
            growth_percent,
            20.0,
            f"Memory grew {growth_percent:.1f}% (>{20.0}% threshold). "
            f"Possible memory leak."
        )


if __name__ == "__main__":
    unittest.main()

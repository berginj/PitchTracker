"""Extended memory stress tests for leak detection.

These tests run for longer durations and test more complex scenarios
than the basic resource leak verification tests.
"""

import unittest
import threading
import time
import gc
import tempfile
import shutil
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class TestMemoryStressTests(unittest.TestCase):
    """Extended memory stress tests to detect leaks in complex scenarios."""

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

    def test_detection_pipeline_extended_operation(self):
        """Test detection pipeline for 5+ minutes of continuous operation."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from contracts import Frame
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig, FilterConfig
        import numpy as np

        print("\n" + "="*60)
        print("Extended Detection Pipeline Test (5 minutes)")
        print("="*60)

        # Create detector
        filter_config = FilterConfig()
        detector_config = DetectorConfig(filters=filter_config)
        detector = ClassicalDetector(detector_config)

        # Start detection pool
        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: detector.detect(frame))
        pool.start(queue_size=6)

        # Get initial memory
        gc.collect()
        time.sleep(0.5)
        initial_memory = self.get_memory_mb()
        print(f"Initial memory: {initial_memory:.1f} MB")

        # Run for 5 minutes
        duration = 300  # 5 minutes
        start_time = time.time()
        frame_count = 0
        memory_samples = []

        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        while time.time() - start_time < duration:
            # Create frame with current timestamp
            timestamp = int(time.time() * 1e9)
            frame = Frame(
                image=image,
                t_capture_monotonic_ns=timestamp,
                t_capture_utc_ns=timestamp,
                t_received_monotonic_ns=timestamp,
                width=640,
                height=480,
                camera_id="stress_test"
            )

            pool.enqueue_frame("left", frame)
            frame_count += 1

            # Sample memory every 30 seconds
            if frame_count % 1800 == 0:  # ~60 FPS * 30 seconds
                gc.collect()
                current_memory = self.get_memory_mb()
                elapsed = time.time() - start_time
                growth = current_memory - initial_memory
                growth_pct = (growth / initial_memory) * 100

                memory_samples.append((elapsed, current_memory, growth_pct))
                print(f"  [{elapsed:>5.0f}s] {current_memory:>7.1f} MB "
                      f"(+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

            # Throttle slightly to avoid overwhelming
            time.sleep(0.01)

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        total_growth = final_memory - initial_memory
        growth_percent = (total_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{total_growth:.1f} MB, +{growth_percent:.1f}%)")
        print(f"Frames processed: {frame_count:,}")

        # Stop pool
        pool.stop()

        # Memory should not grow more than 15% over 5 minutes
        self.assertLess(
            growth_percent,
            15.0,
            f"Memory grew {growth_percent:.1f}% over 5 minutes. Possible leak."
        )

        print("✅ PASS: Memory stable over extended operation")

    def test_session_recorder_multiple_sessions(self):
        """Test SessionRecorder for memory leaks across multiple sessions."""
        from app.pipeline.recording.session_recorder import SessionRecorder
        from app.config import AppConfig
        import numpy as np
        import cv2

        print("\n" + "="*60)
        print("SessionRecorder Multiple Sessions Test")
        print("="*60)

        # Create config
        config = AppConfig()
        config.video_fps = 60
        config.video_codec = "MJPG"

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"Initial memory: {initial_memory:.1f} MB")

        # Create and destroy 20 recording sessions
        for session_num in range(20):
            recorder = SessionRecorder(config, self.temp_dir)

            # Start session
            session_dir, _ = recorder.start_session(
                session_name=f"stress_test_{session_num:03d}",
                pitch_id=f"pitch_{session_num:03d}",
                mode="test"
            )

            # Write 30 frames per session
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            timestamp_ns = int(time.time() * 1e9)

            for i in range(30):
                recorder.add_frame("left", frame, timestamp_ns + i * 16_666_667)
                recorder.add_frame("right", frame, timestamp_ns + i * 16_666_667)

            # Stop session
            recorder.stop_session()

            # Check memory every 5 sessions
            if (session_num + 1) % 5 == 0:
                gc.collect()
                current_memory = self.get_memory_mb()
                growth = current_memory - initial_memory
                growth_pct = (growth / initial_memory) * 100
                print(f"  Session {session_num+1:>2}/20: {current_memory:>7.1f} MB "
                      f"(+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        total_growth = final_memory - initial_memory
        growth_percent = (total_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{total_growth:.1f} MB, +{growth_percent:.1f}%)")

        # Memory should not grow more than 20% after 20 sessions
        self.assertLess(
            growth_percent,
            20.0,
            f"Memory grew {growth_percent:.1f}% after 20 sessions. Possible leak."
        )

        print("✅ PASS: SessionRecorder memory stable across sessions")

    def test_stereo_manager_extended_operation(self):
        """Test StereoManager for memory leaks during extended operation."""
        from app.pipeline.stereo.stereo_manager import StereoManager
        from contracts import Detection, Frame
        from app.config import AppConfig
        import numpy as np

        print("\n" + "="*60)
        print("StereoManager Extended Operation Test")
        print("="*60)

        # Create config
        config = AppConfig()

        # Create stereo manager
        manager = StereoManager(config)

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"Initial memory: {initial_memory:.1f} MB")

        # Process 5000 frame pairs
        num_frames = 5000

        for i in range(num_frames):
            timestamp = int(time.time() * 1e9) + i * 16_666_667

            # Create dummy detections (simulate detected baseball)
            left_detections = [
                Detection(
                    x=320 + i % 100,
                    y=240,
                    w=30,
                    h=30,
                    confidence=0.9,
                    label="baseball",
                    t_ns=timestamp
                )
            ]

            right_detections = [
                Detection(
                    x=300 + i % 100,
                    y=240,
                    w=30,
                    h=30,
                    confidence=0.9,
                    label="baseball",
                    t_ns=timestamp
                )
            ]

            # Process stereo
            manager.process_detections(left_detections, right_detections)

            # Sample memory every 1000 frames
            if (i + 1) % 1000 == 0:
                gc.collect()
                current_memory = self.get_memory_mb()
                growth = current_memory - initial_memory
                growth_pct = (growth / initial_memory) * 100
                print(f"  Frame {i+1:>5}/{num_frames}: {current_memory:>7.1f} MB "
                      f"(+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        total_growth = final_memory - initial_memory
        growth_percent = (total_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{total_growth:.1f} MB, +{growth_percent:.1f}%)")

        # Memory should not grow more than 15% after 5000 frames
        self.assertLess(
            growth_percent,
            15.0,
            f"Memory grew {growth_percent:.1f}% after 5000 frames. Possible leak."
        )

        print("✅ PASS: StereoManager memory stable during extended operation")

    def test_pitch_state_machine_multiple_pitches(self):
        """Test PitchStateMachineV2 for memory leaks across many pitches."""
        from app.pipeline.pitch_tracking_v2 import PitchStateMachineV2
        from contracts import StereoObservation
        from app.config import AppConfig

        print("\n" + "="*60)
        print("PitchStateMachine Multiple Pitches Test")
        print("="*60)

        # Create config
        config = AppConfig()

        # Create state machine
        state_machine = PitchStateMachineV2(config)

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"Initial memory: {initial_memory:.1f} MB")

        # Simulate 100 complete pitches
        num_pitches = 100

        for pitch_num in range(num_pitches):
            base_time = int(time.time() * 1e9) + pitch_num * 2_000_000_000  # 2 seconds apart

            # Simulate pitch trajectory (5 observations per pitch)
            for i in range(5):
                obs = StereoObservation(
                    t_ns=base_time + i * 33_000_000,  # 30 FPS
                    left=(100.0 + i * 10, 200.0),
                    right=(150.0 + i * 10, 200.0),
                    X=0.1 * i,
                    Y=0.5,
                    Z=10.0 - i * 0.5,
                    quality=0.9,
                    confidence=0.9,
                )
                state_machine.add_observation(obs)

            # Allow pitch to finalize
            time.sleep(0.05)

            # Process to advance state machine
            state_machine.process_frame(base_time + 1_000_000_000)

            # Sample memory every 20 pitches
            if (pitch_num + 1) % 20 == 0:
                gc.collect()
                current_memory = self.get_memory_mb()
                growth = current_memory - initial_memory
                growth_pct = (growth / initial_memory) * 100
                print(f"  Pitch {pitch_num+1:>3}/{num_pitches}: {current_memory:>7.1f} MB "
                      f"(+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        total_growth = final_memory - initial_memory
        growth_percent = (total_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{total_growth:.1f} MB, +{growth_percent:.1f}%)")

        # Memory should not grow more than 15% after 100 pitches
        self.assertLess(
            growth_percent,
            15.0,
            f"Memory grew {growth_percent:.1f}% after 100 pitches. Possible leak."
        )

        print("✅ PASS: PitchStateMachine memory stable across pitches")

    def test_rapid_start_stop_cycles(self):
        """Test for memory leaks during rapid start/stop cycles."""
        from app.pipeline.detection.threading_pool import DetectionThreadPool
        from detect.classical_detector import ClassicalDetector
        from detect.config import DetectorConfig, FilterConfig
        from contracts import Frame
        import numpy as np

        print("\n" + "="*60)
        print("Rapid Start/Stop Cycles Test (100 cycles)")
        print("="*60)

        gc.collect()
        initial_memory = self.get_memory_mb()
        initial_threads = threading.active_count()
        print(f"Initial: {initial_memory:.1f} MB, {initial_threads} threads")

        # Create detector once
        filter_config = FilterConfig()
        detector_config = DetectorConfig(filters=filter_config)
        detector = ClassicalDetector(detector_config)

        # Rapid start/stop cycles
        num_cycles = 100

        for cycle in range(num_cycles):
            # Create and start pool
            pool = DetectionThreadPool()
            pool.set_detect_callback(lambda label, frame: detector.detect(frame))
            pool.start(queue_size=6)

            # Process a few frames
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            timestamp = int(time.time() * 1e9)

            for i in range(10):
                frame = Frame(
                    image=image,
                    t_capture_monotonic_ns=timestamp + i * 16_666_667,
                    t_capture_utc_ns=timestamp + i * 16_666_667,
                    t_received_monotonic_ns=timestamp + i * 16_666_667,
                    width=640,
                    height=480,
                    camera_id="cycle_test"
                )
                pool.enqueue_frame("left", frame)

            time.sleep(0.05)

            # Stop pool
            pool.stop()
            time.sleep(0.05)

            # Sample every 20 cycles
            if (cycle + 1) % 20 == 0:
                gc.collect()
                current_memory = self.get_memory_mb()
                current_threads = threading.active_count()
                memory_growth = current_memory - initial_memory
                thread_growth = current_threads - initial_threads
                memory_growth_pct = (memory_growth / initial_memory) * 100

                print(f"  Cycle {cycle+1:>3}/{num_cycles}: {current_memory:>7.1f} MB "
                      f"(+{memory_growth:>5.1f} MB, +{memory_growth_pct:>5.1f}%), "
                      f"{current_threads} threads (+{thread_growth})")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        final_threads = threading.active_count()
        memory_growth = final_memory - initial_memory
        thread_growth = final_threads - initial_threads
        memory_growth_pct = (memory_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{memory_growth:.1f} MB, +{memory_growth_pct:.1f}%)")
        print(f"Threads: {initial_threads} → {final_threads} (+{thread_growth})")

        # Memory should not grow more than 10% after 100 cycles
        self.assertLess(
            memory_growth_pct,
            10.0,
            f"Memory grew {memory_growth_pct:.1f}% after 100 cycles. Possible leak."
        )

        # Threads should return to near-initial count
        self.assertLessEqual(
            thread_growth,
            3,
            f"Thread leak: {initial_threads} → {final_threads} (+{thread_growth} threads)"
        )

        print("✅ PASS: Memory and threads stable during rapid cycling")


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)

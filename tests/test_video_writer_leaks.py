"""Memory leak tests for video writing and camera capture.

These tests focus on potential leaks in:
- Video writer lifecycle (cv2.VideoWriter)
- Camera capture start/stop cycles
- Frame buffer management
"""

import unittest
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


class TestVideoWriterLeaks(unittest.TestCase):
    """Test video writer and camera capture for memory leaks."""

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

    def test_video_writer_create_destroy_cycles(self):
        """Test video writer for leaks during repeated create/destroy cycles."""
        import cv2
        import numpy as np

        print("\n" + "="*60)
        print("VideoWriter Create/Destroy Cycles Test")
        print("="*60)

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"Initial memory: {initial_memory:.1f} MB")

        # Test multiple codec types
        codecs = ["MJPG", "XVID"]
        num_cycles_per_codec = 25

        for codec in codecs:
            fourcc = cv2.VideoWriter_fourcc(*codec)

            for cycle in range(num_cycles_per_codec):
                # Create video writer
                video_path = self.temp_dir / f"{codec}_{cycle:03d}.avi"
                writer = cv2.VideoWriter(
                    str(video_path),
                    fourcc,
                    60.0,  # FPS
                    (640, 480),
                    True
                )

                # Write 30 frames
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                for i in range(30):
                    writer.write(frame)

                # Release writer
                writer.release()

                # Delete video file to save space
                if video_path.exists():
                    video_path.unlink()

            # Check memory after each codec
            gc.collect()
            current_memory = self.get_memory_mb()
            growth = current_memory - initial_memory
            growth_pct = (growth / initial_memory) * 100
            print(f"  After {num_cycles_per_codec} cycles of {codec}: "
                  f"{current_memory:>7.1f} MB (+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        total_growth = final_memory - initial_memory
        growth_percent = (total_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{total_growth:.1f} MB, +{growth_percent:.1f}%)")

        # Memory should not grow more than 15%
        self.assertLess(
            growth_percent,
            15.0,
            f"Memory grew {growth_percent:.1f}% after video writer cycles. Possible leak."
        )

        print("✅ PASS: VideoWriter memory stable across cycles")

    def test_video_writer_large_file_cycles(self):
        """Test video writer with larger files (more frames)."""
        import cv2
        import numpy as np

        print("\n" + "="*60)
        print("VideoWriter Large File Cycles Test")
        print("="*60)

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"Initial memory: {initial_memory:.1f} MB")

        # Create 10 larger video files
        num_files = 10
        frames_per_file = 300  # 5 seconds at 60 FPS

        fourcc = cv2.VideoWriter_fourcc(*"MJPG")

        for file_num in range(num_files):
            video_path = self.temp_dir / f"large_{file_num:03d}.avi"

            # Create writer
            writer = cv2.VideoWriter(
                str(video_path),
                fourcc,
                60.0,
                (1280, 720),  # Higher resolution
                True
            )

            # Write frames
            for frame_num in range(frames_per_file):
                # Generate frame with some content
                frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
                writer.write(frame)

            # Release and check memory
            writer.release()

            # Delete to save space
            if video_path.exists():
                video_path.unlink()

            # Sample memory every 2 files
            if (file_num + 1) % 2 == 0:
                gc.collect()
                current_memory = self.get_memory_mb()
                growth = current_memory - initial_memory
                growth_pct = (growth / initial_memory) * 100
                print(f"  File {file_num+1:>2}/{num_files}: {current_memory:>7.1f} MB "
                      f"(+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        total_growth = final_memory - initial_memory
        growth_percent = (total_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{total_growth:.1f} MB, +{growth_percent:.1f}%)")

        # Memory should not grow more than 20% for larger files
        self.assertLess(
            growth_percent,
            20.0,
            f"Memory grew {growth_percent:.1f}% with large files. Possible leak."
        )

        print("✅ PASS: VideoWriter memory stable with large files")

    def test_simulated_camera_lifecycle(self):
        """Test simulated camera for memory leaks during start/stop cycles."""
        from capture.simulated_camera import SimulatedCamera

        print("\n" + "="*60)
        print("Simulated Camera Lifecycle Test")
        print("="*60)

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"Initial memory: {initial_memory:.1f} MB")

        num_cycles = 30

        for cycle in range(num_cycles):
            # Create camera
            camera = SimulatedCamera(camera_id=f"sim_cycle_{cycle}")

            # Start camera
            camera.start_capture()
            time.sleep(0.1)

            # Grab some frames
            for i in range(30):
                frame = camera.get_frame()
                if frame is None:
                    break

            # Stop camera
            camera.stop_capture()
            camera.release()

            # Sample every 10 cycles
            if (cycle + 1) % 10 == 0:
                gc.collect()
                current_memory = self.get_memory_mb()
                growth = current_memory - initial_memory
                growth_pct = (growth / initial_memory) * 100
                print(f"  Cycle {cycle+1:>2}/{num_cycles}: {current_memory:>7.1f} MB "
                      f"(+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        total_growth = final_memory - initial_memory
        growth_percent = (total_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{total_growth:.1f} MB, +{growth_percent:.1f}%)")

        # Memory should not grow more than 10%
        self.assertLess(
            growth_percent,
            10.0,
            f"Memory grew {growth_percent:.1f}% during camera cycles. Possible leak."
        )

        print("✅ PASS: SimulatedCamera memory stable during lifecycle")

    def test_frame_buffer_management(self):
        """Test that frame buffers don't accumulate in memory."""
        from contracts import Frame
        import numpy as np

        print("\n" + "="*60)
        print("Frame Buffer Management Test")
        print("="*60)

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"Initial memory: {initial_memory:.1f} MB")

        # Create and discard 10,000 frames
        num_frames = 10000

        for i in range(num_frames):
            # Create frame
            image = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
            timestamp = int(time.time() * 1e9) + i * 16_666_667

            frame = Frame(
                image=image,
                t_capture_monotonic_ns=timestamp,
                t_capture_utc_ns=timestamp,
                t_received_monotonic_ns=timestamp,
                width=1280,
                height=720,
                camera_id="buffer_test"
            )

            # Immediately discard (frame goes out of scope)
            del frame
            del image

            # Force GC periodically
            if i % 1000 == 0 and i > 0:
                gc.collect()
                current_memory = self.get_memory_mb()
                growth = current_memory - initial_memory
                growth_pct = (growth / initial_memory) * 100
                print(f"  Frame {i:>5}/{num_frames}: {current_memory:>7.1f} MB "
                      f"(+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        total_growth = final_memory - initial_memory
        growth_percent = (total_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{total_growth:.1f} MB, +{growth_percent:.1f}%)")

        # Memory should return to near-initial (allow 10% for caching)
        self.assertLess(
            growth_percent,
            10.0,
            f"Memory grew {growth_percent:.1f}% after frame creation. Buffer leak?"
        )

        print("✅ PASS: Frame buffers properly released")

    def test_concurrent_video_writers(self):
        """Test multiple video writers running concurrently."""
        import cv2
        import numpy as np
        import threading

        print("\n" + "="*60)
        print("Concurrent Video Writers Test")
        print("="*60)

        gc.collect()
        initial_memory = self.get_memory_mb()
        print(f"Initial memory: {initial_memory:.1f} MB")

        def write_video(writer_id: int, num_frames: int = 100):
            """Write video in a thread."""
            video_path = self.temp_dir / f"concurrent_{writer_id:03d}.avi"
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")

            writer = cv2.VideoWriter(
                str(video_path),
                fourcc,
                60.0,
                (640, 480),
                True
            )

            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

            for i in range(num_frames):
                writer.write(frame)
                time.sleep(0.001)  # Simulate real-time writing

            writer.release()

            # Clean up
            if video_path.exists():
                video_path.unlink()

        # Run 5 concurrent writers, 4 times
        for batch in range(4):
            threads = []

            for writer_id in range(5):
                thread = threading.Thread(
                    target=write_video,
                    args=(batch * 5 + writer_id, 100)
                )
                thread.start()
                threads.append(thread)

            # Wait for all to complete
            for thread in threads:
                thread.join()

            # Check memory after each batch
            gc.collect()
            current_memory = self.get_memory_mb()
            growth = current_memory - initial_memory
            growth_pct = (growth / initial_memory) * 100
            print(f"  Batch {batch+1}/4 (5 concurrent writers): "
                  f"{current_memory:>7.1f} MB (+{growth:>5.1f} MB, +{growth_pct:>5.1f}%)")

        # Final check
        gc.collect()
        time.sleep(0.5)
        final_memory = self.get_memory_mb()
        total_growth = final_memory - initial_memory
        growth_percent = (total_growth / initial_memory) * 100

        print(f"\nFinal: {initial_memory:.1f} MB → {final_memory:.1f} MB "
              f"(+{total_growth:.1f} MB, +{growth_percent:.1f}%)")

        # Memory should not grow more than 20% with concurrent writers
        self.assertLess(
            growth_percent,
            20.0,
            f"Memory grew {growth_percent:.1f}% with concurrent writers. Possible leak."
        )

        print("✅ PASS: Memory stable with concurrent video writers")


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)

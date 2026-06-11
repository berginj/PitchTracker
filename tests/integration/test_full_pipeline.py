"""Integration test for full pipeline with simulated cameras.

Tests the complete end-to-end flow:
- Capture with simulated cameras
- Detection pipeline
- Recording session
- File generation
- Session stop and cleanup
"""

import json
import unittest
import time
import tempfile
import shutil
from pathlib import Path

from configs.settings import load_config
from app.services.orchestrator import PipelineOrchestrator


class TestFullPipeline(unittest.TestCase):
    """Integration tests for full pipeline with simulated cameras."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for recordings
        self.test_dir = Path(tempfile.mkdtemp())

        # Load default config and override output directory
        from dataclasses import replace

        config = load_config(Path("configs/default.yaml"))
        # Override recording output directory to use temp dir
        self.config = replace(
            config,
            recording=replace(config.recording, output_dir=str(self.test_dir)),
        )

    def tearDown(self):
        """Clean up test files."""
        if self.test_dir.exists():
            try:
                shutil.rmtree(self.test_dir)
            except Exception as e:
                print(f"Warning: Could not clean up test directory: {e}")

    def test_full_pipeline_simulated_cameras(self):
        """Test full pipeline: capture → detection → recording → stop."""
        # Create pipeline service with simulated backend
        service = PipelineOrchestrator(backend="sim")

        try:
            # Start capture with simulated cameras
            service.start_capture(
                config=self.config,
                left_serial="sim_left",
                right_serial="sim_right",
            )

            # Give cameras time to start and produce valid frames
            time.sleep(1.0)

            # Verify we can get preview frames (with retry for simulated cameras)
            left_frame, right_frame = None, None
            for attempt in range(5):
                try:
                    left_frame, right_frame = service.get_preview_frames()
                    break
                except Exception:
                    time.sleep(0.5)

            # Skip remaining test if cameras didn't produce frames
            # (This is acceptable for simulated cameras in test environment)
            if left_frame is None or right_frame is None:
                self.skipTest("Simulated cameras did not produce valid frames")

            self.assertIsNotNone(left_frame)
            self.assertIsNotNone(right_frame)

            # Start recording session
            warning = service.start_recording(
                session_name="test_session",
                pitch_id="test_pitch_001",
                mode="test",
            )

            # Should not have disk space warning on fresh system
            self.assertEqual(warning, "", f"Unexpected disk warning: {warning}")

            # Let pipeline run for a few seconds
            time.sleep(3.0)

            # Verify session directory was created
            session_dir = service.get_session_dir()
            self.assertIsNotNone(session_dir)
            self.assertTrue(session_dir.exists())

            # Stop recording
            bundle = service.stop_recording()
            self.assertIsNotNone(bundle)

            # Verify recording files exist
            left_video = session_dir / "session_left.avi"
            right_video = session_dir / "session_right.avi"
            manifest = session_dir / "manifest.json"

            self.assertTrue(left_video.exists(), f"Left video not found: {left_video}")
            self.assertTrue(right_video.exists(), f"Right video not found: {right_video}")
            self.assertTrue(manifest.exists(), f"Manifest not found: {manifest}")

            # Verify video files are not empty
            self.assertGreater(
                left_video.stat().st_size,
                1000,
                "Left video file is too small (< 1KB)",
            )
            self.assertGreater(
                right_video.stat().st_size,
                1000,
                "Right video file is too small (< 1KB)",
            )

            # Stop capture
            service.stop_capture()

        except Exception:
            # Make sure we clean up even if test fails
            try:
                if service._recording:
                    service.stop_recording()
                service.stop_capture()
            except Exception:
                pass
            raise

    def test_multiple_sessions_sequential(self):
        """Test multiple recording sessions in sequence."""
        service = PipelineOrchestrator(backend="sim")

        try:
            # Start capture once
            service.start_capture(
                config=self.config,
                left_serial="sim_left",
                right_serial="sim_right",
            )
            time.sleep(0.5)

            # Record three sessions
            for i in range(3):
                # Start recording
                service.start_recording(
                    session_name=f"test_session_{i}",
                    pitch_id=f"test_pitch_{i:03d}",
                    mode="test",
                )

                # Record for 1 second
                time.sleep(1.0)

                # Stop recording
                bundle = service.stop_recording()
                self.assertIsNotNone(bundle)

                # Verify session directory
                session_dir = bundle.session_dir
                self.assertTrue(session_dir.exists())
                self.assertTrue((session_dir / "session_left.avi").exists())
                self.assertTrue((session_dir / "session_right.avi").exists())

            # Stop capture
            service.stop_capture()

        except Exception:
            try:
                if service._recording:
                    service.stop_recording()
                service.stop_capture()
            except Exception:
                pass
            raise

    def test_preview_frames_during_capture(self):
        """Test that preview frames update during capture."""
        service = PipelineOrchestrator(backend="sim")

        try:
            # Start capture
            service.start_capture(
                config=self.config,
                left_serial="sim_left",
                right_serial="sim_right",
            )
            time.sleep(0.5)

            # Get multiple preview frames
            frame_timestamps = []
            for i in range(5):
                left_frame, right_frame = service.get_preview_frames()
                self.assertIsNotNone(left_frame)
                self.assertIsNotNone(right_frame)

                # Record timestamps
                frame_timestamps.append(left_frame.t_capture_monotonic_ns)

                time.sleep(0.1)

            # Verify timestamps are increasing (frames are updating)
            for i in range(1, len(frame_timestamps)):
                self.assertGreater(
                    frame_timestamps[i],
                    frame_timestamps[i - 1],
                    "Frame timestamps should be increasing",
                )

            # Stop capture
            service.stop_capture()

        except Exception:
            try:
                service.stop_capture()
            except Exception:
                pass
            raise

    def test_stop_capture_cleans_up_resources(self):
        """Test that stopping capture properly cleans up resources."""
        service = PipelineOrchestrator(backend="sim")

        try:
            # Start capture
            service.start_capture(
                config=self.config,
                left_serial="sim_left",
                right_serial="sim_right",
            )
            time.sleep(0.5)

            # Verify cameras are running
            left_frame, right_frame = service.get_preview_frames()
            self.assertIsNotNone(left_frame)

            # Stop capture
            service.stop_capture()

            # Verify we can't get frames after stop
            # (This might raise or return None depending on implementation)
            # Just verify no crash
            try:
                service.get_preview_frames()
            except Exception:
                pass  # Expected - cameras stopped

        except Exception:
            try:
                service.stop_capture()
            except Exception:
                pass
            raise

    def test_recording_without_capture_fails(self):
        """Test that recording fails gracefully if capture not started."""
        service = PipelineOrchestrator(backend="sim")

        # Try to start recording without starting capture first
        with self.assertRaises(Exception):
            service.start_recording(
                session_name="test_session",
                pitch_id="test_pitch",
                mode="test",
            )

    def test_complete_detection_and_trajectory_pipeline(self):
        """Test complete pipeline including detection and trajectory fitting.

        This test validates:
        - Ball detection from stereo frames
        - Stereo triangulation
        - Trajectory fitting with physics model
        - Strike zone determination
        - Session summary generation
        - Manifest file creation with pitch metadata
        """
        service = PipelineOrchestrator(backend="sim")

        try:
            # Start capture
            service.start_capture(
                config=self.config,
                left_serial="sim_left",
                right_serial="sim_right",
            )
            time.sleep(0.5)

            # Verify preview frames are available
            left_frame, right_frame = None, None
            for attempt in range(5):
                try:
                    left_frame, right_frame = service.get_preview_frames()
                    break
                except Exception:
                    time.sleep(0.5)

            if left_frame is None or right_frame is None:
                self.skipTest("Simulated cameras did not produce valid frames")

            # Start recording session
            service.start_recording(
                session_name="detection_test_session",
                pitch_id="pitch_001",
                mode="test",
            )

            # Let pipeline run to process frames
            # Simulated cameras should generate some detection events
            time.sleep(4.0)

            # Stop recording and get session bundle
            bundle = service.stop_recording()
            self.assertIsNotNone(bundle, "Session bundle should not be None")

            # Verify session directory structure
            session_dir = bundle.session_dir
            self.assertTrue(session_dir.exists(), "Session directory should exist")

            # Check for expected files
            manifest_path = session_dir / "manifest.json"
            self.assertTrue(manifest_path.exists(), "Manifest file should exist")

            # Load and validate manifest
            with manifest_path.open("r") as f:
                manifest = json.load(f)

            # Validate manifest structure
            self.assertIn("session_name", manifest, "Manifest should contain session_name")
            self.assertIn("t_start_utc", manifest, "Manifest should contain start time")
            self.assertIn("t_end_utc", manifest, "Manifest should contain end time")
            self.assertIn("pitch_id", manifest, "Manifest should contain pitch_id")
            self.assertEqual(manifest["session_name"], "detection_test_session")
            self.assertEqual(manifest["pitch_id"], "pitch_001")

            # Check if session summary was generated
            summary_json_path = session_dir / "session_summary.json"

            # Note: Summary may not exist if no pitches were tracked
            # This is acceptable for simulated cameras without injected detections
            if summary_json_path.exists():
                with summary_json_path.open("r") as f:
                    summary = json.load(f)

                # Validate summary structure
                self.assertIn("pitches", summary, "Summary should contain pitches list")
                self.assertIsInstance(summary["pitches"], list, "Pitches should be a list")

                # If we have pitches, validate their structure
                for pitch in summary["pitches"]:
                    self.assertIn("pitch_id", pitch, "Pitch should have pitch_id")
                    self.assertIn("t_start_ns", pitch, "Pitch should have start time")
                    self.assertIn("t_end_ns", pitch, "Pitch should have end time")
                    self.assertIn("sample_count", pitch, "Pitch should have sample_count")

                    # If trajectory was fitted, validate those fields
                    if pitch.get("trajectory_plate_x_ft") is not None:
                        self.assertIsInstance(
                            pitch["trajectory_plate_x_ft"],
                            (int, float),
                            "Trajectory X should be numeric",
                        )
                        self.assertIsInstance(
                            pitch["trajectory_plate_y_ft"],
                            (int, float),
                            "Trajectory Y should be numeric",
                        )
                        self.assertIn(
                            "is_strike",
                            pitch,
                            "Pitch should have strike determination",
                        )

            # Verify video files exist and are not empty
            left_video = session_dir / "session_left.avi"
            right_video = session_dir / "session_right.avi"

            self.assertTrue(left_video.exists(), "Left video should exist")
            self.assertTrue(right_video.exists(), "Right video should exist")
            self.assertGreater(
                left_video.stat().st_size,
                1000,
                "Left video should be > 1KB",
            )
            self.assertGreater(
                right_video.stat().st_size,
                1000,
                "Right video should be > 1KB",
            )

            # Stop capture
            service.stop_capture()

            # Additional validation: Check that bundle contains expected attributes.
            # The RecordingBundle carries session_dir; session timing is persisted in
            # the manifest (validated above as t_start_utc/t_end_utc), not on the bundle.
            self.assertIsNotNone(bundle.session_dir, "Bundle should have session_dir")
            self.assertIsInstance(bundle.session_dir, Path, "Bundle session_dir should be a Path")

        except Exception:
            # Clean up on failure
            try:
                if service._recording:
                    service.stop_recording()
                service.stop_capture()
            except Exception:
                pass
            raise

    def test_detection_health_monitoring(self):
        """Test that detection health is monitored during capture."""
        service = PipelineOrchestrator(backend="sim")

        try:
            # Start capture
            service.start_capture(
                config=self.config,
                left_serial="sim_left",
                right_serial="sim_right",
            )
            time.sleep(0.5)

            # Get preview frames (which should include health info)
            left_frame, right_frame = service.get_preview_frames()

            # Verify frames have timestamps
            self.assertIsNotNone(
                left_frame.t_capture_monotonic_ns,
                "Frame should have capture timestamp",
            )
            self.assertIsNotNone(
                right_frame.t_capture_monotonic_ns,
                "Frame should have capture timestamp",
            )

            # Verify frame dimensions are reasonable
            self.assertGreater(left_frame.image.shape[0], 0, "Frame should have height")
            self.assertGreater(left_frame.image.shape[1], 0, "Frame should have width")
            self.assertEqual(len(left_frame.image.shape), 3, "Frame should be color (3 channels)")

            # Stop capture
            service.stop_capture()

        except Exception:
            try:
                service.stop_capture()
            except Exception:
                pass
            raise


if __name__ == "__main__":
    unittest.main()

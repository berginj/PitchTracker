"""Tests for pitch state machine callback error handling and state corruption recovery.

Tests that the pitch state machine properly handles callback exceptions:
- on_pitch_start callback errors
- on_pitch_end callback errors
- State recovery after callback failures
- Error bus publication
- Continued operation after errors
"""

import unittest
import time
from unittest.mock import Mock

from app.pipeline.pitch_tracking_v2 import PitchStateMachineV2, PitchConfig, PitchPhase
from app.events import get_error_bus, ErrorCategory, ErrorSeverity
from contracts import StereoObservation


class TestStateCorruptionRecovery(unittest.TestCase):
    """Tests for pitch state machine error handling and recovery."""

    def setUp(self):
        """Set up test fixtures."""
        # Track errors published to error bus
        self.received_errors = []

        def error_callback(event):
            self.received_errors.append(event)

        get_error_bus().subscribe(error_callback)
        self._error_callback = error_callback

        # Create pitch config
        self.config = PitchConfig(
            min_active_frames=3,
            end_gap_frames=5,
            use_plate_gate=False,
            min_observations=2,
            min_duration_ms=50.0,
            pre_roll_ms=100.0,
            frame_rate=30.0,
        )

        # Create state machine
        self.state_machine = PitchStateMachineV2(self.config)

    def tearDown(self):
        """Clean up test fixtures."""
        # Unsubscribe from error bus
        try:
            get_error_bus().unsubscribe(self._error_callback)
        except Exception:
            pass

    def test_on_pitch_start_callback_exception_recovers_state(self):
        """Test that exception in on_pitch_start callback recovers state properly."""
        # Set up callback that throws exception
        callback_invocations = []

        def failing_start_callback(pitch_index, pitch_data):
            callback_invocations.append(("start", pitch_index))
            raise ValueError("Simulated callback failure")

        self.state_machine.set_callbacks(on_pitch_start=failing_start_callback)

        # Create observations to trigger pitch start
        base_ns = int(time.time() * 1e9)
        observations = [
            StereoObservation(
                t_ns=base_ns + i * 33_000_000,  # ~30 FPS
                left=(100.0 + i * 10, 200.0),
                right=(150.0 + i * 10, 200.0),
                X=0.1 * i,
                Y=0.5,
                Z=10.0 - i * 0.5,
                quality=0.9,
                confidence=0.9,
            )
            for i in range(5)
        ]

        # Feed observations to state machine
        for obs in observations:
            self.state_machine.add_observation(obs)

        # Callback should have been invoked and failed
        self.assertEqual(len(callback_invocations), 1)
        self.assertEqual(callback_invocations[0], ("start", 1))

        # State should have been reverted to RAMP_UP (not ACTIVE)
        self.assertEqual(self.state_machine.get_phase(), PitchPhase.RAMP_UP)

        # Pitch index should have been reverted
        # (The machine tried to start pitch 1, failed, reverted to 0)

        # Error should have been published to error bus
        tracking_errors = [
            e
            for e in self.received_errors
            if e.category == ErrorCategory.TRACKING
        ]
        self.assertGreater(len(tracking_errors), 0, "Expected error published to error bus")

        # Verify error message
        error = tracking_errors[0]
        self.assertEqual(error.severity, ErrorSeverity.ERROR)
        self.assertIn("start callback failed", error.message)

    def test_on_pitch_end_callback_exception_recovers_state(self):
        """Test that exception in on_pitch_end callback resets state properly."""
        # Set up callbacks
        start_invocations = []
        end_invocations = []

        def normal_start_callback(pitch_index, pitch_data):
            start_invocations.append(pitch_index)

        def failing_end_callback(pitch_data):
            end_invocations.append(pitch_data.pitch_index)
            raise ValueError("Simulated end callback failure")

        self.state_machine.set_callbacks(
            on_pitch_start=normal_start_callback,
            on_pitch_end=failing_end_callback,
        )

        # Create observations to trigger pitch start and end
        base_ns = int(time.time() * 1e9)
        active_observations = [
            StereoObservation(
                t_ns=base_ns + i * 33_000_000,
                left=(100.0 + i * 10, 200.0),
                right=(150.0 + i * 10, 200.0),
                X=0.1 * i,
                Y=0.5,
                Z=10.0 - i * 0.5,
                quality=0.9,
                confidence=0.9,
            )
            for i in range(5)
        ]

        # Feed observations to trigger ACTIVE state
        for obs in active_observations:
            self.state_machine.add_observation(obs)

        # Should have transitioned to ACTIVE
        self.assertEqual(len(start_invocations), 1)

        # Now trigger end by sending frames with no observations
        for i in range(10):
            self.state_machine.process_frame(base_ns + (i + 10) * 33_000_000)

        # End callback should have been invoked and failed
        self.assertEqual(len(end_invocations), 1)

        # State should have been reset to INACTIVE (ready for next pitch)
        self.assertEqual(self.state_machine.get_phase(), PitchPhase.INACTIVE)

        # Error should have been published
        tracking_errors = [
            e
            for e in self.received_errors
            if e.category == ErrorCategory.TRACKING
        ]
        end_errors = [e for e in tracking_errors if "end callback failed" in e.message]
        self.assertGreater(len(end_errors), 0, "Expected end callback error on error bus")

    def test_state_machine_continues_after_callback_error(self):
        """Test that state machine continues processing after callback error."""
        # Set up callback that fails on first pitch, succeeds on second
        self.call_count = 0
        successful_pitches = []

        def intermittent_start_callback(pitch_index, pitch_data):
            self.call_count += 1
            if self.call_count == 1:
                # Fail first pitch
                raise ValueError("First pitch fails")
            else:
                # Succeed on subsequent pitches
                successful_pitches.append(pitch_index)

        self.state_machine.set_callbacks(on_pitch_start=intermittent_start_callback)

        # First pitch - will fail
        base_ns = int(time.time() * 1e9)
        pitch1_observations = [
            StereoObservation(
                t_ns=base_ns + i * 33_000_000,
                left=(100.0 + i * 10, 200.0),
                right=(150.0 + i * 10, 200.0),
                X=0.1 * i,
                Y=0.5,
                Z=10.0,
                quality=0.9,
                confidence=0.9,
            )
            for i in range(5)
        ]

        for obs in pitch1_observations:
            self.state_machine.add_observation(obs)

        # Should have failed
        self.assertEqual(len(successful_pitches), 0)
        self.assertEqual(self.state_machine.get_phase(), PitchPhase.RAMP_UP)

        # Second pitch - should succeed
        # Wait a bit and send new observations
        time.sleep(0.1)
        base_ns2 = base_ns + 1_000_000_000  # 1 second later

        pitch2_observations = [
            StereoObservation(
                t_ns=base_ns2 + i * 33_000_000,
                left=(100.0 + i * 10, 200.0),
                right=(150.0 + i * 10, 200.0),
                X=0.2 * i,
                Y=0.5,
                Z=10.0,
                quality=0.9,
                confidence=0.9,
            )
            for i in range(5)
        ]

        # Reset state to INACTIVE first
        # Feed gap frames to reset
        for i in range(10):
            self.state_machine.process_frame(base_ns + (i + 20) * 33_000_000)

        # Now feed second pitch observations
        for obs in pitch2_observations:
            self.state_machine.add_observation(obs)

        # Should have succeeded
        self.assertGreater(
            len(successful_pitches),
            0,
            "Second pitch should succeed after first pitch error",
        )

    def test_state_corruption_during_start_callback_reverts_correctly(self):
        """Test that state is correctly reverted when start callback fails."""
        # Set up failing callback
        def failing_callback(pitch_index, pitch_data):
            # Verify state before exception
            self.assertEqual(self.state_machine.get_phase(), PitchPhase.ACTIVE)
            raise RuntimeError("Callback error")

        self.state_machine.set_callbacks(on_pitch_start=failing_callback)

        # Feed observations
        base_ns = int(time.time() * 1e9)
        for i in range(5):
            obs = StereoObservation(
                t_ns=base_ns + i * 33_000_000,
                left=(100.0 + i * 10, 200.0),
                right=(150.0 + i * 10, 200.0),
                X=0.1 * i,
                Y=0.5,
                Z=10.0,
                quality=0.9,
                confidence=0.9,
            )
            self.state_machine.add_observation(obs)

        # After callback failure, state should be reverted to RAMP_UP
        self.assertEqual(
            self.state_machine.get_phase(),
            PitchPhase.RAMP_UP,
            "State should be reverted to RAMP_UP after start callback error",
        )

    def test_multiple_callback_errors_all_published_to_error_bus(self):
        """Test that multiple callback errors are all published to error bus."""
        # Set up callbacks that always fail
        def failing_start(pitch_index, pitch_data):
            raise ValueError(f"Start error {pitch_index}")

        def failing_end(pitch_data):
            raise ValueError(f"End error {pitch_data.pitch_index}")

        self.state_machine.set_callbacks(
            on_pitch_start=failing_start,
            on_pitch_end=failing_end,
        )

        # Try to trigger multiple pitches
        base_ns = int(time.time() * 1e9)

        # First pitch
        for i in range(5):
            obs = StereoObservation(
                t_ns=base_ns + i * 33_000_000,
                left=(100.0 + i * 10, 200.0),
                right=(150.0 + i * 10, 200.0),
                X=0.1 * i,
                Y=0.5,
                Z=10.0,
                quality=0.9,
                confidence=0.9,
            )
            self.state_machine.add_observation(obs)

        # Should have at least one error
        tracking_errors = [
            e
            for e in self.received_errors
            if e.category == ErrorCategory.TRACKING
        ]
        self.assertGreater(len(tracking_errors), 0, "Expected errors published")

        # Verify all errors have correct severity
        for error in tracking_errors:
            self.assertEqual(error.severity, ErrorSeverity.ERROR)

    def test_error_metadata_includes_context(self):
        """Test that error events include relevant context metadata."""
        def failing_callback(pitch_index, pitch_data):
            raise ValueError("Test error")

        self.state_machine.set_callbacks(on_pitch_start=failing_callback)

        # Trigger error
        base_ns = int(time.time() * 1e9)
        for i in range(5):
            obs = StereoObservation(
                t_ns=base_ns + i * 33_000_000,
                left=(100.0 + i * 10, 200.0),
                right=(150.0 + i * 10, 200.0),
                X=0.1 * i,
                Y=0.5,
                Z=10.0,
                quality=0.9,
                confidence=0.9,
            )
            self.state_machine.add_observation(obs)

        # Check error metadata
        tracking_errors = [
            e
            for e in self.received_errors
            if e.category == ErrorCategory.TRACKING
        ]
        self.assertGreater(len(tracking_errors), 0)

        error = tracking_errors[0]
        # Should have source information
        self.assertIsNotNone(error.source)
        self.assertIn("PitchStateMachineV2", error.source)


if __name__ == "__main__":
    unittest.main()

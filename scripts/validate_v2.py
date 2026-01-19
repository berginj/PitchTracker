"""Validation script for Pitch Tracking V2 integration.

Verifies core functionality without requiring pytest:
- Pre-roll capture
- Ramp-up observation capture
- Thread safety
- Timing accuracy
- Data validation
"""

import sys
import threading
import time
from typing import List, Optional

# Add project root to path
sys.path.insert(0, ".")

from app.pipeline.pitch_tracking_v2 import (
    PitchConfig,
    PitchData,
    PitchPhase,
    PitchStateMachineV2,
)
from contracts import Frame, StereoObservation


# Test helpers
def create_test_frame(timestamp_ns: int, camera_id: str = "test_cam") -> Frame:
    """Create test frame with minimal data."""
    return Frame(
        camera_id=camera_id,
        frame_index=0,
        t_capture_monotonic_ns=timestamp_ns,
        image=None,
        width=640,
        height=480,
        pixfmt="RGB",
    )


def create_test_observation(timestamp_ns: int) -> StereoObservation:
    """Create test observation."""
    return StereoObservation(
        t_ns=timestamp_ns,
        left=(0.0, 0.0),
        right=(0.0, 0.0),
        X=0.0,
        Y=0.0,
        Z=0.0,
        quality=1.0,
    )


# Test implementations
class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error: Optional[str] = None

    def __str__(self):
        status = "[PASS]" if self.passed else "[FAIL]"
        msg = f"{status}: {self.name}"
        if self.error:
            msg += f"\n    Error: {self.error}"
        return msg


def test_basic_initialization() -> TestResult:
    """Test basic initialization."""
    result = TestResult("Basic Initialization")
    try:
        config = PitchConfig(min_active_frames=5, frame_rate=30.0)
        sm = PitchStateMachineV2(config)

        assert sm.get_phase() == PitchPhase.INACTIVE
        assert sm.get_pitch_index() == 0

        result.passed = True
    except Exception as e:
        result.error = str(e)
    return result


def test_pre_roll_buffering() -> TestResult:
    """Test pre-roll frames are buffered before pitch starts."""
    result = TestResult("Pre-roll Buffering")
    try:
        config = PitchConfig(
            min_active_frames=3,
            pre_roll_ms=100.0,
            frame_rate=30.0,
        )
        sm = PitchStateMachineV2(config)

        captured_pre_roll: List = []

        def on_start(idx, data):
            nonlocal captured_pre_roll
            captured_pre_roll = data.pre_roll_frames

        sm.set_callbacks(on_pitch_start=on_start)

        # Buffer 10 frames before any detection
        for i in range(10):
            frame = create_test_frame(i * 33_000_000)
            sm.buffer_frame("left", frame)
            sm.update(frame.t_capture_monotonic_ns, 0, 0, 0)

        # Trigger pitch start with detections
        for i in range(10, 15):
            frame = create_test_frame(i * 33_000_000)
            sm.buffer_frame("left", frame)
            sm.update(frame.t_capture_monotonic_ns, 1, 1, 1)

        # Verify pre-roll was captured
        assert len(captured_pre_roll) > 0, "Pre-roll frames should be captured"
        assert len(captured_pre_roll) >= 3, f"Should capture at least 3 pre-roll frames, got {len(captured_pre_roll)}"

        result.passed = True
    except Exception as e:
        result.error = str(e)
    return result


def test_ramp_up_observations() -> TestResult:
    """Test observations during ramp-up are captured."""
    result = TestResult("Ramp-up Observation Capture")
    try:
        config = PitchConfig(
            min_active_frames=5,
            min_duration_ms=100.0,  # Need minimum duration
            frame_rate=30.0
        )
        sm = PitchStateMachineV2(config)

        ramp_up_obs: List = []
        start_called = False

        def on_start(idx, data):
            nonlocal ramp_up_obs, start_called
            start_called = True
            ramp_up_obs = data.observations

        sm.set_callbacks(on_pitch_start=on_start)

        # Trigger ramp-up, then add observations during ramp-up
        # Need 5 frames at 33ms apart = 132ms duration to exceed 100ms minimum
        # Plus one more frame to trigger the transition
        for i in range(6):
            # Update state first to enter/stay in RAMP_UP phase
            sm.update(i * 33_000_000, 1, 1, 1)
            # Now add observation (should be stored in ramp-up)
            obs = create_test_observation(i * 33_000_000)
            sm.add_observation(obs)

        # Debug: Check event log if callback wasn't called
        if not start_called:
            events = sm.get_event_log()
            last_events = [e for e in events[-10:]]
            raise AssertionError(f"Pitch start callback should have been called (phase={sm.get_phase().value}, events={last_events})")

        # Verify observations were captured (should have 5 from ramp-up + 1 from post-transition)
        assert len(ramp_up_obs) >= 5, f"Should capture at least 5 observations from ramp-up, got {len(ramp_up_obs)}"

        result.passed = True
    except Exception as e:
        result.error = str(e)
    return result


def test_accurate_timing() -> TestResult:
    """Test start/end times are accurate."""
    result = TestResult("Accurate Timing")
    try:
        config = PitchConfig(
            min_active_frames=3,
            end_gap_frames=3,
            min_duration_ms=100.0,
            frame_rate=30.0,
        )
        sm = PitchStateMachineV2(config)

        pitch_start_ns: Optional[int] = None
        pitch_end_ns: Optional[int] = None
        first_detection = 100_000_000  # 100ms
        last_detection_time = 0

        def on_start(idx, data):
            nonlocal pitch_start_ns
            pitch_start_ns = data.start_ns

        def on_end(data):
            nonlocal pitch_end_ns
            pitch_end_ns = data.end_ns

        sm.set_callbacks(on_pitch_start=on_start, on_pitch_end=on_end)

        # Trigger pitch start with enough frames to meet min_active_frames and min_duration
        for i in range(4):  # Need 4 frames to trigger on the 4th (3 min_active + duration check)
            timestamp = first_detection + (i * 33_000_000)
            last_detection_time = timestamp
            # Add observation for each frame (need min 3 observations for validation)
            obs = create_test_observation(timestamp)
            sm.add_observation(obs)
            sm.update(timestamp, 1, 1, 1)

        # Continue pitch
        for i in range(4, 10):
            timestamp = first_detection + (i * 33_000_000)
            last_detection_time = timestamp
            obs = create_test_observation(timestamp)
            sm.add_observation(obs)
            sm.update(timestamp, 1, 1, 1)

        # End pitch with gap (3 frames of no detections)
        for i in range(3):
            timestamp = last_detection_time + ((i + 1) * 33_000_000)
            sm.update(timestamp, 0, 0, 0)

        # Verify timing
        assert pitch_start_ns == first_detection, f"Start time should be {first_detection}, got {pitch_start_ns}"
        # End time should be last detection, not gap end
        assert pitch_end_ns is not None, "End time should be set"
        assert pitch_end_ns == last_detection_time, f"End time should be {last_detection_time}, got {pitch_end_ns}"

        result.passed = True
    except Exception as e:
        result.error = str(e)
    return result


def test_thread_safety() -> TestResult:
    """Test concurrent updates are safe."""
    result = TestResult("Thread Safety")
    try:
        config = PitchConfig(min_active_frames=5, frame_rate=30.0)
        sm = PitchStateMachineV2(config)

        errors = []

        def update_thread():
            try:
                for i in range(50):
                    sm.update(i * 1_000_000, 1, 1, 1)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def observation_thread():
            try:
                for i in range(50):
                    obs = create_test_observation(i * 1_000_000)
                    sm.add_observation(obs)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def buffer_thread():
            try:
                for i in range(50):
                    frame = create_test_frame(i * 1_000_000)
                    sm.buffer_frame("left", frame)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=update_thread),
            threading.Thread(target=observation_thread),
            threading.Thread(target=buffer_thread),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety violations: {errors}"

        result.passed = True
    except Exception as e:
        result.error = str(e)
    return result


def test_minimum_duration_filter() -> TestResult:
    """Test short false triggers are filtered."""
    result = TestResult("Minimum Duration Filter")
    try:
        config = PitchConfig(
            min_active_frames=3,
            min_duration_ms=100.0,
            frame_rate=30.0,
        )
        sm = PitchStateMachineV2(config)

        pitch_started = False

        def on_start(idx, data):
            nonlocal pitch_started
            pitch_started = True

        sm.set_callbacks(on_pitch_start=on_start)

        # Rapid burst (< 100ms)
        for i in range(3):
            sm.update(i * 10_000_000, 1, 1, 1)  # 10ms apart = 30ms total

        assert not pitch_started, "Short burst should not trigger pitch"

        # Reset
        sm.reset()
        pitch_started = False

        # Longer sequence (> 100ms)
        # Need 6 frames: 5 to meet min_active_frames, plus 1 more to trigger transition
        for i in range(6):
            sm.update(i * 33_000_000, 1, 1, 1)  # 33ms apart = 165ms total

        assert pitch_started, "Longer sequence should trigger pitch"

        result.passed = True
    except Exception as e:
        result.error = str(e)
    return result


def test_data_validation() -> TestResult:
    """Test pitch data is validated before finalization."""
    result = TestResult("Data Validation")
    try:
        config = PitchConfig(
            min_active_frames=3,
            end_gap_frames=3,
            min_observations=5,  # Require at least 5 observations
            frame_rate=30.0,
        )
        sm = PitchStateMachineV2(config)

        pitch_ended = False

        def on_end(data):
            nonlocal pitch_ended
            pitch_ended = True

        sm.set_callbacks(on_pitch_end=on_end)

        # Trigger pitch start with only 3 observations
        for i in range(3):
            obs = create_test_observation(i * 33_000_000)
            sm.add_observation(obs)
            sm.update(i * 33_000_000, 1, 1, 1)

        # Continue for a bit
        for i in range(3, 6):
            sm.update(i * 33_000_000, 1, 1, 1)

        # End pitch with gap
        for i in range(3):
            sm.update((6 + i) * 33_000_000, 0, 0, 0)

        # Verify pitch was NOT finalized (too few observations)
        assert not pitch_ended, "Pitch should be rejected due to too few observations"

        result.passed = True
    except Exception as e:
        result.error = str(e)
    return result


def test_error_recovery() -> TestResult:
    """Test callback errors don't corrupt state."""
    result = TestResult("Error Recovery")
    try:
        config = PitchConfig(min_active_frames=3, frame_rate=30.0)
        sm = PitchStateMachineV2(config)

        def failing_callback(idx, data):
            raise RuntimeError("Callback failed!")

        sm.set_callbacks(on_pitch_start=failing_callback)

        # Trigger pitch start (should handle error)
        for i in range(5):
            sm.update(i * 33_000_000, 1, 1, 1)

        # State machine should still be functional
        phase = sm.get_phase()
        assert phase == PitchPhase.RAMP_UP, f"Should revert to RAMP_UP after callback failure, got {phase}"

        result.passed = True
    except Exception as e:
        result.error = str(e)
    return result


# Run all tests
def main():
    print("=" * 70)
    print("Pitch Tracking V2 Validation")
    print("=" * 70)
    print()

    tests = [
        test_basic_initialization,
        test_pre_roll_buffering,
        test_ramp_up_observations,
        test_accurate_timing,
        test_thread_safety,
        test_minimum_duration_filter,
        test_data_validation,
        test_error_recovery,
    ]

    results = []
    for test_fn in tests:
        print(f"Running: {test_fn.__doc__}")
        result = test_fn()
        results.append(result)
        print(f"  {result}")
        print()

    print("=" * 70)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)

    if passed == total:
        print("SUCCESS: All tests passed!")
        return 0
    else:
        print(f"FAILURE: {total - passed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

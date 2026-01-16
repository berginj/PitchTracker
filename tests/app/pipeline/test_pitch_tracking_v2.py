"""Unit tests for PitchStateMachineV2.

Tests verify critical improvements over v1:
- Thread safety
- Pre-roll capture
- Ramp-up observation capture
- Accurate timing
- Data validation
"""

import threading
import time
from unittest.mock import Mock

import pytest

from app.pipeline.pitch_tracking_v2 import (
    PitchConfig,
    PitchData,
    PitchPhase,
    PitchStateMachineV2,
)
from contracts import Frame, StereoObservation


# Test fixtures

def create_test_frame(timestamp_ns: int, camera_id: str = "test_cam") -> Frame:
    """Create test frame with minimal data."""
    return Frame(
        camera_id=camera_id,
        frame_index=0,
        t_capture_monotonic_ns=timestamp_ns,
        image=None,  # Not needed for state machine tests
    )


def create_test_observation(timestamp_ns: int) -> StereoObservation:
    """Create test observation."""
    return StereoObservation(
        t_ns=timestamp_ns,
        x_ft=0.0,
        y_ft=0.0,
        z_ft=0.0,
        left_detection_id="",
        right_detection_id="",
    )


@pytest.fixture
def default_config():
    """Default test configuration."""
    return PitchConfig(
        min_active_frames=5,
        end_gap_frames=10,
        use_plate_gate=True,
        min_observations=3,
        min_duration_ms=100.0,
        pre_roll_ms=300.0,
        frame_rate=30.0,
    )


@pytest.fixture
def state_machine(default_config):
    """Create state machine with default config."""
    return PitchStateMachineV2(default_config)


# Test pre-roll capture

def test_pre_roll_buffered_before_pitch_start(state_machine):
    """Verify pre-roll frames are buffered before pitch detection."""
    captured_pre_roll = []

    def on_start(idx, data: PitchData):
        captured_pre_roll.extend(data.pre_roll_frames)

    state_machine.set_callbacks(on_pitch_start=on_start)

    # Buffer 10 frames before any activity
    for i in range(10):
        frame = create_test_frame(i * 33_000_000)
        state_machine.buffer_frame("left", frame)
        state_machine.update(frame.t_capture_monotonic_ns, 0, 0, 0)

    assert len(captured_pre_roll) == 0, "Pre-roll not captured yet"

    # Trigger pitch start with activity
    for i in range(10, 20):
        frame = create_test_frame(i * 33_000_000)
        state_machine.buffer_frame("left", frame)
        state_machine.update(frame.t_capture_monotonic_ns, 1, 1, 1)

    # Pre-roll should include frames from before pitch started
    assert len(captured_pre_roll) > 0, "Pre-roll should be captured"
    assert len(captured_pre_roll) >= 10, f"Expected >=10 pre-roll frames, got {len(captured_pre_roll)}"

    # Verify pre-roll frames are chronologically before pitch start
    first_pre_roll_ns = captured_pre_roll[0][1].t_capture_monotonic_ns
    assert first_pre_roll_ns < 10 * 33_000_000, "Pre-roll should include frames before activity"


def test_pre_roll_per_camera(state_machine):
    """Verify pre-roll captured for both cameras."""
    captured_pre_roll = []

    def on_start(idx, data: PitchData):
        captured_pre_roll.extend(data.pre_roll_frames)

    state_machine.set_callbacks(on_pitch_start=on_start)

    # Buffer frames for both cameras
    for i in range(10):
        left_frame = create_test_frame(i * 33_000_000, "left")
        right_frame = create_test_frame(i * 33_000_000, "right")
        state_machine.buffer_frame("left", left_frame)
        state_machine.buffer_frame("right", right_frame)
        state_machine.update(i * 33_000_000, 0, 0, 0)

    # Trigger pitch
    for i in range(10, 20):
        left_frame = create_test_frame(i * 33_000_000, "left")
        right_frame = create_test_frame(i * 33_000_000, "right")
        state_machine.buffer_frame("left", left_frame)
        state_machine.buffer_frame("right", right_frame)
        state_machine.update(i * 33_000_000, 1, 1, 1)

    # Verify both cameras in pre-roll
    left_count = sum(1 for label, _ in captured_pre_roll if label == "left")
    right_count = sum(1 for label, _ in captured_pre_roll if label == "right")

    assert left_count > 0, "Left camera pre-roll missing"
    assert right_count > 0, "Right camera pre-roll missing"


def test_pre_roll_trimmed_to_window(state_machine):
    """Verify old frames are trimmed from pre-roll buffer."""
    # Buffer many frames (more than pre-roll window)
    for i in range(100):
        frame = create_test_frame(i * 33_000_000)
        state_machine.buffer_frame("left", frame)

    # Check buffer size is limited
    buffer = state_machine._pre_roll_frames["left"]
    assert len(buffer) <= 100, "Buffer should be limited"

    # Frames should be within pre-roll window (300ms at 30fps = ~9 frames)
    if len(buffer) > 1:
        oldest_ns = buffer[0].t_capture_monotonic_ns
        newest_ns = buffer[-1].t_capture_monotonic_ns
        window_ms = (newest_ns - oldest_ns) / 1_000_000

        # Allow some margin
        assert window_ms <= 350, f"Pre-roll window too large: {window_ms}ms"


# Test ramp-up observations

def test_ramp_up_observations_captured(state_machine):
    """Verify observations during ramp-up are not lost."""
    captured_observations = []

    def on_start(idx, data: PitchData):
        captured_observations.extend(data.observations)

    state_machine.set_callbacks(on_pitch_start=on_start)

    # Add observations during ramp-up (before pitch confirmed)
    for i in range(5):
        obs = create_test_observation(i * 33_000_000)
        state_machine.add_observation(obs)
        state_machine.update(i * 33_000_000, 1, 1, 1)

    # All ramp-up observations should be captured
    assert len(captured_observations) == 5, f"Expected 5 ramp-up observations, got {len(captured_observations)}"


def test_observation_at_trigger_frame_captured(state_machine):
    """Verify observation on exact trigger frame is not lost."""
    captured_observations = []

    def on_start(idx, data: PitchData):
        captured_observations.extend(data.observations)

    state_machine.set_callbacks(on_pitch_start=on_start)

    # Frames 0-3: ramp-up
    for i in range(4):
        obs = create_test_observation(i * 33_000_000)
        state_machine.add_observation(obs)
        state_machine.update(i * 33_000_000, 1, 1, 1)

    # Frame 4: trigger frame (min_active_frames=5 met)
    trigger_obs = create_test_observation(4 * 33_000_000)
    state_machine.add_observation(trigger_obs)
    state_machine.update(4 * 33_000_000, 1, 1, 1)

    # All 5 observations should be captured (including trigger frame)
    assert len(captured_observations) == 5, f"Trigger frame observation lost: got {len(captured_observations)}"


def test_observations_after_activation_captured(state_machine):
    """Verify observations after pitch activation continue to be captured."""
    all_observations = []

    def on_start(idx, data: PitchData):
        all_observations.extend(data.observations)

    def on_end(data: PitchData):
        all_observations.clear()
        all_observations.extend(data.observations)

    state_machine.set_callbacks(on_pitch_start=on_start, on_pitch_end=on_end)

    # Ramp-up
    for i in range(5):
        obs = create_test_observation(i * 33_000_000)
        state_machine.add_observation(obs)
        state_machine.update(i * 33_000_000, 1, 1, 1)

    # Active pitch
    for i in range(5, 15):
        obs = create_test_observation(i * 33_000_000)
        state_machine.add_observation(obs)
        state_machine.update(i * 33_000_000, 1, 1, 1)

    # End pitch
    for i in range(15, 26):
        state_machine.update(i * 33_000_000, 0, 0, 0)

    # All 15 observations should be captured
    assert len(all_observations) == 15, f"Expected 15 observations, got {len(all_observations)}"


# Test thread safety

def test_concurrent_updates_thread_safe(state_machine):
    """Verify concurrent updates don't cause crashes or corruption."""
    errors = []
    pitch_count = [0]

    def on_end(data: PitchData):
        pitch_count[0] += 1

    state_machine.set_callbacks(on_pitch_end=on_end)

    def update_thread():
        try:
            for i in range(200):
                state_machine.update(i * 1_000_000, 1 if i < 100 else 0, 1 if i < 100 else 0, 1 if i < 100 else 0)
                time.sleep(0.0001)
        except Exception as e:
            errors.append(("update", e))

    def observation_thread():
        try:
            for i in range(200):
                obs = create_test_observation(i * 1_000_000)
                state_machine.add_observation(obs)
                time.sleep(0.0001)
        except Exception as e:
            errors.append(("observation", e))

    def buffer_thread():
        try:
            for i in range(200):
                frame = create_test_frame(i * 1_000_000)
                state_machine.buffer_frame("left", frame)
                time.sleep(0.0001)
        except Exception as e:
            errors.append(("buffer", e))

    threads = [
        threading.Thread(target=update_thread),
        threading.Thread(target=observation_thread),
        threading.Thread(target=buffer_thread),
        threading.Thread(target=update_thread),  # Multiple update threads
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread safety violations: {errors}"
    assert pitch_count[0] >= 1, "Should detect at least one pitch"


# Test accurate timing

def test_start_time_is_first_detection(state_machine):
    """Verify start time is first detection, not trigger frame."""
    start_data = None

    def on_start(idx, data: PitchData):
        nonlocal start_data
        start_data = data

    state_machine.set_callbacks(on_pitch_start=on_start)

    first_detection_ns = 100_000_000

    # First detection at 100ms
    state_machine.update(first_detection_ns, 1, 1, 1)

    # More detections
    for i in range(1, 10):
        state_machine.update(first_detection_ns + i * 33_000_000, 1, 1, 1)

    # Start time should be first detection, not frame 5 (trigger)
    assert start_data is not None, "Pitch should have started"
    assert start_data.start_ns == first_detection_ns, f"Start time wrong: {start_data.start_ns} != {first_detection_ns}"
    assert start_data.first_detection_ns == first_detection_ns


def test_end_time_is_last_detection(state_machine):
    """Verify end time is last detection, not gap end."""
    end_data = None

    def on_end(data: PitchData):
        nonlocal end_data
        end_data = data

    state_machine.set_callbacks(on_pitch_end=on_end)

    # Start pitch
    for i in range(10):
        state_machine.update(i * 33_000_000, 1, 1, 1)

    last_detection_ns = 9 * 33_000_000

    # End with gap
    for i in range(10, 21):
        state_machine.update(i * 33_000_000, 0, 0, 0)

    # End time should be last detection (9*33ms), not frame 20 (20*33ms)
    assert end_data is not None, "Pitch should have ended"
    assert end_data.end_ns == last_detection_ns, f"End time wrong: {end_data.end_ns} != {last_detection_ns}"
    assert end_data.last_detection_ns == last_detection_ns


# Test data validation

def test_minimum_observations_filter(state_machine):
    """Verify pitches with too few observations are rejected."""
    pitch_ended = False

    def on_end(data: PitchData):
        nonlocal pitch_ended
        pitch_ended = True

    state_machine.set_callbacks(on_pitch_end=on_end)

    # Trigger pitch with only 2 observations (min is 3)
    for i in range(5):
        if i < 2:
            obs = create_test_observation(i * 33_000_000)
            state_machine.add_observation(obs)
        state_machine.update(i * 33_000_000, 1, 1, 1)

    # End pitch
    for i in range(5, 16):
        state_machine.update(i * 33_000_000, 0, 0, 0)

    # Pitch should be rejected (too few observations)
    assert not pitch_ended, "Pitch with 2 observations should be rejected (min is 3)"


def test_minimum_duration_filter(state_machine):
    """Verify short false triggers are filtered."""
    pitch_started = False

    def on_start(idx, data: PitchData):
        nonlocal pitch_started
        pitch_started = True

    state_machine.set_callbacks(on_pitch_start=on_start)

    # Rapid burst (5 frames at 10ms apart = 40ms total, < 100ms minimum)
    for i in range(5):
        state_machine.update(i * 10_000_000, 1, 1, 1)

    # Should not trigger (too short)
    assert not pitch_started, "Short burst should not trigger pitch"


def test_valid_pitch_passes_validation(state_machine):
    """Verify valid pitch is accepted."""
    pitch_ended = False
    pitch_data = None

    def on_end(data: PitchData):
        nonlocal pitch_ended, pitch_data
        pitch_ended = True
        pitch_data = data

    state_machine.set_callbacks(on_pitch_end=on_end)

    # Valid pitch: 10 observations over 300ms
    for i in range(10):
        obs = create_test_observation(i * 33_000_000)
        state_machine.add_observation(obs)
        state_machine.update(i * 33_000_000, 1, 1, 1)

    # End pitch
    for i in range(10, 21):
        state_machine.update(i * 33_000_000, 0, 0, 0)

    # Should be accepted
    assert pitch_ended, "Valid pitch should be accepted"
    assert pitch_data is not None
    assert len(pitch_data.observations) == 10


# Test error handling

def test_callback_exception_recovery(state_machine):
    """Verify state machine recovers from callback exceptions."""
    call_count = [0]

    def failing_callback(idx, data: PitchData):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("Test exception")
        # Second call should succeed

    state_machine.set_callbacks(on_pitch_start=failing_callback)

    # First pitch (callback fails)
    for i in range(10):
        state_machine.update(i * 33_000_000, 1, 1, 1)

    # Should recover and not be in broken state
    phase = state_machine.get_phase()
    assert phase != PitchPhase.ACTIVE, "State should revert after callback failure"

    # Second pitch (callback succeeds)
    for i in range(100, 110):
        state_machine.update(i * 33_000_000, 1, 1, 1)

    assert call_count[0] == 2, "Second pitch should trigger callback"


# Test state transitions

def test_state_transition_flow(state_machine):
    """Verify state transitions follow expected flow."""
    phases = []

    def track_phase():
        phases.append(state_machine.get_phase())

    # Start: INACTIVE
    track_phase()
    assert state_machine.get_phase() == PitchPhase.INACTIVE

    # First detection → RAMP_UP
    state_machine.update(0, 1, 1, 1)
    track_phase()
    assert state_machine.get_phase() == PitchPhase.RAMP_UP

    # Continue detections → ACTIVE
    for i in range(1, 10):
        state_machine.update(i * 33_000_000, 1, 1, 1)
    track_phase()
    assert state_machine.get_phase() == PitchPhase.ACTIVE

    # Gap → back to INACTIVE
    for i in range(10, 21):
        state_machine.update(i * 33_000_000, 0, 0, 0)
    track_phase()
    assert state_machine.get_phase() == PitchPhase.INACTIVE


def test_false_start_during_ramp_up(state_machine):
    """Verify state resets if activity stops during ramp-up."""
    pitch_started = False

    def on_start(idx, data):
        nonlocal pitch_started
        pitch_started = True

    state_machine.set_callbacks(on_pitch_start=on_start)

    # Start ramping up
    for i in range(3):
        state_machine.update(i * 33_000_000, 1, 1, 1)

    assert state_machine.get_phase() == PitchPhase.RAMP_UP

    # Activity stops (false start)
    for i in range(3, 6):
        state_machine.update(i * 33_000_000, 0, 0, 0)

    # Should return to INACTIVE
    assert state_machine.get_phase() == PitchPhase.INACTIVE
    assert not pitch_started, "Pitch should not have started"


# Test configuration

def test_config_update_when_inactive(state_machine):
    """Verify configuration can be updated when inactive."""
    new_config = PitchConfig(min_active_frames=10)
    success = state_machine.update_config(new_config)

    assert success, "Config update should succeed when inactive"
    assert state_machine._config.min_active_frames == 10


def test_config_update_rejected_when_active(state_machine):
    """Verify configuration cannot be updated during active pitch."""
    # Start pitch
    for i in range(10):
        state_machine.update(i * 33_000_000, 1, 1, 1)

    assert state_machine.get_phase() == PitchPhase.ACTIVE

    # Try to update config
    new_config = PitchConfig(min_active_frames=10)
    success = state_machine.update_config(new_config)

    assert not success, "Config update should be rejected during active pitch"
    assert state_machine._config.min_active_frames == 5  # Original value


# Test force_end

def test_force_end_during_active_pitch(state_machine):
    """Verify force_end properly finalizes active pitch."""
    pitch_ended = False

    def on_end(data: PitchData):
        nonlocal pitch_ended
        pitch_ended = True

    state_machine.set_callbacks(on_pitch_end=on_end)

    # Start pitch
    for i in range(10):
        obs = create_test_observation(i * 33_000_000)
        state_machine.add_observation(obs)
        state_machine.update(i * 33_000_000, 1, 1, 1)

    assert state_machine.get_phase() == PitchPhase.ACTIVE

    # Force end
    state_machine.force_end(10 * 33_000_000)

    assert pitch_ended, "Pitch should be ended"
    assert state_machine.get_phase() == PitchPhase.INACTIVE


def test_reset_clears_state(state_machine):
    """Verify reset properly clears all state."""
    # Start pitch
    for i in range(10):
        obs = create_test_observation(i * 33_000_000)
        frame = create_test_frame(i * 33_000_000)
        state_machine.add_observation(obs)
        state_machine.buffer_frame("left", frame)
        state_machine.update(i * 33_000_000, 1, 1, 1)

    # Reset
    state_machine.reset()

    # Verify state is cleared
    assert state_machine.get_phase() == PitchPhase.INACTIVE
    assert state_machine.get_pitch_index() == 0
    assert len(state_machine._observations) == 0
    assert len(state_machine._pre_roll_frames["left"]) == 0

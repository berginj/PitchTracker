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
        width=1280,
        height=720,
        pixfmt="BGR8",
    )


def create_test_observation(timestamp_ns: int) -> StereoObservation:
    """Create test observation."""
    return StereoObservation(
        t_ns=timestamp_ns,
        left=(640.0, 360.0),
        right=(638.0, 360.0),
        X=0.0,
        Y=0.0,
        Z=float(timestamp_ns) / 33_000_000.0,
        quality=1.0,
        confidence=0.9,
    )


def add_detection_with_observation(state_machine: PitchStateMachineV2, i: int, step_ns: int = 33_000_000) -> None:
    """Advance detection state and retain the same-frame observation."""
    t_ns = i * step_ns
    if state_machine.get_phase() == PitchPhase.INACTIVE:
        state_machine.update(t_ns, 1, 1, 1)
        state_machine.add_observation(create_test_observation(t_ns))
    else:
        state_machine.add_observation(create_test_observation(t_ns))
        state_machine.update(t_ns, 1, 1, 1)


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
        add_detection_with_observation(state_machine, i)

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
        add_detection_with_observation(state_machine, i)

    # Frame 4: trigger frame (min_active_frames=5 met)
    add_detection_with_observation(state_machine, 4)

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
        add_detection_with_observation(state_machine, i)

    # Active pitch
    for i in range(5, 15):
        add_detection_with_observation(state_machine, i)

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
                state_machine.update(i * 2_000_000, 1 if i < 100 else 0, 1 if i < 100 else 0, 1 if i < 100 else 0)
                time.sleep(0.0001)
        except Exception as e:
            errors.append(("update", e))

    def observation_thread():
        try:
            for i in range(200):
                obs = create_test_observation(i * 2_000_000)
                state_machine.add_observation(obs)
                time.sleep(0.0001)
        except Exception as e:
            errors.append(("observation", e))

    def buffer_thread():
        try:
            for i in range(200):
                frame = create_test_frame(i * 2_000_000)
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

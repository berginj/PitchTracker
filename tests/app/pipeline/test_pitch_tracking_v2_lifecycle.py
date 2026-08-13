"""Lifecycle and validation tests for PitchStateMachineV2."""

import pytest

from app.pipeline.pitch_tracking_v2 import (
    PitchConfig,
    PitchData,
    PitchPhase,
    PitchStateMachineV2,
)
from contracts import Frame, StereoObservation


def create_test_frame(timestamp_ns: int, camera_id: str = "test_cam") -> Frame:
    """Create test frame with minimal data."""
    return Frame(
        camera_id=camera_id,
        frame_index=0,
        t_capture_monotonic_ns=timestamp_ns,
        image=None,
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


def test_start_time_is_first_detection(state_machine):
    """Verify start time is first detection, not trigger frame."""
    start_data = None

    def on_start(idx, data: PitchData):
        nonlocal start_data
        start_data = data

    state_machine.set_callbacks(on_pitch_start=on_start)
    first_detection_ns = 100_000_000
    state_machine.update(first_detection_ns, 1, 1, 1)
    for i in range(1, 10):
        state_machine.update(first_detection_ns + i * 33_000_000, 1, 1, 1)
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
    for i in range(10):
        add_detection_with_observation(state_machine, i)
    last_detection_ns = 9 * 33_000_000
    for i in range(10, 21):
        state_machine.update(i * 33_000_000, 0, 0, 0)
    assert end_data is not None, "Pitch should have ended"
    assert end_data.end_ns == last_detection_ns, f"End time wrong: {end_data.end_ns} != {last_detection_ns}"
    assert end_data.last_detection_ns == last_detection_ns


def test_minimum_observations_filter(state_machine):
    """Verify pitches with too few observations are rejected."""
    pitch_ended = False

    def on_end(data: PitchData):
        nonlocal pitch_ended
        pitch_ended = True

    state_machine.set_callbacks(on_pitch_end=on_end)
    for i in range(5):
        if i < 2:
            obs = create_test_observation(i * 33_000_000)
            state_machine.add_observation(obs)
        state_machine.update(i * 33_000_000, 1, 1, 1)
    for i in range(5, 16):
        state_machine.update(i * 33_000_000, 0, 0, 0)
    assert not pitch_ended, "Pitch with 2 observations should be rejected (min is 3)"


def test_minimum_duration_filter(state_machine):
    """Verify short false triggers are filtered."""
    pitch_started = False

    def on_start(idx, data: PitchData):
        nonlocal pitch_started
        pitch_started = True

    state_machine.set_callbacks(on_pitch_start=on_start)
    for i in range(5):
        state_machine.update(i * 10_000_000, 1, 1, 1)
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
    for i in range(10):
        add_detection_with_observation(state_machine, i)
    for i in range(10, 21):
        state_machine.update(i * 33_000_000, 0, 0, 0)
    assert pitch_ended, "Valid pitch should be accepted"
    assert pitch_data is not None
    assert len(pitch_data.observations) == 10


def test_callback_exception_recovery(state_machine):
    """Verify state machine recovers from callback exceptions."""
    call_count = [0]

    def failing_callback(idx, data: PitchData):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("Test exception")

    state_machine.set_callbacks(on_pitch_start=failing_callback)
    for i in range(5):
        state_machine.update(i * 33_000_000, 1, 1, 1)
    phase = state_machine.get_phase()
    assert phase != PitchPhase.ACTIVE, "State should revert after callback failure"
    for i in range(100, 110):
        state_machine.update(i * 33_000_000, 1, 1, 1)
    assert call_count[0] == 2, "Second pitch should trigger callback"


def test_state_transition_flow(state_machine):
    """Verify state transitions follow expected flow."""
    phases = []

    def track_phase():
        phases.append(state_machine.get_phase())

    track_phase()
    assert state_machine.get_phase() == PitchPhase.INACTIVE
    state_machine.update(0, 1, 1, 1)
    track_phase()
    assert state_machine.get_phase() == PitchPhase.RAMP_UP
    for i in range(1, 10):
        state_machine.update(i * 33_000_000, 1, 1, 1)
    track_phase()
    assert state_machine.get_phase() == PitchPhase.ACTIVE
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
    for i in range(3):
        state_machine.update(i * 33_000_000, 1, 1, 1)
    assert state_machine.get_phase() == PitchPhase.RAMP_UP
    for i in range(3, 6):
        state_machine.update(i * 33_000_000, 0, 0, 0)
    assert state_machine.get_phase() == PitchPhase.INACTIVE
    assert not pitch_started, "Pitch should not have started"


def test_config_update_when_inactive(state_machine):
    """Verify configuration can be updated when inactive."""
    new_config = PitchConfig(min_active_frames=10)
    success = state_machine.update_config(new_config)
    assert success, "Config update should succeed when inactive"
    assert state_machine._config.min_active_frames == 10


def test_config_update_rejected_when_active(state_machine):
    """Verify configuration cannot be updated during active pitch."""
    for i in range(10):
        state_machine.update(i * 33_000_000, 1, 1, 1)
    assert state_machine.get_phase() == PitchPhase.ACTIVE
    new_config = PitchConfig(min_active_frames=10)
    success = state_machine.update_config(new_config)
    assert not success, "Config update should be rejected during active pitch"
    assert state_machine._config.min_active_frames == 5


def test_force_end_during_active_pitch(state_machine):
    """Verify force_end properly finalizes active pitch."""
    pitch_ended = False

    def on_end(data: PitchData):
        nonlocal pitch_ended
        pitch_ended = True

    state_machine.set_callbacks(on_pitch_end=on_end)
    for i in range(10):
        add_detection_with_observation(state_machine, i)
    assert state_machine.get_phase() == PitchPhase.ACTIVE
    state_machine.force_end(10 * 33_000_000)
    assert pitch_ended, "Pitch should be ended"
    assert state_machine.get_phase() == PitchPhase.INACTIVE


def test_reset_clears_state(state_machine):
    """Verify reset properly clears all state."""
    for i in range(10):
        frame = create_test_frame(i * 33_000_000)
        state_machine.buffer_frame("left", frame)
        add_detection_with_observation(state_machine, i)
    state_machine.reset()
    assert state_machine.get_phase() == PitchPhase.INACTIVE
    assert state_machine.get_pitch_index() == 0
    assert len(state_machine._observations) == 0
    assert len(state_machine._pre_roll_frames["left"]) == 0

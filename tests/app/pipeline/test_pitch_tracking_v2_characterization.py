"""Characterization tests for pitch-state extraction boundaries."""

from app.pipeline.pitch_tracking_v2 import PitchConfig, PitchPhase, PitchStateMachineV2
from contracts import RayObservation, StereoObservation


def _stereo_observation(frame_index: int) -> StereoObservation:
    timestamp_ns = frame_index * 33_000_000
    return StereoObservation(
        t_ns=timestamp_ns,
        left=(640.0, 360.0),
        right=(638.0, 360.0),
        X=0.0,
        Y=0.0,
        Z=float(frame_index),
        quality=1.0,
        confidence=0.9,
        observation_id=f"stereo-{frame_index}",
    )


def _ray_observation(frame_index: int) -> RayObservation:
    return RayObservation(
        camera_id="left",
        frame_index=frame_index,
        t_ns=frame_index * 33_000_000,
        u=640.0,
        v=360.0,
        radius_px=4.0,
        confidence=0.8,
    )


def _add_active_frame(state_machine: PitchStateMachineV2, frame_index: int) -> None:
    timestamp_ns = frame_index * 33_000_000
    if state_machine.get_phase() == PitchPhase.INACTIVE:
        state_machine.update(timestamp_ns, 1, 1, 1)
        state_machine.add_observation(_stereo_observation(frame_index))
        state_machine.add_ray_observation(_ray_observation(frame_index))
        return

    state_machine.add_observation(_stereo_observation(frame_index))
    state_machine.add_ray_observation(_ray_observation(frame_index))
    state_machine.update(timestamp_ns, 1, 1, 1)


def test_callback_snapshots_preserve_stereo_and_ray_state() -> None:
    """Callback-owned lists cannot mutate later state-machine snapshots."""
    config = PitchConfig(min_active_frames=3, end_gap_frames=2, min_observations=2, min_duration_ms=50.0)
    state_machine = PitchStateMachineV2(config)
    ended = []

    def on_start(_pitch_index, pitch_data):
        assert len(pitch_data.observations) == 3
        assert len(pitch_data.ray_observations) == 3
        pitch_data.observations.clear()
        pitch_data.ray_observations.clear()

    state_machine.set_callbacks(on_pitch_start=on_start, on_pitch_end=ended.append)

    for frame_index in range(5):
        _add_active_frame(state_machine, frame_index)
    for frame_index in range(5, 7):
        state_machine.update(frame_index * 33_000_000, 0, 0, 0)

    assert len(ended) == 1
    assert [obs.observation_id for obs in ended[0].observations] == [f"stereo-{i}" for i in range(5)]
    assert [obs.frame_index for obs in ended[0].ray_observations] == list(range(5))


def test_transition_event_log_order_is_preserved() -> None:
    """Extraction retains update-before-transition event ordering."""
    config = PitchConfig(min_active_frames=2, end_gap_frames=2, min_observations=1, min_duration_ms=20.0)
    state_machine = PitchStateMachineV2(config)
    state_machine.set_callbacks(on_pitch_end=lambda _pitch_data: None)

    _add_active_frame(state_machine, 0)
    _add_active_frame(state_machine, 1)
    state_machine.update(66_000_000, 0, 0, 0)
    state_machine.update(99_000_000, 0, 0, 0)

    events = state_machine.get_event_log()
    assert [event["type"] for event in events] == [
        "update",
        "transition",
        "update",
        "transition",
        "update",
        "update",
        "transition",
    ]
    assert [event["data"]["to"] for event in events if event["type"] == "transition"] == [
        "RAMP_UP",
        "ACTIVE",
        "FINALIZED",
    ]

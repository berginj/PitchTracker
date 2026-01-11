from contracts import Detection, Frame, PitchMetrics, StereoObservation, TrackSample


def test_contracts_instantiation() -> None:
    frame = Frame(
        camera_id="left",
        frame_index=1,
        t_capture_monotonic_ns=123,
        image=None,
        width=1920,
        height=1080,
        pixfmt="GRAY8",
    )
    detection = Detection(
        camera_id="left",
        frame_index=1,
        t_capture_monotonic_ns=123,
        u=100.0,
        v=200.0,
        radius_px=5.0,
        confidence=0.9,
    )
    stereo = StereoObservation(
        t_ns=123,
        left=(100.0, 200.0),
        right=(95.0, 200.0),
        X=1.0,
        Y=2.0,
        Z=50.0,
        quality=0.9,
        confidence=0.9,
    )
    track = TrackSample(
        t_ns=123,
        X=1.0,
        Y=2.0,
        Z=50.0,
        Vx=0.1,
        Vy=0.2,
        Vz=-30.0,
    )
    metrics = PitchMetrics(
        pitch_id="test",
        t_start_ns=0,
        t_end_ns=1,
        velo_mph=90.0,
        HB_in=5.0,
        iVB_in=10.0,
        release_xyz_ft=(0.0, 6.0, 50.0),
        approach_angles_deg=(1.0, -5.0),
        confidence=0.8,
    )

    assert frame.camera_id == "left"
    assert detection.camera_id == "left"
    assert stereo.Z == 50.0
    assert track.Vz == -30.0
    assert metrics.pitch_id == "test"

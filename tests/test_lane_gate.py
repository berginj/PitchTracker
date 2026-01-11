from detect.lane import LaneGate, LaneRoi
from stereo.association import StereoMatch
from stereo.lane import StereoLaneGate

from contracts import Detection


def test_lane_gate_filters_detections() -> None:
    roi = LaneRoi(polygon=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
    gate = LaneGate(roi_by_camera={"left": roi})
    detections = [
        Detection(
            camera_id="left",
            frame_index=1,
            t_capture_monotonic_ns=1,
            u=5.0,
            v=5.0,
            radius_px=3.0,
            confidence=0.9,
        ),
        Detection(
            camera_id="left",
            frame_index=2,
            t_capture_monotonic_ns=2,
            u=15.0,
            v=5.0,
            radius_px=3.0,
            confidence=0.9,
        ),
    ]

    filtered = gate.filter_detections(detections)

    assert len(filtered) == 1
    assert filtered[0].frame_index == 1


def test_stereo_lane_gate_filters_matches() -> None:
    roi = LaneRoi(polygon=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
    gate = LaneGate(roi_by_camera={"left": roi, "right": roi})
    stereo_gate = StereoLaneGate(lane_gate=gate)
    left = Detection(
        camera_id="left",
        frame_index=1,
        t_capture_monotonic_ns=1,
        u=5.0,
        v=5.0,
        radius_px=3.0,
        confidence=0.9,
    )
    right = Detection(
        camera_id="right",
        frame_index=1,
        t_capture_monotonic_ns=1,
        u=12.0,
        v=5.0,
        radius_px=3.0,
        confidence=0.9,
    )
    match = StereoMatch(left=left, right=right, epipolar_error_px=0.1, score=0.9)

    filtered = stereo_gate.filter_matches([match])

    assert len(filtered) == 0

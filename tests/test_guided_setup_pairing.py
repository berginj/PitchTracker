"""Guided image checks preserve unmatched frames in capture qualification."""

from dataclasses import replace

import pytest

from tests.test_guided_setup_workflow import _capture, _new_workflow


@pytest.mark.parametrize("offset_ns,expected_pairs", ((16_666_667, 59), (8_333_333, 0)))
def test_guided_capture_uses_timestamp_pairs_instead_of_frame_positions(tmp_path, offset_ns, expected_pairs):
    workflow = _new_workflow(tmp_path)
    workflow.assign("left", "right")
    result = _capture(workflow, tmp_path)
    shifted = tuple(replace(frame, t_capture_monotonic_ns=frame.t_capture_monotonic_ns + offset_ns)
                    for frame in result.right_frames)
    diagnostics = workflow.apply_capture_result(replace(result, right_frames=shifted))
    qualification = diagnostics["qualification"]
    pairing = diagnostics["checks"]["pairing"]["details"]
    assert qualification["frame_count_left"] == qualification["frame_count_right"] == 60
    assert qualification["paired_count"] == pairing["sample_count"] == expected_pairs
    assert pairing["unpaired_count"] == 120 - 2 * expected_pairs
    assert qualification["unmatched_frame_rate"] == pytest.approx((120 - 2 * expected_pairs) / 120)
    assert qualification["pair_skew_p95_ms"] == 0.0
    assert not pairing["exposure_sync_verified"]
    assert not workflow.state["checks"]["images"]["passed"]

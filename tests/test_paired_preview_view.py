from ui.setup.paired_preview_view import (
    PairedPreviewSnapshot,
    empty_preview_snapshot,
    grade_preview,
    present_paired_preview,
)


def _passing_snapshot() -> PairedPreviewSnapshot:
    return PairedPreviewSnapshot(
        left_ok=True,
        right_ok=True,
        paired_within_tolerance=True,
        left_frame_index=10,
        right_frame_index=11,
        pair_offset_ms=1.5,
        frames_observed=4,
    )


def test_grade_preview_passes_when_streams_pair_within_tolerance() -> None:
    assert grade_preview(_passing_snapshot()) == (True, "")


def test_grade_preview_fails_for_empty_snapshot() -> None:
    assert grade_preview(empty_preview_snapshot()) == (False, "No frames received from either camera.")


def test_grade_preview_fails_when_left_camera_missing() -> None:
    snapshot = PairedPreviewSnapshot(
        left_ok=False,
        right_ok=True,
        paired_within_tolerance=False,
        right_frame_index=8,
        frames_observed=1,
    )

    assert grade_preview(snapshot) == (False, "Left camera not delivering frames.")


def test_grade_preview_fails_when_right_camera_missing() -> None:
    snapshot = PairedPreviewSnapshot(
        left_ok=True,
        right_ok=False,
        paired_within_tolerance=False,
        left_frame_index=8,
        frames_observed=1,
    )

    assert grade_preview(snapshot) == (False, "Right camera not delivering frames.")


def test_grade_preview_fails_when_pairing_is_out_of_tolerance() -> None:
    snapshot = PairedPreviewSnapshot(
        left_ok=True,
        right_ok=True,
        paired_within_tolerance=False,
        left_frame_index=8,
        right_frame_index=9,
        frames_observed=2,
    )

    assert grade_preview(snapshot) == (False, "Left/right frames not pairing within tolerance.")


def test_present_paired_preview_success_tone_for_passing_snapshot() -> None:
    view = present_paired_preview(_passing_snapshot())

    assert view.tone == "success"
    assert view.warnings == []
    assert view.rows[0].label == "Left stream"
    assert view.rows[0].value == "OK (frame 10)"
    assert view.rows[1].value == "OK (frame 11)"
    assert view.rows[2].value == "1.5 ms"


def test_present_paired_preview_warning_tone_for_partial_snapshot() -> None:
    view = present_paired_preview(
        PairedPreviewSnapshot(
            left_ok=True,
            right_ok=False,
            paired_within_tolerance=False,
            left_frame_index=3,
            frames_observed=1,
        )
    )

    assert view.tone == "warning"
    assert view.warnings == ["Right camera not delivering frames."]


def test_present_paired_preview_error_tone_for_zero_frames() -> None:
    view = present_paired_preview(empty_preview_snapshot())

    assert view.tone == "error"
    assert view.warnings == ["No frames received from either camera."]

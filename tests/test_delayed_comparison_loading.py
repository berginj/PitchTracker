"""Delayed comparisons appear in review without altering the primary manifest."""

import json

from app.review.session_artifacts import load_pitch


def test_review_loads_delayed_comparisons_separately(tmp_path):
    primary = {
        "pitch_id": "pitch_1",
        "trajectory": {
            "mode": "stereo_3d",
            "comparison": {
                "ray_graph": {"status": "DEFERRED"},
            },
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(primary))
    comparison = {"ray_graph": {"diagnostics": {"failure_codes": ["CAMERA_MODEL_MISSING"]}}}
    (tmp_path / "trajectory_comparisons.json").write_text(
        json.dumps(
            {
                "schema_version": "trajectory_comparisons.v1",
                "pitch_id": "pitch_1",
                "results": comparison,
            }
        )
    )
    pitch = load_pitch(tmp_path)
    assert pitch.trajectory_comparisons == comparison
    assert pitch.manifest == primary
    assert json.loads(path.read_text()) == primary


def test_review_rejects_comparison_for_other_pitch(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"pitch_id": "pitch_1"}))
    (tmp_path / "trajectory_comparisons.json").write_text(
        json.dumps(
            {
                "schema_version": "trajectory_comparisons.v1",
                "pitch_id": "pitch_other",
                "results": {},
            }
        )
    )
    assert load_pitch(tmp_path).trajectory_comparisons is None

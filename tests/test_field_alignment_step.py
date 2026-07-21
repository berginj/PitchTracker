from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import QtWidgets  # noqa: E402

from ui.setup.field_alignment_view import load_or_estimate_field_alignment
from ui.setup.steps.field_alignment_step import FieldAlignmentStep


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def test_field_alignment_estimates_and_persists_transform(tmp_path: Path) -> None:
    fixture_path = tmp_path / "field_fixture_points.json"
    fixture_path.write_text(
        json.dumps(
            {
                "fixture_id": "plate-targets",
                "camera_points_ft": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                "field_points_ft": [[2, 3, 0], [3, 3, 0], [2, 4, 0]],
            }
        ),
        encoding="utf-8",
    )
    snapshot = load_or_estimate_field_alignment(tmp_path)
    assert snapshot.passed is True
    transform_payload = json.loads((tmp_path / "field_transform.json").read_text(encoding="utf-8"))
    assert transform_payload["fixture_source_sha256"] == snapshot.fixture_source_sha256
    assert transform_payload["fixture_point_count"] == 3
    assert len(snapshot.fixture_source_sha256) == 64


def test_field_alignment_widget_blocks_missing_fixture(qapp, tmp_path: Path) -> None:
    widget = FieldAlignmentStep(snapshot_provider=lambda: load_or_estimate_field_alignment(tmp_path))
    widget.on_enter()
    valid, message = widget.validate()
    assert valid is False
    assert "three non-collinear" in message


def test_field_alignment_blocks_transform_above_residual_gate(tmp_path: Path) -> None:
    (tmp_path / "field_transform.json").write_text(
        json.dumps(
            {
                "matrix_4x4": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                "rms_residual_ft": 0.2,
                "max_rms_residual_ft": 0.1,
                "fixture_id": "bad-fixture",
            }
        ),
        encoding="utf-8",
    )
    snapshot = load_or_estimate_field_alignment(tmp_path)
    assert snapshot.passed is False
    assert "exceeds" in snapshot.recommendation


def test_field_alignment_recomputes_when_fixture_source_changes(tmp_path: Path) -> None:
    fixture_path = tmp_path / "field_fixture_points.json"
    fixture_path.write_text(
        json.dumps(
            {
                "fixture_id": "plate-targets",
                "camera_points_ft": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                "field_points_ft": [[2, 3, 0], [3, 3, 0], [2, 4, 0]],
            }
        ),
        encoding="utf-8",
    )
    first = load_or_estimate_field_alignment(tmp_path)

    fixture_path.write_text(
        json.dumps(
            {
                "fixture_id": "plate-targets",
                "camera_points_ft": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                "field_points_ft": [[5, 6, 0], [6, 6, 0], [5, 7, 0]],
            }
        ),
        encoding="utf-8",
    )
    second = load_or_estimate_field_alignment(tmp_path)

    assert first.passed and second.passed
    assert first.fixture_source_sha256 != second.fixture_source_sha256
    assert first.transform is not None and second.transform is not None
    assert first.transform.matrix_4x4 != second.transform.matrix_4x4
    persisted = json.loads((tmp_path / "field_transform.json").read_text(encoding="utf-8"))
    assert persisted["fixture_source_sha256"] == second.fixture_source_sha256


def test_force_recalculate_does_not_trust_tampered_cached_transform(tmp_path: Path) -> None:
    fixture_path = tmp_path / "field_fixture_points.json"
    fixture_path.write_text(
        json.dumps(
            {
                "fixture_id": "plate-targets",
                "camera_points_ft": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                "field_points_ft": [[2, 3, 0], [3, 3, 0], [2, 4, 0]],
            }
        ),
        encoding="utf-8",
    )
    first = load_or_estimate_field_alignment(tmp_path)
    assert first.transform is not None
    transform_path = tmp_path / "field_transform.json"
    cached = json.loads(transform_path.read_text(encoding="utf-8"))
    cached["matrix_4x4"][0][3] = 99.0
    transform_path.write_text(json.dumps(cached), encoding="utf-8")

    forced = load_or_estimate_field_alignment(tmp_path, force_recalculate=True)

    assert forced.passed is True
    assert forced.transform is not None
    assert forced.transform.matrix_4x4[0][3] == pytest.approx(2.0)

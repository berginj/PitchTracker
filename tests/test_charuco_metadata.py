"""Tests for ChArUco board metadata loading."""

from __future__ import annotations

import json

import pytest

from ui.setup.steps.charuco_metadata import load_charuco_metadata


def test_load_charuco_metadata_reads_generated_json(tmp_path) -> None:
    metadata_path = tmp_path / "charuco_board.json"
    metadata_path.write_text(
        json.dumps(
            {
                "cols": 7,
                "rows": 5,
                "square_mm": 25.0,
                "dictionary": "6x6_250",
            }
        ),
        encoding="utf-8",
    )

    metadata = load_charuco_metadata([metadata_path])

    assert metadata is not None
    assert metadata.cols == 7
    assert metadata.rows == 5
    assert metadata.square_mm == 25.0
    assert metadata.dictionary == "6x6_250"
    assert metadata.source_path == metadata_path


def test_load_charuco_metadata_returns_none_when_missing(tmp_path) -> None:
    assert load_charuco_metadata([tmp_path / "missing.json"]) is None


def test_load_charuco_metadata_rejects_invalid_dimensions(tmp_path) -> None:
    metadata_path = tmp_path / "bad.json"
    metadata_path.write_text(
        json.dumps({"cols": 0, "rows": 5, "square_mm": 25.0}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cols must be positive"):
        load_charuco_metadata([metadata_path])

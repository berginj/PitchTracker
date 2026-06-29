"""Tests for field fixture scaffolding."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from calib.field_fixture import PASS, validate_field_fixture_manifest
from calib.field_fixture_scaffold import scaffold_field_fixture


def test_scaffold_field_fixture_copies_lightweight_manifests_and_validates(tmp_path: Path) -> None:
    session_dir = _session(tmp_path)
    calibration_report = tmp_path / "calibration_report_source.json"
    calibration_report.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    sync_report = tmp_path / "sync_report_source.json"
    sync_report.write_text(json.dumps({"sync_quality": "GOOD"}), encoding="utf-8")
    output_dir = tmp_path / "fixture"

    manifest = scaffold_field_fixture(
        session_dir=session_dir,
        output_dir=output_dir,
        fixture_id="field-smoke",
        calibration_report=calibration_report,
        sync_report=sync_report,
    )

    assert manifest["fixture_id"] == "field-smoke"
    assert manifest["calibration_report"] == "calibration_report.json"
    assert manifest["sync_report"] == "sync_report.json"
    assert manifest["session_manifest"] == "session/manifest.json"
    assert manifest["cases"][0]["manifest_path"] == "session/pitch_00001/manifest.json"
    assert manifest["cases"][0]["expected"]["observation_quality_status"] == "PASS"
    assert manifest["cases"][0]["expected"]["trajectory_mode"] == "stereo_3d"
    assert manifest["cases"][0]["expected"]["plate_z_ft"] == 0.02
    assert (output_dir / "session" / "manifest.json").exists()
    assert (output_dir / "session" / "pitch_00001" / "manifest.json").exists()
    assert (output_dir / "notes.md").exists()

    report = validate_field_fixture_manifest(output_dir / "field_fixture.json")
    assert report["status"] == PASS


def test_scaffold_field_fixture_refuses_non_empty_output_without_overwrite(tmp_path: Path) -> None:
    session_dir = _session(tmp_path)
    output_dir = tmp_path / "fixture"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        scaffold_field_fixture(session_dir=session_dir, output_dir=output_dir)


def test_scaffold_field_fixture_cli(tmp_path: Path) -> None:
    session_dir = _session(tmp_path)
    output_dir = tmp_path / "fixture"

    completed = subprocess.run(
        [
            sys.executable,
            "tools/scaffold_field_fixture.py",
            str(session_dir),
            str(output_dir),
            "--fixture-id",
            "cli-fixture",
        ],
        check=False,
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert '"fixture_id": "cli-fixture"' in completed.stdout
    assert (output_dir / "field_fixture.json").exists()


def _session(root: Path) -> Path:
    session_dir = root / "recordings" / "session_001"
    pitch_dir = session_dir / "pitch_00001"
    pitch_dir.mkdir(parents=True)
    (session_dir / "manifest.json").write_text(
        json.dumps({"session_id": "session_001", "pitch_id": "pitch_00001"}),
        encoding="utf-8",
    )
    (pitch_dir / "manifest.json").write_text(
        json.dumps(
            {
                "pitch_id": "pitch_00001",
                "trajectory": {
                    "mode": "stereo_3d",
                    "plate_crossing_xyz_ft": [0.1, 2.5, 0.02],
                },
                "observation_quality": {"status": "PASS"},
            }
        ),
        encoding="utf-8",
    )
    (pitch_dir / "left.avi").write_text("not copied", encoding="utf-8")
    return session_dir

"""Tests for field validation fixture manifests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from calib.field_fixture import FAIL, PASS, WARN, validate_field_fixture_manifest


def test_field_fixture_manifest_passes_static_and_pitch_cases(tmp_path: Path) -> None:
    (tmp_path / "calibration_report.json").write_text(
        json.dumps({"schema_version": "calibration_report.v1", "status": "PASS"}),
        encoding="utf-8",
    )
    (tmp_path / "sync_report.json").write_text(json.dumps({"sync_quality": "GOOD"}), encoding="utf-8")
    pitch_manifest = tmp_path / "pitch_00001" / "manifest.json"
    pitch_manifest.parent.mkdir()
    pitch_manifest.write_text(
        json.dumps(
            {
                "trajectory": {
                    "mode": "stereo_3d",
                    "plate_crossing_xyz_ft": [0.1, 2.5, 0.04],
                },
                "observation_quality": {"status": "PASS"},
            }
        ),
        encoding="utf-8",
    )
    fixture = tmp_path / "field_fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "field_fixture.v1",
                "fixture_id": "bullpen-smoke",
                "calibration_report": "calibration_report.json",
                "sync_report": "sync_report.json",
                "cases": [
                    {
                        "case_id": "target-home-plate",
                        "type": "static_target",
                        "expected_xyz_ft": [0.0, 2.5, 3.0],
                        "actual_xyz_ft": [0.1, 2.45, 3.05],
                        "max_error_ft": 0.25,
                    },
                    {
                        "case_id": "pitch-00001",
                        "type": "pitch_manifest",
                        "manifest_path": "pitch_00001/manifest.json",
                        "expected": {
                            "observation_quality_status": "PASS",
                            "trajectory_mode": "stereo_3d",
                            "plate_z_ft": 0.0,
                            "max_plate_z_error_ft": 0.1,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_field_fixture_manifest(fixture)

    assert report["status"] == PASS
    assert report["errors"] == []
    assert report["components"]["calibration"]["status"] == PASS
    assert report["components"]["sync"]["status"] == PASS
    assert report["components"]["field_targets"]["status"] == PASS
    assert report["components"]["pitch_manifests"]["status"] == PASS
    assert report["cases"][0]["component"] == "field_targets"
    assert report["cases"][1]["component"] == "pitch_manifests"
    assert report["cases"][0]["metrics"]["error_ft"] > 0.0
    assert report["cases"][1]["metrics"]["plate_z_ft"] == 0.04


def test_field_fixture_manifest_fails_bad_static_target_and_pitch_verdict(tmp_path: Path) -> None:
    (tmp_path / "calibration_report.json").write_text(
        json.dumps({"schema_version": "calibration_report.v1", "status": "FAIL"}),
        encoding="utf-8",
    )
    (tmp_path / "sync_report.json").write_text(json.dumps({"sync_quality": "POOR"}), encoding="utf-8")
    pitch_manifest = tmp_path / "pitch_00001" / "manifest.json"
    pitch_manifest.parent.mkdir()
    pitch_manifest.write_text(
        json.dumps(
            {
                "trajectory": {"mode": "stereo_3d", "plate_crossing_xyz_ft": [0.1, 2.5, 1.25]},
                "observation_quality": {"status": "REJECT"},
            }
        ),
        encoding="utf-8",
    )
    fixture = tmp_path / "field_fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "field_fixture.v1",
                "fixture_id": "bad-fixture",
                "calibration_report": "calibration_report.json",
                "sync_report": "sync_report.json",
                "cases": [
                    {
                        "case_id": "target-home-plate",
                        "type": "static_target",
                        "expected_xyz_ft": [0.0, 0.0, 0.0],
                        "actual_xyz_ft": [1.0, 0.0, 0.0],
                        "max_error_ft": 0.25,
                    },
                    {
                        "case_id": "pitch-00001",
                        "type": "pitch_manifest",
                        "manifest_path": "pitch_00001/manifest.json",
                        "expected": {
                            "observation_quality_status": "PASS",
                            "plate_z_ft": 0.0,
                            "max_plate_z_error_ft": 0.1,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_field_fixture_manifest(fixture)

    assert report["status"] == FAIL
    assert report["components"]["calibration"]["status"] == FAIL
    assert report["components"]["sync"]["status"] == FAIL
    assert report["components"]["field_targets"]["status"] == FAIL
    assert report["components"]["pitch_manifests"]["status"] == FAIL
    assert any("calibration_report status is FAIL" in item for item in report["errors"])
    assert any("sync_report status is FAIL" in item for item in report["errors"])
    assert any("static target error" in item for item in report["errors"])
    assert any("observation_quality.status" in item for item in report["errors"])
    assert any("plate z error" in item for item in report["errors"])


def test_field_fixture_manifest_warns_for_missing_optional_artifacts(tmp_path: Path) -> None:
    fixture = tmp_path / "field_fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "field_fixture.v1",
                "fixture_id": "missing-artifact",
                "calibration_report": "calibration_report.json",
                "cases": [
                    {
                        "case_id": "target-home-plate",
                        "type": "static_target",
                        "expected_xyz_ft": [0.0, 0.0, 0.0],
                        "actual_xyz_ft": [0.0, 0.0, 0.0],
                        "max_error_ft": 0.25,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_field_fixture_manifest(fixture)

    assert report["status"] == WARN
    assert report["components"]["calibration"]["status"] == WARN
    assert any("calibration_report does not exist" in item for item in report["warnings"])


def test_field_fixture_manifest_rejects_paths_outside_fixture_root(tmp_path: Path) -> None:
    fixture = tmp_path / "field_fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "field_fixture.v1",
                "fixture_id": "unsafe",
                "cases": [
                    {
                        "case_id": "pitch-00001",
                        "type": "pitch_manifest",
                        "manifest_path": "../outside.json",
                        "expected": {"observation_quality_status": "PASS"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_field_fixture_manifest(fixture)

    assert report["status"] == FAIL
    assert any("escapes fixture directory" in item for item in report["errors"])


def test_validate_field_fixture_cli_exit_codes(tmp_path: Path) -> None:
    fixture = tmp_path / "field_fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": "field_fixture.v1",
                "fixture_id": "cli-fixture",
                "cases": [
                    {
                        "case_id": "target-home-plate",
                        "type": "static_target",
                        "expected_xyz_ft": [0.0, 0.0, 0.0],
                        "actual_xyz_ft": [0.0, 0.0, 0.0],
                        "max_error_ft": 0.25,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "tools/validate_field_fixture.py", str(fixture)],
        check=False,
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert '"status": "PASS"' in completed.stdout

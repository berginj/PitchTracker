"""Scaffold lightweight field validation fixture packages from recordings."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from calib.field_fixture import SCHEMA_VERSION


def scaffold_field_fixture(
    *,
    session_dir: Path,
    output_dir: Path,
    fixture_id: str | None = None,
    calibration_report: Path | None = None,
    sync_report: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create a lightweight field fixture package from an existing recording session."""
    session_dir = Path(session_dir).resolve()
    output_dir = Path(output_dir).resolve()
    if not session_dir.exists() or not session_dir.is_dir():
        raise FileNotFoundError(f"Session directory not found: {session_dir}")
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    session_manifest_src = _existing_manifest(session_dir)
    if session_manifest_src is None:
        raise FileNotFoundError(f"Session manifest not found in {session_dir}")
    session_out = output_dir / "session"
    session_out.mkdir(exist_ok=True)
    shutil.copy2(session_manifest_src, session_out / "manifest.json")

    calibration_ref = _copy_optional_report(calibration_report, output_dir, "calibration_report.json")
    sync_ref = _copy_optional_report(sync_report, output_dir, "sync_report.json")

    cases: list[dict[str, Any]] = []
    for pitch_dir in sorted(item for item in session_dir.iterdir() if item.is_dir()):
        manifest_src = _existing_manifest(pitch_dir)
        if manifest_src is None:
            continue
        pitch_out = session_out / pitch_dir.name
        pitch_out.mkdir(exist_ok=True)
        manifest_dst = pitch_out / "manifest.json"
        shutil.copy2(manifest_src, manifest_dst)
        cases.append(_pitch_case(pitch_dir.name, _relative_path(output_dir, manifest_dst), _load_json(manifest_dst)))

    if not cases:
        raise FileNotFoundError(f"No pitch manifests found in {session_dir}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": fixture_id or session_dir.name,
        "calibration_report": calibration_ref,
        "sync_report": sync_ref,
        "session_manifest": "session/manifest.json",
        "cases": cases,
    }
    (output_dir / "field_fixture.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _write_notes(output_dir)
    return manifest


def _existing_manifest(directory: Path) -> Path | None:
    for name in ("manifest.json", "session_manifest.json", "pitch_manifest.json"):
        path = directory / name
        if path.exists():
            return path
    return None


def _copy_optional_report(path: Path | None, output_dir: Path, filename: str) -> str | None:
    if path is None:
        return None
    src = Path(path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Report not found: {src}")
    shutil.copy2(src, output_dir / filename)
    return filename


def _pitch_case(case_id: str, manifest_path: str, manifest: dict[str, Any]) -> dict[str, Any]:
    trajectory = manifest.get("trajectory") or {}
    observation_quality = manifest.get("observation_quality") or {}
    expected: dict[str, Any] = {}
    if observation_quality.get("status") is not None:
        expected["observation_quality_status"] = observation_quality.get("status")
    if trajectory.get("mode") is not None:
        expected["trajectory_mode"] = trajectory.get("mode")
    plate_z = _plate_z(manifest)
    if plate_z is not None:
        expected["plate_z_ft"] = plate_z
        expected["max_plate_z_error_ft"] = 0.5
    return {
        "case_id": case_id,
        "type": "pitch_manifest",
        "manifest_path": manifest_path,
        "expected": expected,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file is not an object: {path}")
    return payload


def _plate_z(manifest: dict[str, Any]) -> float | None:
    crossing = ((manifest.get("trajectory") or {}).get("plate_crossing_xyz_ft"))
    if not isinstance(crossing, list) or len(crossing) < 3:
        return None
    try:
        return float(crossing[2])
    except (TypeError, ValueError):
        return None


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _write_notes(output_dir: Path) -> None:
    (output_dir / "notes.md").write_text(
        "# Field Fixture Notes\n\n"
        "- Add static target cases with measured `expected_xyz_ft` and reconstructed `actual_xyz_ft`.\n"
        "- Confirm generated pitch expectations are intentional; do not treat copied actuals as accuracy proof.\n"
        "- Keep videos outside Git unless explicitly needed for a small fixture.\n",
        encoding="utf-8",
    )

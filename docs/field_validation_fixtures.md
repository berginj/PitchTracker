# Field Validation Fixtures

Field fixtures are the bridge between synthetic geometry tests and accuracy claims. They should be small, repeatable validation packages built from real rig recordings and known targets.

## Fixture Package Layout

Use one directory per validation session:

```text
field_fixture.json
calibration_report.json
sync_report.json
session/manifest.json
session/pitch_00001/manifest.json
notes.md
```

Large videos can live outside Git, but the fixture manifest should stay stable and point to the copied lightweight manifests/reports used for validation.

## Manifest Example

```json
{
  "schema_version": "field_fixture.v1",
  "fixture_id": "bullpen-2026-07-01",
  "calibration_report": "calibration_report.json",
  "sync_report": "sync_report.json",
  "session_manifest": "session/manifest.json",
  "cases": [
    {
      "case_id": "home-plate-target",
      "type": "static_target",
      "expected_xyz_ft": [0.0, 2.5, 3.0],
      "actual_xyz_ft": [0.08, 2.46, 3.04],
      "max_error_ft": 0.25
    },
    {
      "case_id": "pitch-00001",
      "type": "pitch_manifest",
      "manifest_path": "session/pitch_00001/manifest.json",
      "expected": {
        "observation_quality_status": "PASS",
        "trajectory_mode": "stereo_3d",
        "plate_z_ft": 0.0,
        "max_plate_z_error_ft": 0.5
      }
    }
  ]
}
```

## Validation Command

```powershell
.\.venv\Scripts\python.exe tools\validate_field_fixture.py path\to\field_fixture.json --output path\to\field_fixture_report.json
```

Exit codes:

- `0`: pass
- `1`: warnings
- `2`: failure

The JSON report includes component-level attribution:

```json
{
  "status": "FAIL",
  "components": {
    "calibration": {"status": "PASS", "warnings": [], "errors": []},
    "sync": {"status": "WARN", "warnings": ["sync_report status is WARN."], "errors": []},
    "field_targets": {"status": "FAIL", "warnings": [], "errors": ["home-plate-target: static target error ..."]},
    "pitch_manifests": {"status": "PASS", "warnings": [], "errors": []}
  }
}
```

Use this section to decide whether a failure belongs to calibration, synchronization, static-target stereo geometry, or pitch/path output.

## Scaffold From A Session

After recording a session, create a lightweight fixture package from its manifests:

```powershell
.\.venv\Scripts\python.exe tools\scaffold_field_fixture.py recordings\session_name_YYYYMMDD-HHMMSS fixtures\session_name `
  --fixture-id session_name `
  --calibration-report calibration_report.json `
  --sync-report sync_report.json
```

The scaffold copies only lightweight JSON manifests and reports. It does not copy videos. Review the generated `field_fixture.json`, then add static target cases with measured target coordinates and reconstructed coordinates before using the fixture for accuracy claims.

## Capture Requirements

- Include the exact calibration report used for the session.
- Include a sync report or timestamp-pairing report.
- Include rig profile, camera settings, ROI files, and operator notes.
- Record at least one static target near plate and one target in the pitch lane.
- Record at least one controlled moving-object clip before relying on live pitches.
- Do not use a fixture for accuracy claims unless the observation quality verdict and expected target checks pass.

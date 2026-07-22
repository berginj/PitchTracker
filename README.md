# PitchTracker

PitchTracker is a Windows desktop application for evidence-first baseball and
softball pitch tracking with two USB global-shutter cameras. It captures paired
frames, detects and associates ball candidates, reconstructs a 3D trajectory,
records replayable evidence, and presents coaching summaries without hiding
quality or correction information.

> **Current status (2026-07-22):** the software pipeline, setup snapshot,
> decision replay, error accounting, and physical-validation contracts are
> implemented and covered by automated tests. Physical speed and plate-location
> accuracy are **not yet validated** for public claims. We are actively looking
> for testers with global-shutter stereo rigs and independent reference
> equipment. See [Testing help needed](docs/TESTING_NEEDED.md).

## What is ready

- Service-oriented capture, detection, tracking, trajectory, recording, and
  analysis pipeline.
- Canonical ten-step stereo setup workflow with interruptible supervised capture.
- Camera recommendation that prefers a connected previously validated pair,
  then ranks recognized global-shutter pairs by requested-mode capability.
- Content-addressed setup-system snapshots recording software, host, cameras,
  controls, capture quality, calibration, ROI, field transform, and policy hashes.
- Complete candidate/match/triangulation decision evidence, unmatched-frame
  outcomes, global stereo assignment, session journal, and offline replay.
- Explicit error budgets, raw-versus-corrected values, drift monitoring, and
  fail-closed physical accuracy eligibility.
- PySide6 setup, coaching, recording, review, and export workflows.

Automated tests demonstrate software behavior with simulated and synthetic
inputs. They do not establish real-world measurement accuracy.

## Help us test

The highest-value contributions now require physical hardware:

1. Global-shutter camera discovery, control readback, synchronization, and
   capture qualification on Windows.
2. Repeatability of the ten-step setup workflow across PCs, USB controllers,
   camera models, lighting, and mounting conditions.
3. Ground-truth speed and plate-location comparisons using an independent,
   calibrated reference device and a predeclared protocol.
4. Clean Windows installer smoke tests.

Start with [docs/TESTING_NEEDED.md](docs/TESTING_NEEDED.md), then submit either a
[Validation Report](https://github.com/berginj/PitchTracker/issues/new?template=validation_report.yml)
or [Pilot Feedback](https://github.com/berginj/PitchTracker/issues/new?template=pilot_feedback.yml).
Do not upload athlete video, names, private facility information, calibration
files, or raw recordings unless sharing has been explicitly authorized.

## Release status

- Latest published release/tag: [`v2.0.0`](https://github.com/berginj/PitchTracker/releases/tag/v2.0.0).
- Current development branch: `main`.
- The published `v2.0.0` release currently has no installer asset. Build from
  source for testing until a refreshed installer is published and independently
  smoke-tested.
- Canonical status and open work: [Current Status](docs/CURRENT_STATUS.md) and
  [Roadmap](docs/ROADMAP.md).

## Developer setup

Requirements: Windows 10/11, Python 3.11 or 3.12 for CI parity, and two UVC
cameras for physical testing.

```powershell
git clone https://github.com/berginj/PitchTracker.git
cd PitchTracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python setup_validator.py
python launcher.py
```

Run against UVC cameras:

```powershell
.\run.ps1 -Backend uvc
```

Simulator-backed development and most automated tests do not require cameras.

## Setup workflow

The canonical workflow is:

1. Select cameras.
2. Verify paired preview.
3. Qualify synchronization.
4. Lock and verify focus/exposure controls.
5. Validate image overlap.
6. Compute coarse rectification.
7. Optionally refine with ChArUco.
8. Align camera coordinates to the measured field fixture.
9. Persist the rig profile and setup snapshot.
10. Review the quality report and blockers.

A completed wizard is not automatically a validated measurement system. The
snapshot, artifact hashes, physical-validation approval, current preflight, and
pitch-level evidence must all remain eligible.

## Tests

```powershell
python -m pytest -q
```

Latest recorded run on `main` at commit `211d246`:

- `1267 passed`
- `32 skipped`
- `0 failed`

Skipped tests are optional or environment/hardware dependent. See
[Testing Help Needed](docs/TESTING_NEEDED.md) for physical test procedures and
[Contributing](CONTRIBUTING.md) for required CI gates.

## Build the Windows installer

Install PyInstaller and Inno Setup 6, then run:

```powershell
.\build_installer.ps1 -Clean
```

Expected outputs:

- `dist\PitchTracker\PitchTracker.exe`
- `installer_output\PitchTracker-Setup-v2.0.0-stereo.exe`

See [Build Instructions](BUILD_INSTRUCTIONS.md). Generated build outputs are not
committed.

## Evidence and validation boundaries

- Default trajectory mode remains `stereo_3d`.
- Ray modes remain comparison-first until physical evidence supports promotion.
- Missing evidence is represented as unavailable, degraded, or rejected—not zero
  and not inferred success.
- Corrections retain raw values and an audit record.
- Detailed diagnostics are persisted and available on demand but are not shown
  by default unless they help setup or recovery.
- Physical `VALIDATED` status requires a separate confirmation dataset and signed
  approval bound to the exact rig, software, artifacts, and correction policy.

Relevant specifications:

- [Setup Snapshot Requirements](docs/SETUP_SNAPSHOT_REQUIREMENTS.md)
- [Evidence-First Field Robustness](docs/EVIDENCE_FIRST_FIELD_ROBUSTNESS.md)
- [Physical Validation Protocol v2](docs/PHYSICAL_VALIDATION_PROTOCOL_V2.md)
- [PT-001–PT-015 Traceability](docs/PT_001_015_TRACEABILITY.md)
- [Architecture](docs/ARCHITECTURE_CURRENT_STATE.md)

## Documentation

- [Documentation index](docs/README.md)
- [Current status](docs/CURRENT_STATUS.md)
- [Roadmap](docs/ROADMAP.md)
- [Testing help needed](docs/TESTING_NEEDED.md)
- [Installation](README_INSTALL.md)
- [User quick start](docs/QUICK_START.md)
- [Troubleshooting](docs/user/TROUBLESHOOTING.md)
- [Support](SUPPORT.md)
- [Security policy](SECURITY.md)
- [Requirements](REQ.md)
- [Changelog](CHANGELOG.md)

Historical plans and point-in-time reports are retained under `archive/` and
`docs/archive/`; they are not current status sources.

## Privacy

Frames, recordings, manifests, calibration artifacts, athlete information,
facility details, and logs may be sensitive. Keep them local by default. Public
issues should contain anonymized summaries and hashes or filenames—not private
media or secrets.

## License

See [LICENSE](LICENSE).

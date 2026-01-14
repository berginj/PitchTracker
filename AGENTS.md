# PitchTracker Agent Notes

## Project summary
PitchTracker is a Windows-first Python app that uses two USB3 cameras, OpenCV, and a PySide6 UI to capture, detect, and track baseball/softball pitches. The UI drives an in-process pipeline service, with core modules living outside the UI layer.

## Setup (PowerShell)
```powershell
.\setup.ps1
```

## Run (PowerShell)
```powershell
.\run.ps1 -Backend uvc
```
Use `-Backend opencv` when only an internal camera is available.

## Tests
```powershell
python -m pytest
```
Optional clip test:
```powershell
$env:PITCHTRACKER_TEST_VIDEO="C:\path\to\left.avi"
python -m pytest tests/test_video_clip.py
```

## Key directories
- `capture/`, `calib/`, `rectify/`, `detect/`, `stereo/`, `track/`, `metrics/`, `telemetry/`, `record/`: pipeline stages and utilities.
- `ui/`: PySide6 UI and the app entrypoint (`python -m ui.qt_app`).
- `configs/`: app settings and defaults (see `configs/default.yaml`).
- `contracts/` and `contracts-shared/`: serialized contract definitions and schemas.
- `tests/`: pytest suite.

## Contracts and boundaries
- Core pipeline code should stay UI-agnostic; avoid Qt types outside `ui/`.
- If you change serialized contracts or schemas, update the version in `contracts-shared/schema/version.json` and ensure manifests include schema/app metadata.

## Notes
- See `REQ.md` for architecture, data contract definitions, and system constraints.
- Camera selection and tuning are handled through the UI and `configs/`.

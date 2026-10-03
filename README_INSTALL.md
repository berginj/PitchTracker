# PitchTracker Installation

**Last reviewed:** 2026-10-03

**Applies to:** v2.0.0 and current `main`

## Current release status

The published [`v2.0.0` release](https://github.com/berginj/PitchTracker/releases/tag/v2.0.0)
has no installer asset. Run from source for current testing. Do not treat the
older v1.5 pilot installer as the current v2 build.

The repository can produce
`PitchTracker-Setup-v2.0.0-stereo.exe`, but that locally built artifact is not a
public release until it passes clean-machine smoke testing and is published with
its exact source commit and SHA-256.

## Run from source

Requirements:

- 64-bit Windows 10 or Windows 11;
- Python 3.13 or newer;
- enough disk space for dependencies and private recordings; and
- two qualifying global-shutter UVC cameras for physical testing.

```powershell
git clone https://github.com/berginj/PitchTracker.git
cd PitchTracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python setup_validator.py
python launcher.py --backend sim
```

Most automated tests and simulator workflows do not require cameras. Use
`python launcher.py --backend uvc` for a camera-backed run after setup.

## Build an installer for controlled testing

Developers need PyInstaller and Inno Setup 6:

```powershell
python -m pip install -r requirements-dev.txt
.\build_installer.ps1 -Clean
```

Expected outputs:

- `dist\PitchTracker\PitchTracker.exe`
- `dist\PitchTracker\PitchTrackerWorker.exe` (required beside the GUI)
- `installer_output\PitchTracker-Setup-v2.0.0-stereo.exe`
- `installer_output\PitchTracker-Setup-v2.0.0-stereo.exe.sha256`

See [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md). A successful build does not
prove that the package installs, updates, uninstalls, or preserves data correctly
on a clean machine.

## Verify a future published installer

Before running a published artifact:

1. Confirm it is attached to the intended GitHub release.
2. Confirm the filename and release tag agree.
3. Verify the published SHA-256.
4. Read the release's hardware and accuracy limitations.
5. Retain the installer filename, checksum, Windows version, and security prompts
   in any smoke-test report.

The packaged build is intended to include Python and runtime dependencies; a
separate Python installation should not be required for that exact verified
artifact.

## First launch

1. Connect the candidate camera pair.
2. Launch PitchTracker.
3. Choose **Setup & Calibration**.
4. Complete the canonical ten-step setup workflow.
5. Resolve all blockers and review the persisted setup snapshot.
6. Use **Coaching Sessions** only after the current preflight remains eligible.

Wizard completion does not establish physical speed or location accuracy.

## Data and network behavior

- Source launches retain checkout-relative paths: sessions default to
  `recordings/`, rig profiles to `calibration/rigs/`, and preferences to `configs/`.
- Frozen builds keep writable configuration, logs, calibration, ROIs and default
  recordings beneath `%LOCALAPPDATA%\PitchTracker\`, separate from installed
  executables and immutable defaults. Updates copy defaults only when absent;
  uninstalling the current build does not recursively delete operator data.
- The first default-path launch copies known legacy runtime directories from the
  installation and `_internal` into per-user state. It preserves originals and
  existing destination files, skips links, and leaves configured absolute paths
  unchanged. Review older absolute recording/calibration paths and reselect them
  explicitly when needed; back up operator state before lifecycle testing.
- An absolute `PITCHTRACKER_DATA_DIR` outside the installation selects a separate
  frozen workspace and suppresses automatic legacy migration. Source launches
  ignore this override. The state filesystem must support atomic hard links;
  the standard local NTFS path does. Inspect the active config and setup report
  for separately configured external recording/export locations.
- The updater checks the public GitHub Releases API by default.
- Capture artifacts remain local unless an optional integration is explicitly
  enabled, authenticated, and configured.

Treat recordings, frames, logs, manifests, calibration artifacts, athlete data,
and facility information as private.

The GUI can be checked without camera discovery or updater requests using an
explicit isolated smoke run:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:PITCHTRACKER_DATA_DIR = "C:\QA\PitchTracker-state"
.\dist\PitchTracker\PitchTracker.exe --gui-smoke-report "C:\QA\gui-smoke.json"
```

Choose a new QA directory rather than an operator workspace. This checks GUI
imports, rendering and simulator shutdown; it does not install the application
or establish physical accuracy, signing or clean-machine lifecycle behavior.

## Support

- [Quick Start](docs/QUICK_START.md)
- [Current Status](docs/CURRENT_STATUS.md)
- [Troubleshooting](docs/user/TROUBLESHOOTING.md)
- [GitHub Issues](https://github.com/berginj/PitchTracker/issues)
- [Private Security Reporting](https://github.com/berginj/PitchTracker/security/advisories/new)

The current installer smoke-test request is tracked in
[issue #11](https://github.com/berginj/PitchTracker/issues/11).

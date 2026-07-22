# PitchTracker Quick Start

**Last reviewed:** 2026-07-22

**Applies to:** v2.0.0 and current `main`

PitchTracker is ready for simulator-backed development and controlled field
testing. Physical speed and plate-location accuracy are not yet validated for a
public claim.

## Choose an installation path

### Current public path: run from source

The published `v2.0.0` release has no installer asset. On Windows with Python
3.11 or 3.12:

```powershell
git clone https://github.com/berginj/PitchTracker.git
cd PitchTracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python setup_validator.py
python launcher.py
```

Do not download the older v1.5 pilot installer as though it were the current v2
build. A refreshed installer will be published only after clean-machine smoke
testing and checksum verification.

### Future packaged installer

When a tested v2 installer is attached to a release, verify its filename,
release tag, and SHA-256 before running it. Packaged builds should not require a
separate Python installation. See [README_INSTALL.md](../README_INSTALL.md) for
the current release gap and verification checklist.

## Hardware required for field testing

- Two matching USB global-shutter cameras with stable identities.
- Verified 60 FPS-or-better mode at the intended resolution.
- Fixed or lockable focus and exposure controls.
- Rigid mounts, measured placement, and overlapping views of the pitch volume.
- Direct USB 3.x connections where practical.
- A rigid ChArUco target for calibration refinement.
- An independent calibrated reference channel for physical accuracy validation.

Conventional rolling-shutter webcams are not recommended for validation. Review
the [candidate hardware profile](HARDWARE_PROFILE.md) before purchasing cameras.

Simulator-backed development does not require cameras.

## Run the canonical setup

Launch `python launcher.py`, choose **Setup & Calibration**, and complete the
ten-step workflow:

1. Select and verify the camera pair.
2. Confirm paired preview.
3. Qualify synchronization.
4. Lock and verify focus and exposure controls.
5. Validate image overlap.
6. Compute coarse rectification.
7. Optionally refine with ChArUco.
8. Align camera coordinates to the measured field fixture.
9. Persist the rig profile and content-addressed setup snapshot.
10. Review the quality report and resolve blockers.

Wizard completion is not equivalent to a validated measurement system. The
current snapshot, calibration artifacts, physical approval, preflight, and
pitch-level evidence must all remain eligible.

## Start a controlled session

1. Return to the launcher and choose **Coaching Sessions**.
2. Start capture and confirm both previews, achieved FPS, and health indicators.
3. Resolve setup or synchronization blockers before recording.
4. Start a named session and record controlled test pitches.
5. Stop recording and capture cleanly before disconnecting cameras.
6. Use **Review** to inspect the session, evidence, and detailed diagnostics.

Recordings use the configured `recording.output_dir`; the default source-tree
configuration uses `recordings/`. Rig profiles default to `calibration/rigs/`.
Treat both locations as private.

## Interpret results honestly

- Automated or simulated success proves software behavior, not physical
  accuracy.
- Missing measurements remain unavailable, degraded, or rejected; do not treat
  placeholder zeroes as observations.
- `run_in` and `rise_in` are currently raw first-to-last observation
  displacement, not validated induced break.
- Ray trajectory modes remain comparison-first.
- Corrections retain raw values and an audit record.

## Get help or contribute evidence

- [Current status](CURRENT_STATUS.md)
- [Testing help needed](TESTING_NEEDED.md)
- [Setup snapshot requirements](SETUP_SNAPSHOT_REQUIREMENTS.md)
- [Troubleshooting](user/TROUBLESHOOTING.md)
- [FAQ](FAQ.md)
- [GitHub issues](https://github.com/berginj/PitchTracker/issues)

Do not post athlete media, private facility information, raw serial numbers,
calibration artifacts, secrets, or unreviewed logs in public issues.

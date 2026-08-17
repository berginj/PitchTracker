# PitchTracker

PitchTracker is a Windows desktop app that uses two cameras to track baseball
and softball pitches. It shows the operator what was captured, what the system
could measure, and which results are uncertain.

## Current status

The software is ready for simulator use and controlled engineering tests.
Physical speed and plate-location accuracy are **not validated for public
claims**. The current public `v2.0.0` release has no installer asset, so the
supported public path is running from source.

See [Current Status](docs/CURRENT_STATUS.md) for the latest test, release, and
hardware evidence. See the [glossary](docs/GLOSSARY.md) if terms such as
“global shutter,” “stereo,” or “setup snapshot” are unfamiliar.

## Choose your path

- **Try the simulator:** follow [Quick Start](docs/QUICK_START.md). No cameras
  are required.
- **Run the desktop app:** follow [Installation](README_INSTALL.md) and the
  [operator runbook](docs/OPERATOR_RUNBOOK.md).
- **Test cameras or field accuracy:** start with [Testing Help Needed](docs/TESTING_NEEDED.md).
- **Contribute code or documentation:** read [Contributing](CONTRIBUTING.md).
- **Report a problem:** use [Support](SUPPORT.md) and choose the appropriate
  issue form.

## What the app does

1. Helps an operator select and qualify a camera pair.
2. Captures synchronized views of the pitch lane.
3. Finds ball candidates and reconstructs a 3D trajectory when the evidence is
   sufficient.
4. Records replayable video, observations, decisions, and quality diagnostics.
5. Presents coaching and review information without hiding missing or rejected
   measurements.

Automated tests use simulated and synthetic inputs. They prove software
behavior; they do not prove real-world measurement accuracy.

## What is and is not validated

The project currently has software coverage for setup contracts, capture and
tracking behavior, evidence recording, replay, and validation gates. It does
not yet have an independently reviewed physical confirmation dataset for speed
or plate-location accuracy.

Do not describe a camera model, trajectory mode, or measurement error bound as
validated unless an active physical-validation approval explicitly covers the
exact rig, software, environment, protocol, and dataset.

## Run from source

Requirements:

- Windows 10 or 11;
- Python 3.13 or newer;
- no cameras for simulator development;
- two matching, qualified global-shutter UVC cameras for field testing.

```powershell
git clone https://github.com/berginj/PitchTracker.git
cd PitchTracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python setup_validator.py
python launcher.py --backend sim
```

For a camera-backed run, use the same launcher after setup, or run:

```powershell
.\run.ps1 -Backend uvc
```

Most automated tests do not require cameras:

```powershell
python -m pytest -q
```

## Setup workflow

The guided setup has ten stages:

1. Select cameras.
2. Verify paired preview.
3. Qualify synchronization.
4. Lock and verify focus and exposure controls.
5. Validate image overlap.
6. Compute coarse rectification.
7. Optionally refine with ChArUco.
8. Align camera coordinates to the measured field fixture.
9. Persist the rig profile and setup snapshot.
10. Review the quality report and blockers.

Completing the wizard does not establish physical accuracy. The setup snapshot,
calibration artifacts, physical approval, current preflight, and pitch evidence
must remain eligible.

## Hardware testing

Field testing requires a rigid mount, two matching cameras with stable
identities, a verified target capture mode, and an independent calibrated
reference device for accuracy claims. Read the [testing guide](docs/TESTING_NEEDED.md)
before collecting data. It explains what each test needs, what to record, and
how to keep development data separate from confirmation data.

## Privacy and safety

Frames, recordings, calibration files, logs, athlete information, and facility
details may be sensitive. Keep them local by default. Public reports should use
anonymized summaries, hashes, and filenames—not athlete media, raw serials,
private paths, or secrets.

## Documentation map

- [Documentation index](docs/README.md)
- [Quick Start](docs/QUICK_START.md)
- [Glossary](docs/GLOSSARY.md)
- [Current Status](docs/CURRENT_STATUS.md)
- [Roadmap](docs/ROADMAP.md)
- [Testing Help Needed](docs/TESTING_NEEDED.md)
- [Operator runbook](docs/OPERATOR_RUNBOOK.md)
- [Physical validation checklist](docs/PHYSICAL_VALIDATION_EXECUTION_CHECKLIST.md)
- [Architecture](docs/ARCHITECTURE_CURRENT_STATE.md)
- [Troubleshooting](docs/user/TROUBLESHOOTING.md)
- [Support](SUPPORT.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

Historical and exploratory material is retained under `archive/` and
`docs/archive/`; it is not current product status.

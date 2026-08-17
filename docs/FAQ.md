# PitchTracker Frequently Asked Questions

**Last reviewed:** 2026-08-16

**Applies to:** v2.0.0 and current `main`

## Installation and releases

### Is there a current v2 installer?

No. The published [`v2.0.0` release](https://github.com/berginj/PitchTracker/releases/tag/v2.0.0)
does not have an installer asset. Run from source for current testing. The older
v1.5 pilot installer is not the current v2 application.

A refreshed installer will be published only after clean Windows smoke testing,
artifact provenance recording, and checksum verification.

### How do I run from source?

Use Windows with Python 3.13 or newer:

```powershell
git clone https://github.com/berginj/PitchTracker.git
cd PitchTracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python setup_validator.py
python launcher.py
```

### Will a packaged installer require Python?

The PyInstaller-based package is intended to bundle its Python runtime and
dependencies. That statement applies only after a specific installer has been
built and smoke-tested; there is no current public v2 installer to rely on.

### Does PitchTracker check the internet?

The updater checks the public GitHub Releases API by default. It reports an
update only when a newer release contains an installer asset. Capture artifacts
remain local by default. Optional TAG/cloud synchronization is disabled unless
it is explicitly enabled and configured.

## Cameras and setup

### What cameras should I use?

Physical qualification requires two matching USB global-shutter cameras with
stable identities, an observed 60 FPS-or-better capture mode, and fixed or
lockable focus/exposure controls. See the
[candidate hardware profile](HARDWARE_PROFILE.md).

A catalog match helps discovery; it does not validate a model or physical pair.
Conventional rolling-shutter webcams may be useful for UI experimentation but
should not support an accuracy claim.

### Why are my cameras missing?

1. Close other applications that may hold the cameras.
2. Reconnect each camera directly to a USB port.
3. Confirm Windows camera permissions and Device Manager state.
4. Re-run discovery and compare stable hardware identities.
5. Review technical logs for backend, permission, or mode-negotiation errors.

OpenCV mode uses numeric indexes and is not stable enough for a production
multi-camera identity. Prefer the UVC backend and serial-based selection.

### Why is setup blocked?

Setup intentionally fails closed when evidence such as camera identity,
negotiated mode, control readback, synchronization, overlap, calibration, field
alignment, or artifact binding is missing or outside policy. Follow the
operator action shown, correct the physical condition, and run the affected step
again. Do not edit a report to convert failure into success.

### Does global shutter mean the cameras are synchronized?

No. Global shutter reduces within-frame motion distortion. Two independent USB
cameras can still capture at different times. PitchTracker records pair skew,
cadence, dropped frames, and unmatched outcomes; the onsite rig must satisfy the
configured synchronization gates.

### Is ChArUco optional?

The workflow can compute coarse rectification before optional ChArUco
refinement, but a physical accuracy claim still requires calibration and field
alignment evidence that satisfies the approved protocol. “Optional wizard
step” does not mean “optional evidence for validation.”

## Measurements and validation

### Are speed and plate location validated?

Not yet for a public accuracy claim. Automated tests cover software contracts,
failure paths, replay, and synthetic geometry. Independent physical confirmation
against a calibrated reference device remains open work.

### What do `run_in` and `rise_in` mean?

They currently represent raw first-to-last stereo-observation displacement in
inches. Durable summaries label the basis and set `movement_validated=false`.
They are not validated induced pitch break.

### What happens when evidence is missing?

The result should be unavailable, degraded, excluded, or rejected with a reason.
PitchTracker preserves attempted, accepted, rejected, unmatched, excluded, and
reference-missing denominators. Missing information must not be replaced by an
assumed pass or measurement zero.

### Can software correct a poor onsite setup?

Software can identify bounded corrective actions and retain raw-versus-corrected
records. It must not silently mutate calibration or manufacture an accuracy
claim. Material physical problems such as camera movement, insufficient overlap,
focus loss, or USB contention require onsite correction and a new setup snapshot.

## Recording, privacy, and support

### Where are sessions stored?

The recording service uses `recording.output_dir` from the active configuration;
the source-tree default is `recordings/`. Rig profiles default to
`calibration/rigs/`. Paths may differ in a packaged or customized deployment, so
check the active configuration and setup report.

### Is data uploaded automatically?

Camera frames, recordings, calibration artifacts, manifests, and athlete data
are local by default. The updater makes a GitHub API request. Optional cloud/TAG
features require explicit feature enablement, authentication, and a configured
adapter. Review configuration and logs before using any integration.

### What can I post in a public issue?

Post anonymized system facts, counts with denominators, failure codes, hashes or
filenames, and reproduction steps. Do not post athlete media, names, private
facility details, raw serial numbers, calibration files, trust keys, secrets, or
unreviewed logs.

### Where should I ask for help?

- Use [GitHub issues](https://github.com/berginj/PitchTracker/issues) for bugs and
  bounded feature requests.
- Use the Validation Report or Pilot Feedback forms for structured field results.
- Read [Testing Help Needed](TESTING_NEEDED.md) before submitting evidence.
- Report vulnerabilities privately through
  [GitHub Security Advisories](https://github.com/berginj/PitchTracker/security/advisories/new).

## Current sources of truth

- [Current status](CURRENT_STATUS.md)
- [Roadmap](ROADMAP.md)
- [Quick start](QUICK_START.md)
- [Troubleshooting](user/TROUBLESHOOTING.md)
- [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md)

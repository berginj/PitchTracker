# Testing Help Needed

PitchTracker needs external testing on real Windows hardware. Automated tests
cover software contracts and synthetic geometry, but they cannot prove camera
driver behavior, installation quality, or physical pitch accuracy.

## Who can help

- Developers with two UVC global-shutter cameras.
- Facilities with a rigid stereo mount and a safe bullpen or pitching lane.
- Testers with Windows 10/11 systems using different USB controllers.
- Teams with an independently calibrated radar or plate-location reference.
- Windows testers willing to install and remove a checksum-identified candidate
  build when one is explicitly provided for smoke testing.

You do not need to provide athlete video. Anonymized numeric reports are more
useful than unsupported success claims.

## Choose a test by what you have

| Test | Cameras | Independent reference | Typical time | What to return |
|---|---:|---:|---:|---|
| Installer smoke test | No | No | 30–60 minutes | install, launch, update, uninstall checklist |
| Camera discovery | Yes | No | 30–60 minutes | models, identities, modes, and pairing behavior |
| Capture qualification | Yes | No | 1–2 hours | frame/drop counts, achieved FPS, controls, and timing |
| Setup recovery | Yes | No | 1–2 hours | what happened after one reversible setup problem |
| Accuracy validation | Yes | Yes | multiple sessions | protocol-bound comparison report |

If you have no cameras, the installer smoke test and simulator workflow are
still valuable. If you have cameras but no reference device, stop at capture
qualification or setup recovery; do not call the result an accuracy validation.

The [glossary](GLOSSARY.md) explains terms such as global shutter, setup
snapshot, pair-skew, shadow dataset, confirmation dataset, and denominator.

## Choose a test

### 1. Installer smoke test — no cameras required

The current public `v2.0.0` release has no installer asset. Run this test only
with a candidate whose source commit, filename, and SHA-256 are supplied.

Verify install, first launch, simulator workflow, logs, update check, uninstall,
and reinstall on a clean Windows machine. Record Windows version/architecture,
security prompts, and the exact installer SHA-256.

Do not upload the installer, logs, or screenshots if they contain usernames,
private paths, tokens, or facility information.

### 2. Camera discovery and recommendation

Connect two or more cameras and record:

- Friendly name and stable hardware ID.
- Whether the camera is recognized as global shutter.
- Requested and negotiated resolution/FPS/pixel format.
- Which pair and sides are preselected and why.
- Whether unplug/replug preserves identity.
- Driver, firmware, and USB-controller information when available.

Do not mark a model validated from discovery alone.

### 3. Capture qualification

Run the setup burst and report both raw counts and rates:

- Frames requested/received per camera.
- Paired and unmatched frames.
- Drops and denominator.
- Achieved FPS and cadence jitter.
- Pair-skew p50/p95/p99.
- Control settings and verified readback.
- Setup assessment and every reason code.

Repeat once under normal conditions and once with a controlled problem such as
USB contention or exposure mismatch. Do not risk damaging cameras or mounts.

For every rate, report both the numerator and the opportunity count. For
example, “146 paired frames out of 151 opportunities” is useful; “96.7%” alone
is not.

### 4. Setup recovery

Introduce one reversible configuration problem at a time: swap camera sides,
change focus, alter exposure, reduce overlap, or shift the fixture. Confirm the
software identifies the problem, proposes a relevant action, and produces a new
snapshot after correction.

### 5. Ground-truth validation — reference equipment required

Read [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md) before
collecting confirmation data. Lock thresholds, strata, exclusions, and sample
counts in advance. Preserve rejected attempts and reference uncertainty. A
development dataset may guide fixes; only a separate confirmation dataset can
support approval.

Do not change code, calibration, thresholds, or correction rules after seeing
confirmation results. If you do, the data becomes development data and a new
confirmation run is required.

## Reporting results

Use the structured GitHub forms:

- [Validation Report](https://github.com/berginj/PitchTracker/issues/new?template=validation_report.yml)
- [Pilot Feedback](https://github.com/berginj/PitchTracker/issues/new?template=pilot_feedback.yml)

Include:

- Exact PitchTracker commit or version.
- Setup snapshot ID and fingerprint, not the private snapshot contents.
- Camera models and anonymized hardware identifiers if serials are sensitive.
- Windows, CPU architecture, driver, and USB-controller information.
- Protocol, denominators, numeric results, reason codes, and unexpected behavior.
- Hashes and filenames for locally retained evidence.

## Privacy and safety

Do not post:

- Athlete names, faces, or identifiable video.
- Private facility names, addresses, network details, or credentials.
- Raw calibration files, logs, or manifests before reviewing them for private
  paths and identifiers.
- API keys, tokens, or signed approval trust keys.

Keep raw media local unless a maintainer explicitly requests an authorized,
private transfer. Stop testing if camera mounts, cables, pitching activity, or
the test environment are unsafe.

## How results will be used

Reports will be triaged as software defects, hardware compatibility evidence,
setup guidance improvements, or physical-validation evidence. A report may
improve the known-good hardware matrix without granting an accuracy approval;
those are intentionally separate decisions.

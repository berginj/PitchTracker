> **Current repository status (2026-10-06):** This tag has no installer asset. Current `main` includes later software remediation, but eight software review follow-ups, issue acceptance reconciliation, physical qualification, signing, and clean-machine installer testing remain open. See [Current Status](https://github.com/berginj/PitchTracker/blob/main/docs/CURRENT_STATUS.md) and [Roadmap](https://github.com/berginj/PitchTracker/blob/main/docs/ROADMAP.md). The highlights and test counts below describe the historical tag, not current `main`.
# PitchTracker v2.0.0 — Stereo Foundation Rebuild

This release rebuilds the stereo camera foundation so the system can genuinely
**receive, pair, compare, and calibrate** left/right camera images before any
pitch-tracking logic runs.

## Highlights

- **Genuine 9-step stereo setup wizard** — a real `StereoSetupWindow` driven by a
  setup state machine: detect/select cameras → live paired preview → timestamp &
  sync check → manual fixed-focus + exposure lock → left/right overlap & feature
  match → targetless coarse rectification → optional ChArUco fine-tuning →
  persist calibration profile → calibration quality report. Wired into the
  launcher via a dedicated **Stereo Setup** role button.
- **Camera catalog service** — persistent catalog of known/supported cameras
  (Arducam global-shutter fixed-focus) with side assignment and model matching,
  so device state carries across sessions.
- **Capture-sync foundation** — paired stereo capture, timestamping, and
  left/right synchronization checks.
- **Stereo calibration hardening** — overlap/feature-match validation,
  targetless coarse rectification, and a calibration quality report widget.
- **ChArUco repositioned** as optional fine-tuning (intrinsics, distortion,
  scale/baseline validation) after the stereo pair is already operational.
- **ArduCam detection diagnostics** — `tools/diagnose_camera_detection.py` plus
  capability-probe tooling to debug inconsistent device enumeration.

## Engineering

- Live provider injection (`build_live_stereo_step_widgets`) keeps the wizard
  fully testable without hardware.
- `launcher.py` refactored under the 500-line guard; file-length CI gate
  restored to green.
- Full test suite: **1054 passed / 32 skipped**.

## Version

- `APP_VERSION = 2.0.0` (`contracts/versioning.py`), `SCHEMA_VERSION = 1.2.0`.
- Installer label: `PitchTracker-Setup-v2.0.0-stereo.exe`.

## Status

The tag records a stereo software foundation exercised with simulated inputs.
It does not establish physical speed/location accuracy or availability of a
current installer. Remaining work includes software review follow-ups as well
as real-rig qualification, independent physical confirmation, signing, and
clean-machine installer lifecycle tests. Use Current Status and Roadmap for the
current backlog rather than the historical stage count or test totals above.

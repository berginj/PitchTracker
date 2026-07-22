# PitchTracker Launcher Guide

**Last reviewed:** 2026-07-22

**Applies to:** v2.0.0 and current `main`

## Start the launcher

After installing source dependencies:

```powershell
python launcher.py
```

Or use the repository wrapper:

```powershell
.\run.ps1 -Backend uvc
```

The current public v2.0.0 release has no installer asset. See
[README_INSTALL.md](README_INSTALL.md) before using or distributing a locally
built package.

## Launcher roles

### Setup & Calibration

Use this role to select cameras, qualify capture and synchronization, calibrate
the stereo rig, align it to the field fixture, persist a rig profile and setup
snapshot, and review blockers. Long-running setup work belongs to tooling and
setup services, not the runtime orchestrator.

The canonical setup has ten steps. Completion alone does not grant physical
`VALIDATED` status.

### Coaching Sessions

Use this role for controlled capture and recording after the active rig profile
and preflight remain eligible. The operator view is intentionally compact;
detailed capture, matching, correction, and error diagnostics remain available
on demand and in durable evidence.

### Review

Use review workflows to inspect recorded sessions, videos, pitch artifacts,
summaries, and evidence. Offline replay can reconcile recorded decisions but
does not convert synthetic or incomplete evidence into physical validation.

## Data locations

Runtime paths are configuration- and working-directory-dependent:

- session output: `recording.output_dir` (`recordings/` in the default config);
- rig profiles: `calibration/rigs/` by default;
- update preferences: `configs/update_settings.json`; and
- logs and exported artifacts: as selected or configured by the workflow.

Do not assume that a packaged deployment uses the same absolute path as a source
checkout. Confirm the active configuration before backup, support, or uninstall
testing.

## Common startup problems

- **Missing imports:** activate the intended virtual environment and reinstall
  `requirements.txt`.
- **No cameras:** close other camera applications, check Windows permissions,
  reconnect directly to USB, and rerun discovery.
- **OpenCV IDs rejected:** OpenCV mode accepts numeric indexes; use UVC serial
  identities for production-style multi-camera testing.
- **Setup blocked:** follow the reported corrective action and rerun the affected
  step; do not bypass validation or edit persisted evidence.
- **No installer update:** the updater requires a newer GitHub release with an
  installer asset. The current v2.0.0 release has none.

## Current boundaries

- Default trajectory mode is `stereo_3d`.
- Ray modes remain comparison-first.
- Physical speed and plate-location accuracy are not publicly validated.
- Camera catalog recognition is not a known-good hardware claim.
- Missing information remains unavailable, degraded, excluded, or rejected.

See [Current Status](docs/CURRENT_STATUS.md),
[Quick Start](docs/QUICK_START.md), and
[Troubleshooting](docs/user/TROUBLESHOOTING.md).

# PitchTracker Launcher Guide

**Last reviewed:** 2026-10-14

**Applies to:** v2.0.0 and current `main`

## Start the launcher

After installing source dependencies:

```powershell
python launcher.py
```

For simulator use, run `python launcher.py --backend sim`. The default UVC
workspace also opens without acquiring or probing cameras. Prepare a session
or explicitly request camera actions in Setup to access hardware. Software
validation and update checks remain enabled in either mode.

Or use the repository wrapper:

```powershell
.\run.ps1 -Backend uvc
```

Both commands open the same persistent workspace. `python -m ui.qt_app` remains
a compatibility entry point; `--setup` opens the Setup destination.

The current public v2.0.0 release has no installer asset. See
[README_INSTALL.md](README_INSTALL.md) before using or distributing a locally
built package.

## Workspace destinations

Live, Sessions, Players and Setup share one window. Navigation preserves the
active session and selected historical content. The header reports runtime
recording status on every page; browsing history never changes the active pitcher.

### Setup

Choose **Open Guided Setup** to select cameras, qualify capture and synchronization, calibrate
the stereo rig, align it to the field fixture, persist a rig profile and setup
snapshot, and review blockers. Long-running setup work belongs to tooling and
setup services, not the runtime orchestrator.

The canonical setup has five stages: Cameras, Image checks, Calibration, Field
and regions, and Ready. During runtime capture it is view-only; stop preview
explicitly in Live before editing. Completion alone does not grant physical `VALIDATED` status.

### Live

Use this page for controlled capture and recording after the active rig profile
and preflight remain eligible. The operator view is intentionally compact;
detailed capture, matching, correction, and error diagnostics remain available
on demand and in durable evidence.

### Sessions and Players

The header owns the essential session controls on every page. Preparation opens
preview only; **Start Recording** remains explicit. Pending commands show progress
while navigation stays responsive. Failed operations preserve their last confirmed
state and expose a supported retry, including **Retry End Session**. After successful
finalization, choose **Review Session** or **New Session**. Summary availability and
measurement quality remain separate from recording state.

Sessions hosts local review; Players hosts roster browsing and management.
Choosing **View Sessions** records a browsing selection, not an active-pitcher
change. Player-based history filtering and safe pitcher attribution are later UX work.

Use review workflows to inspect recorded sessions, videos, pitch artifacts,
summaries, and evidence. Offline replay can reconcile recorded decisions but
does not convert synthetic or incomplete evidence into physical validation.

Exit offers **End Session and Exit** or **Cancel** for an owned recording.
The window stays open while workers and accepted work drain. If shutdown fails,
**Retry Exit** retains the same service owner instead of abandoning artifacts.

## Data locations

Source launches use the checkout's working directory. Frozen Windows builds use
`%LOCALAPPDATA%\PitchTracker\` for writable operator state:

- session output: `recording.output_dir` (`recordings/` in the default config);
- rig profiles: `calibration/rigs/` by default;
- update preferences: `configs/update_settings.json`; and
- logs and exported artifacts: as selected or configured by the workflow.

In a frozen build those relative defaults resolve beneath the operator-state
directory. Bundled defaults and assets remain inside the installation; updates
seed missing defaults without overwriting operator configuration. Uninstalling
the current build does not recursively remove operator data.

On the first default-path launch, legacy `configs`, `calibration`, `rois`, `data`,
`recordings`, and `logs` beneath the installation and its `_internal` directory
are copied into operator state without deleting originals or replacing existing
files. Migration skips links and does not rewrite absolute paths in configuration
or signed/durable evidence. An old absolute recording or calibration path can
therefore require explicit operator reselection after migration.

`PITCHTRACKER_DATA_DIR` selects an absolute writable state directory outside the
installation. An explicit override starts an isolated workspace and suppresses
automatic legacy migration; it does not change source-launch paths. State
initialization uses atomic hard links, so the selected filesystem must support
them (the usual local NTFS directory does). Confirm the active state and any
configured external destinations before backup or uninstall testing.

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

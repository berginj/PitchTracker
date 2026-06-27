# PitchTracker Current Status

**Last Updated:** 2026-06-26
**Release Identity:** v2.0.0-stereo
**Internal App Version:** `2.0.0` (`contracts/versioning.py`)
**Status:** Stereo-foundation rebuild complete in software; on-rig hardware validation pending

---

## Canonical Release

The canonical release is **v2.0.0-stereo** (the stereo-foundation rebuild). The
prior pilot build **v1.5.0-pilot** remains the last validated facility-pilot
artifact.

Use the v2.0.0-stereo label for:

- installer filenames: `PitchTracker-Setup-v2.0.0-stereo.exe`
- Git release/tag naming: `v2.0.0-stereo`
- documentation referencing the rebuilt stereo setup wizard

Use the internal app version **2.0.0** for:

- `contracts/versioning.py` (`APP_VERSION`, single source of truth)
- `installer.iss` `AppVersion`
- `updater.py` `CURRENT_VERSION`
- update comparisons that expect numeric semantic versions
- durable artifact `app_version` fields

---

## Stereo Foundation Rebuild (v2.0.0) — Completed

The v2.0.0 rebuild proves the product can receive, pair, compare, and calibrate
left/right images before any pitch-tracking logic runs.

- **Capture foundation:** buffer/callback locking, timestamp-at-read + frame-index
  gating for reliable L/R pairing, sync-start scaffolding, reconnect-race fix,
  L/R persistence by hardware id.
- **Camera catalog:** `CameraCatalogService` + contracts with publish/pull
  carry-over of known devices by hardware id (Arducam global-shutter support).
- **Genuine 9-step stereo wizard:** Qt-free `SetupStateMachine` + a registry of
  nine real, synthetic-testable step widgets (select cameras → paired preview →
  sync → focus/exposure → overlap → coarse rectify → optional ChArUco → persist
  → quality report), each with an injectable provider and view-model.
- **`StereoSetupWindow`** hosts the wizard and is wired into the role-selector
  launch path alongside the legacy Setup Wizard.
- **Real adapter providers** (`ui/setup/providers.py`): live UVC discovery + a
  camera-backed paired-preview provider, with hardware-free test doubles.
- **Test suite:** 1051 passed / 32 skipped / 0 failed.

### Pending (hardware/integration-bound — cannot run in CI)

1. On-rig validation of discovery + paired capture with the Arducam
   global-shutter cameras.
2. Live camera-context propagation feeding a real-camera step-2 preview provider
   from the capture service.
3. End-to-end physical stereo calibration producing the `report.json` the
   gate/quality steps consume.

---

## Current Product Position

PitchTracker is suitable for controlled pilot deployments where:

- cameras are installed in a fixed or repeatable facility setup
- a trained operator can run setup, calibration, and sessions
- pilots agree to structured usage feedback and validation collection
- accuracy claims are treated as pending until reference-equipment testing is complete

The stereo setup foundation is now rebuilt and fully covered by tests, but the
pilot remains pending on-rig camera alignment work and validation results.
PitchTracker should not yet be positioned as a casual self-service consumer
product.

---

## Current Architecture

The preferred runtime entry point is:

```python
from app.services.orchestrator import PipelineOrchestrator
```

The UI-safe wrapper is:

```python
from app.qt_pipeline_service import QtPipelineService
```

`InProcessPipelineService` remains in the repository as a legacy compatibility
path. New implementation work should use the service-oriented architecture
documented in `docs/ARCHITECTURE_CURRENT_STATE.md` and `agents.md`.

---

## Validation State

| Area | Current State | Required Next Step |
| --- | --- | --- |
| Version identity | Aligned around v2.0.0-stereo (`APP_VERSION` 2.0.0) | Keep patch releases on `v2.0.x-stereo` if needed |
| Stereo setup wizard | Genuine 9-step wizard complete; 1051 tests green | Validate the flow on a physical stereo rig |
| External release | `v2.0.0` tag pushed | Build + smoke-test the v2.0.0-stereo installer on a clean Windows machine |
| Architecture docs | Service-oriented + stereo-setup docs current | Keep calibration boundary explicit |
| Hardware profile | In validation testing | Record tested Arducam camera/mount evidence |
| Camera alignment | Blocking pilot start | Complete alignment and document results |
| Velocity accuracy | Protocol exists; validation testing in progress | Run reference-equipment validation |
| Location accuracy | Not yet published | Define and run target-grid validation |
| Pilot personas | Canonical doc added | Confirm with real pilot operators |
| GitHub feedback | Structured issue forms added | Triage `pilot-feedback` and `validation` issues |
| TAG Sports | Partnership docs active; waiting on TAG feedback | Update plan after response |

---

## Open Decisions

1. Which exact camera alignment result is sufficient to start the pilot?
2. What smoke-test checklist must pass before publishing today's release?
3. What support contact should be published as the real pilot support channel?
4. What policy should govern replacing the already-published installer with
   the refreshed package that excludes runtime-local config state?

---

## Current Priority

1. Finish camera alignment work required to unblock the pilot.
2. Run validation tests and record results through GitHub validation issues.
3. Smoke-test the refreshed installer on a clean Windows machine.
4. Update public-facing support/contact channels.
5. Keep new feature work behind the capability contract until pilot feedback
   proves demand.

---

## Calibration Boundary Explanation

`PipelineOrchestrator.run_calibration()` is a public API method inherited from
`PipelineService`, but the current implementation does not perform calibration.

Two choices exist:

- **Route calibration through the orchestrator:** one API can start capture,
  record, and run calibration. This is convenient for callers, but it makes the
  runtime orchestrator responsible for long-running setup/tooling work and adds
  release risk before validation.
- **Keep calibration in setup/tooling paths:** Setup Doctor and tooling services
  own calibration; the runtime orchestrator only starts once a rig profile is
  validated. This keeps the pilot runtime simpler and safer, but callers must
  use the setup/tooling workflow instead of calling `run_calibration()`.

Decision for v1.5.0-pilot: keep calibration outside the runtime orchestrator.
`PipelineOrchestrator.run_calibration()` now rejects the call with an
actionable setup/tooling message that points callers to Setup Doctor and
`SubprocessToolingService`.

---

## 2026-06-23 P2 Cleanup Record

- Full test suite: `841 passed, 32 skipped, 23 warnings in 514.55s`.
- Event metadata audit added: `docs/EVENT_METADATA_AUDIT.md`.
- Calibration boundary made actionable in `PipelineOrchestrator.run_calibration()`.
- Packaging allowlist added for PyInstaller config data.
- Rebuilt installer: `installer_output/PitchTracker-Setup-v1.5.0-pilot.exe`.
- Installer size: `92,200,172` bytes.
- Installer SHA256:
  `F211FC39FA4468281DA7B5BAED67581049ABADDC266EED1A4DA59039A1C999A2`.
- Verified bundled config data contains only `default.yaml` and
  `snapdragon.yaml`; runtime-local `app_state.json`, `roi.json`,
  `pitchers.json`, `.first_run_done`, `locations`, and cache directories are
  excluded.

# PitchTracker Current Status

**Last Updated:** 2026-06-23
**Release Identity:** v1.5.0-pilot
**Internal App Version:** `1.5.0` (`contracts/versioning.py`)
**Status:** Pilot prerelease published; validation testing in progress

---

## Canonical Release

The canonical pilot release is **v1.5.0-pilot**.

Use this label for:

- installer filenames: `PitchTracker-Setup-v1.5.0-pilot.exe`
- Git release/tag naming: `v1.5.0-pilot`
- pilot documentation and partner communication

Use the internal app version **1.5.0** for:

- `contracts/versioning.py`
- `installer.iss` `AppVersion`
- update comparisons that expect numeric semantic versions
- durable artifact `app_version` fields

---

## Current Product Position

PitchTracker is suitable for controlled pilot deployments where:

- cameras are installed in a fixed or repeatable facility setup
- a trained operator can run setup, calibration, and sessions
- pilots agree to structured usage feedback and validation collection
- accuracy claims are treated as pending until reference-equipment testing is complete

The pilot is currently pending camera alignment work and validation results.
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
| Version identity | Aligned around v1.5.0-pilot | Keep patch releases on `v1.5.x-pilot` if needed |
| External release | `v1.5.0-pilot` tag/release published | Validate the published installer on a clean Windows machine |
| Installer contents | Rebuilt 2026-06-23 with runtime-local config state excluded | Use checksum below for any redistributed refreshed installer |
| Architecture docs | Service-oriented docs current | Keep calibration boundary explicit for pilot |
| Hardware profile | In validation testing | Record tested camera/mount evidence |
| Camera alignment | Blocking pilot start | Complete alignment and document results |
| Velocity accuracy | Protocol exists; validation testing in progress | Run reference-equipment validation |
| Location accuracy | Not yet published | Define and run target-grid validation |
| Pilot personas | Canonical doc added | Confirm with real pilot operators |
| Test suite claims | Current full suite run recorded 2026-06-23 | Keep warning list visible in release notes if externally cited |
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

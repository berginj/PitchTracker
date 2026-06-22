# PitchTracker Current Status

**Last Updated:** 2026-06-22
**Release Identity:** v1.5.0-pilot
**Internal App Version:** `1.5.0` (`contracts/versioning.py`)
**Status:** Release candidate for controlled facility deployments; validation testing in progress

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
| Version identity | Aligned around v1.5.0-pilot | Release current version today |
| External release | Not yet tagged or published | Build, smoke-test, tag, and publish v1.5.0-pilot |
| Architecture docs | Service-oriented docs current | Keep calibration boundary explicit for pilot |
| Hardware profile | In validation testing | Record tested camera/mount evidence |
| Camera alignment | Blocking pilot start | Complete alignment and document results |
| Velocity accuracy | Protocol exists; validation testing in progress | Run reference-equipment validation |
| Location accuracy | Not yet published | Define and run target-grid validation |
| Pilot personas | Canonical doc added | Confirm with real pilot operators |
| Test suite claims | Historical docs exist | Run current suite before publishing external claims |
| GitHub feedback | Structured issue forms added | Triage `pilot-feedback` and `validation` issues |
| TAG Sports | Partnership docs active; waiting on TAG feedback | Update plan after response |

---

## Open Decisions

1. Which exact camera alignment result is sufficient to start the pilot?
2. What smoke-test checklist must pass before publishing today's release?
3. What support contact should be published as the real pilot support channel?
4. Should `PipelineOrchestrator.run_calibration()` remain an explicit
   setup/tooling boundary for v1.5.0-pilot?

---

## Current Priority

1. Finish camera alignment work required to unblock the pilot.
2. Run validation tests and record results through GitHub validation issues.
3. Build and publish the current v1.5.0-pilot release today.
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

Recommendation for v1.5.0-pilot: keep calibration outside the runtime
orchestrator, document the boundary, and replace the current generic
`NotImplementedError` with an actionable message in a later code pass.

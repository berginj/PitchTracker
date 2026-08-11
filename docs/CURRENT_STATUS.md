# PitchTracker Current Status

**Last updated:** 2026-08-11
**Published release:** `v2.0.0` / internal app version `2.0.0`
**Development status:** broad automated implementation on `main`; UI, test-lane,
performance, packaging, and physical-validation gates remain

## Summary

PitchTracker has a broad evidence-first software path for stereo setup,
capture, candidate tracking, global association, trajectory analysis, recording,
replay, correction accounting, and validation gating. The canonical setup now
persists a content-addressed system snapshot and recommends camera pairs using
prior validated hardware or measured catalog capabilities.

The architecture is ready for controlled engineering and simulator testing.
Field testing remains gated by the UI, camera, installer, and evidence work in
the 2026-08-11 review. It is not yet
appropriate to publish speed or plate-location accuracy claims because no
independently reviewed physical confirmation dataset has been approved.

## Release and build state

| Item | State |
|---|---|
| GitHub release | `v2.0.0`, published 2026-06-27 |
| Release installer asset | Not currently attached to the GitHub release |
| Current `main` | Includes PT-001–PT-015, adversarial follow-ups, and setup snapshot/camera recommendation work beyond the tag |
| Latest local clean build | Commit `40158c1`; PyInstaller and Inno Setup completed |
| Full automated suite | Historical CI: 1,267 passed, 32 skipped, 0 failed at `211d246`; current audit: 1,302 collected and serial offscreen 1,235 passed, 34 failed, 33 skipped on the dirty worktree |
| Physical accuracy approval | None; results must remain estimated/degraded/unavailable/rejected as evidence requires |

The locally built installer must be smoke-tested on a clean Windows machine
before it is attached to a refreshed release.

The current audit attributes the 34 displayed serial failures to video-writer
failure when Qt offscreen mode is set on the audit host; writers open outside
that mode. Ten UI workflow tests also skip behind an incorrect `pytest_qt`
import guard, and the coaching simulator window fails during construction. See
[the executive review](review/EXECUTIVE_REVIEW.md) for the evidence boundary.

## Delivered software

- Typed agent/service boundaries for capture, detection, pitch state,
  trajectory, recording, analysis, tooling, and UI.
- Ten-step evidence-gated setup workflow with interruptible capture and explicit
  failure paths.
- Stable camera identity, capability-based recommendation, and previous
  validated-pair preference.
- Setup snapshot containing host/software/camera/control/capture/calibration/ROI/
  field-transform/tracking/correction evidence and artifact hashes.
- Per-frame and per-candidate decision lineage, unmatched outcomes, terminal
  conservation, deterministic global stereo association, and replay.
- Raw/corrected measurement ledger, error budgets, drift monitoring, and compact
  operator guidance with advanced diagnostics on demand.
- Physical-validation v2 contracts, shadow/confirmation separation, independent
  signatures, and exact artifact/fingerprint binding.

See [PT-001–PT-015 traceability](PT_001_015_TRACEABILITY.md) for implementation
and automated evidence.

## What remains

The canonical open work is [ROADMAP.md](ROADMAP.md):

1. Qualify real global-shutter cameras, controls, synchronization, and USB paths.
2. Test setup repeatability and recovery from intentionally poor configurations.
3. Run predeclared physical ground-truth speed and plate-location validation.
4. Smoke-test the installer on clean Windows machines.
5. Finish verified UVC capability/control queries.
6. Publish a hardware matrix and operating envelope only from collected evidence.

## Product boundary

Appropriate today:

- Development and controlled facility testing.
- Fixed/repeatable rigs with trained operators.
- Simulator, replay, evidence inspection, and setup qualification.
- Shadow comparisons where PitchTracker results do not drive an accuracy claim.

Not yet supported as a public claim:

- A specific speed or location error bound.
- Casual self-service setup across arbitrary cameras.
- Automatic correction that silently changes calibration.
- Ray-mode superiority or production promotion.
- A camera model described as validated solely because it appears in the catalog.

## Calibration ownership

Heavyweight calibration remains in Setup Doctor and tooling services.
`PipelineOrchestrator` owns runtime wiring and intentionally does not absorb
long-running calibration algorithms. Runtime starts from a validated rig profile
and fails closed when required evidence or bindings are missing.

## How to help

See [Testing Help Needed](TESTING_NEEDED.md). Public reports should use the
GitHub Validation Report or Pilot Feedback form and must not include private
athlete media, facility data, secrets, or unreviewed logs.

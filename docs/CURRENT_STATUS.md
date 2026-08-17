# PitchTracker Current Status

**Last updated:** 2026-08-16
**Published release:** `v2.0.0` / internal app version `2.0.0`
**Development status:** production-readiness work is consolidated on `main`;
physical validation, native-thread teardown, packaging provenance, and global
mypy cleanup remain

## Summary

PitchTracker has a broad evidence-first software path for stereo setup,
capture, candidate tracking, global association, trajectory analysis, recording,
replay, correction accounting, and validation gating. The canonical setup now
persists a content-addressed system snapshot and recommends camera pairs using
prior validated hardware or measured catalog capabilities.

The architecture is ready for controlled engineering and simulator testing.
It is not yet appropriate to publish speed or plate-location accuracy claims
because no independently reviewed physical confirmation dataset has been
approved.

## Release and build state

| Item | State |
|---|---|
| GitHub release | `v2.0.0`, published 2026-06-27 |
| Release installer asset | Not currently attached to the GitHub release |
| Development baseline | `main`; use the checked-out commit for exact provenance |
| Test collection | Full Python 3.13 and 3.14 suites run in CI; use current CI output for the exact count |
| Latest focused validation | Rig-profile and setup-provider acceptance suites pass; the full Windows run remains authoritative for native teardown behavior |
| Static validation | Schema sync, public docs, file length, Flake8, strict typed clean zones, suppression policy, and a non-increasing mypy baseline are required; the global backlog remains |
| Physical accuracy approval | None; results must remain estimated/degraded/unavailable/rejected as evidence requires |

The locally built installer must be smoke-tested on a clean Windows machine
before it is attached to a refreshed release.

Historical review documents under `docs/review/` retain their original dates and
results. They are evidence archives, not current status. Current release work
must use this document and the roadmap below.

## Delivered software

- Typed agent/service boundaries for capture, detection, pitch state,
  trajectory, recording, analysis, tooling, and UI.
- Ten-step evidence-gated setup workflow with interruptible capture and explicit
  failure paths.
- Stable camera identity, capability-based recommendation, and previous
  validated-pair preference.
- Optional native DirectShow capability inventory with conservative OpenCV
  fallback and durable per-control provenance.
- Rig-profile validation/persistence and setup providers are split behind
  focused typed boundaries; issues #14 and #15 no longer require structural
  work.
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
2. Resolve native-thread teardown and complete lifecycle failure injection.
3. Run predeclared physical ground-truth speed and plate-location validation.
4. Smoke-test a signed installer on clean Windows machines.
5. Eliminate the global mypy baseline; every reduction must be committed and
   strict clean zones cannot regress.
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

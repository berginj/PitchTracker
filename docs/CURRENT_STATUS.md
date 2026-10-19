# PitchTracker Current Status

**Last updated:** 2026-10-16
**Published release:** `v2.0.0` / internal app version `2.0.0`
**Development status:** the October consolidation/remediation batch is implemented
and validated in software. The October 5 software follow-ups have implementations
in the measurement research change. Physical validation and clean-machine lifecycle/
installer qualification also remain.

The measurement research implementation adds Review-mode evidence inspection,
shadow case editing, independent evaluation and cancellable local exports.
Eight October software follow-ups now have implementations; see
[the acceptance ledger](review/RESEARCH_ACCEPTANCE_LEDGER.md). Physical reference,
confirmation, signing, and clean-machine gates remain operator-run work.
Local software checks are recorded in
[the research validation record](review/RESEARCH_VALIDATION_2026_10_10.md).
The guided setup change and its supported-runtime checks are recorded in
[the setup validation record](review/GUIDED_SETUP_VALIDATION_2026_10_11.md).
Native ARM64 numerical execution and issue acceptance are recorded in
[the platform and closeout record](review/PLATFORM_AND_ISSUE_CLOSEOUT_2026_10_12.md).
Optional BaseballCV integration adds twelve detector/stereo comparisons, a
separate monocular study, supervised ONNX workers and explicit live qualification.
Classical detection and stereo remain defaults. See
[the comparison workflow](BASEBALLCV_COMPARISON.md) for model import, dedicated
recording collection and admission gates. Supplied weights and field evidence
have not yet qualified any experimental profile.
Local tests and frozen-worker checks are recorded in
[the integration validation record](review/BASEBALLCV_VALIDATION_2026_10_13.md).

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
| Latest main CI validation | `3639247`: [CI run 38841574855](https://github.com/berginj/PitchTracker/actions/runs/38841574855) passed on Python 3.13/3.14, including native UVC and blocking dependency audits; use that run for exact counts and artifacts |
| Platform/closeout local validation | Python 3.13 and 3.14 each passed 1,942 tests with 45 optional skips; native ARM64 numerical tests passed 39/39, and each x64 client passed all three packaged ARM64 worker tests; mypy passed 823 files |
| Follow-up local validation | `b101740`: Python 3.13 and 3.14 each passed 1,833 tests with 34 skips; final `597c267` passed 30 focused tests on each runtime; static gates passed |
| Frozen artifact validation | Application source `597c267`: six source/frozen GUI and worker smoke tests passed with isolated state and camera checking disabled; see the October remediation record below |
| Static validation | Schema sync, public docs, file length, Flake8, suppression policy, and direct repository-wide mypy are required; no diagnostic baseline remains |
| Physical accuracy approval | None; results must remain estimated/degraded/unavailable/rejected as evidence requires |
| Native ARM64 numerical scope | Compiled kernel and standalone worker exercised on Snapdragon Windows ARM64; CUDA, MSVC production wheels and the full native GUI/video stack remain unqualified |

The October bundle passes simulator GUI and frozen-worker smoke tests, and a
fresh unsigned installer compiled successfully. The installer must be signed
and smoke-tested on a clean Windows machine
before it is attached to a refreshed release.

Historical review documents under `docs/review/` retain their original dates and
results. They are evidence archives, not current status. Current release work
must use this document and the roadmap below.

## Delivered software

The default launcher now opens one persistent workspace with Live, Sessions,
Players and Setup. Global recording status and explicit session actions remain
visible across pages; navigation preserves runtime ownership and historical
selection. Startup does not probe cameras. The
[UX-02 implementation record](review/ux/UX_02_IMPLEMENTATION.md) documents
software checks, synthetic screenshots and remaining manual qualification.
Session commands now run in a retained worker, with shared progress, confirmed
state and supported retry actions. See the
[UX-03 implementation record](review/ux/UX_03_IMPLEMENTATION.md).
Live now uses Latest Pitch, Session Trends and Games, with a resizable preview,
visible measurement provenance and Advanced Tools. See the
[UX-04 implementation record](review/ux/UX_04_IMPLEMENTATION.md).
Sessions now supports direct finalized-session review, configured local history,
linked pitch/video/metric selection and explicit degraded playback states. See the
[UX-05 implementation record](review/ux/UX_05_IMPLEMENTATION.md).
Setup now presents saved revision/readiness, and Players separates historical
browsing from service-confirmed active-pitcher changes. Attribution survives
pitch boundaries and delayed analysis without rewriting older recordings. See the
[UX-06 implementation record](review/ux/UX_06_IMPLEMENTATION.md).
Analytics and secondary dialogs now retain missing outcomes, provide chart/table
equivalents and share accessible controls. Help opens maintained local guidance.
See the [UX-07 implementation record](review/ux/UX_07_IMPLEMENTATION.md).
Complete journey and manual display/accessibility qualification remains in UX-08.
Its [qualification record](review/ux/UX_08_QUALIFICATION.md) now includes a complete
workspace simulator journey, recovery-layout fixes and the pending manual worksheet.

The older desktop/setup/pipeline paths are retired under
`archive/retired/2026-10-13`. Guided setup is the default for launcher, direct
construction and GUI smoke. The [rig walkthrough](RIG_VALIDATION_WALKTHROUGH.md)
separates setup readiness, measured reference-residual spread and independent
physical confirmation. Retirement validation belongs to the new code revision;
older frozen artifacts do not establish it.

The committed controlled-pilot changes address distorted-pixel geometry,
continuous strike-volume intersection, explicit timing and speed provenance,
weighted stereo fitting/eligibility, and dedicated deadline-bounded workers.
They also add analysis queue/latency and pre-roll diagnostics. These are not a
published release or independently confirmed physical performance. See the
[implementation plan](../DEVELOPMENT_PLAN.md) and
[pilot checklist](CONTROLLED_PILOT_CHECKLIST.md).
The [dated software validation record](review/PILOT_SOFTWARE_VALIDATION_2026_09_08.md)
records test scope, bundle hashes, warnings, and remaining manual gates.
The [October consolidation record](review/CONSOLIDATION_VALIDATION_2026_10_02.md)
records discovery cancellation, terminal launcher shutdown, source import
behavior, and removal of verified unused code. These lifecycle changes retain
the current worker-process dispatch and typed service ownership boundaries.
The [October remediation record](review/REMEDIATION_VALIDATION_2026_10_03.md)
records writable installed paths, data preservation, terminal recording/capture
ownership, updater shutdown, export provenance, and boundary uncertainty tests.

- Typed agent/service boundaries for capture, detection, pitch state,
  trajectory, recording, analysis, tooling, and UI.
- Five-stage guided setup with immediate saved configuration, metric calibration,
  paired field targets/holdouts, per-camera regions, and recording admission.
- Interruptible capture and explicit
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

1. Complete the operator-run research baseline and preserve regression coverage
   for the eight follow-ups in the acceptance ledger.
2. Complete the remaining reconciled criteria in #34–#36, #38 and #40;
   deterministic geometry/provenance criteria in #37/#39 are verified.
3. Qualify real global-shutter cameras, controls, synchronization, and USB paths.
4. Qualify bounded shutdown/reconnect and retry behavior on the target rig.
5. Run predeclared physical ground-truth speed and plate-location validation.
6. Smoke-test a signed installer on clean Windows machines.
7. Publish a hardware matrix and operating envelope only from collected evidence.

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

# PitchTracker Roadmap

**Last reviewed:** 2026-08-11
**Source of truth for open work:** this document and linked GitHub issues

This roadmap separates completed software work from physical evidence that
cannot be produced in CI. A checked box means the implementation and automated
contract are complete; it does not imply physical measurement accuracy.

## Completed in software

- [x] PT-001–PT-015 evidence-first field-robustness implementation.
- [x] Interruptible, deadline-bounded setup capture.
- [x] Candidate-level decision lineage, unmatched outcomes, global stereo
  assignment, durable journal, and offline replay reconciliation.
- [x] Physical-validation v2 protocol, datasets, reports, signatures, and exact
  fingerprint-bound approvals.
- [x] Canonical content-addressed setup-system snapshot.
- [x] Validated-pair-first camera recommendation with capability fallback.
- [x] Compact operator health/actions with detailed diagnostics on demand.
- [x] Clean Windows application and installer build from commit `40158c1`.
- [x] Automated regression run: 1,267 passed, 32 skipped, 0 failed at `211d246`.

Implementation evidence is mapped in [PT_001_015_TRACEABILITY.md](PT_001_015_TRACEABILITY.md).
The checked regression count is historical evidence for its named commit, not
a statement that the current dirty worktree or every guarded workflow is green.

## Audit remediation gates

The dependency-ordered source of audit findings and closure criteria is
[review/REMEDIATION_PLAN.md](review/REMEDIATION_PLAN.md). Before field hardening:

- [ ] Restore simulator coaching-window construction and unguarded UI smoke coverage.
- [ ] Correct the pytest-qt import guard and split Qt-offscreen from codec tests.
- [ ] Replace submitted-frame benchmark accounting with terminal conservation.
- [ ] Establish responsive minimum-size and accessibility evidence for setup,
  launcher, and review.
- [ ] Complete required message metadata across durable/asynchronous flows.

## Now: physical validation and tester feedback

### [R-001 — Global-shutter camera qualification](https://github.com/berginj/PitchTracker/issues/9)

Collect repeatable results across supported Windows systems and camera pairs.

Acceptance evidence:

- Stable hardware IDs and correct recommended left/right preselection.
- Requested and negotiated modes recorded for both cameras.
- Verified exposure/gain/focus/white-balance readback where applicable.
- Frame counts, drops, unmatched rate, achieved FPS, cadence jitter, and pair
  skew p50/p95/p99 captured with explicit denominators.
- Driver, firmware, and USB-controller information recorded or explicitly marked
  unavailable.

### [R-002 — Setup repeatability](https://github.com/berginj/PitchTracker/issues/9)

Run the canonical ten-step workflow after intentional poor configurations such
as camera swap, baseline shift, focus loss, exposure mismatch, USB contention,
and partial overlap.

Acceptance evidence:

- Setup blocks or degrades the correct condition.
- Operator guidance identifies a real corrective action.
- Re-running setup after correction produces a new snapshot and fingerprint.
- No correction silently mutates calibration or makes an accuracy claim.

### [R-003 — Physical ground-truth confirmation](https://github.com/berginj/PitchTracker/issues/10)

Execute [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md)
using an independent calibrated reference channel.

Acceptance evidence:

- Protocol, strata, exclusions, sample counts, and thresholds locked before the
  confirmation data is examined.
- Rejected and unmatched attempts retained in denominators.
- Speed bias/MAE/tail error and plate-location MAE/tail error reported with
  reference uncertainty.
- A separate confirmation dataset passes every required threshold.
- Collector and independent reviewer sign an approval bound to the exact rig,
  software, snapshot, artifacts, environment, and correction policy.

### [R-004 — Installer smoke testing](https://github.com/berginj/PitchTracker/issues/11)

Test the clean installer on Windows machines that do not have the development
checkout or Python environment.

Acceptance evidence:

- Install, first launch, setup entry, simulator run, log creation, update check,
  uninstall, and reinstall all complete.
- No repository-local calibration, ROI, recording, or cache data is bundled.
- Windows version, architecture, security warnings, and failure logs recorded.

### [R-005 — UVC capability inventory](https://github.com/berginj/PitchTracker/issues/16)

Replace best-effort control discovery with verified UVC control queries where
the backend supports them. The remaining implementation marker is
`calib/camera_capabilities.py`.

Acceptance evidence:

- Capability results distinguish supported, unsupported, permission denied, and
  unavailable.
- Tests cover device and query failures.
- Setup snapshots persist observed results without inventing defaults.

## Next: field hardening after evidence arrives

- Publish a known-good hardware matrix from qualifying reports.
- Define the supported operating envelope for lighting, baseline, distance,
  speed, ball type, and reference uncertainty.
- Turn repeated setup failures into bounded, audited correction proposals.
- Add anonymized replay fixtures for failures that can legally be shared.
- Publish a refreshed installer only after clean-machine smoke testing.
- Run limited facility pilots with measurable setup time, rejection rate,
  operator intervention, and repeatability targets.

## Engineering debt with active owners

- [Extract rig-profile validation responsibilities](https://github.com/berginj/PitchTracker/issues/14)
  so `app/services/rig_profile.py` can leave the file-length baseline.
- [Split setup providers by workflow boundary](https://github.com/berginj/PitchTracker/issues/15)
  so `ui/setup/providers.py` can leave the file-length baseline without moving
  pipeline or calibration logic into the UI.
- Use [OVERSIZED_MODULE_TRIAGE.md](OVERSIZED_MODULE_TRIAGE.md) as the
  churn-ranked ownership queue for the remaining grandfathered modules.

## Later or conditional

- Promote ray trajectory modes only after separate confirmation evidence.
- Expand ML defaults only after representative labeled data and regression gates.
- Activate TAG/cloud integrations only after partnership scope, privacy review,
  and dedicated implementation issues.
- Add new coaching dashboards only when pilot usage demonstrates a decision need.

## Not current commitments

Historical month-by-month estimates, old version task lists, and partnership
concept schedules remain useful context but are not the active backlog. Open
GitHub issues linked to R-001–R-005 are the executable work queue.

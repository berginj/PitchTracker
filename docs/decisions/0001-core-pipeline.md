# ADR 0001 — Core-Pipeline Rewrite Behind Service Boundaries

- **Status:** Accepted
- **Date:** 2026-06-30
- **Owner:** berginj
- **Supersedes / consolidates:** `docs/rewrite_decision.md`, `docs/architecture_audit.md`,
  `docs/core_pipeline_workback_plan.md`, `docs/implementation_plan.md`

## Decision

`REWRITE_CORE_PIPELINE` is **accepted**.

We will **preserve the service shell** — `PipelineOrchestrator`, the `EventBus`,
the Qt adapter, capture backends, camera manager/catalog, rig-profile service,
setup-wizard state machine, recording service, manifests/summaries, review UI,
and the trajectory failure-code pattern — and **rebuild the calibration →
triangulation → path-fit core** behind those stable service interfaces.

This is **not** a full from-scratch rewrite, and we are **not** continuing to
patch the current prototype geometry as if it were production-grade.

## Context

- Accuracy (velocity / location) has never been validated against a reference,
  despite extended effort. This is the gating product risk.
- `docs/architecture_audit.md` found the service runtime sound but the core
  geometry to be prototype-grade: scalar stereo fallback can silently produce
  wrong depth; `StereoObservation` covariance is unpopulated; detection
  confidence is circularity-only; stereo matching lacks global temporal
  consistency; plate metrics use only first/last observations.
- Continuing incremental patches risks a "finished-looking" UI over unvalidated
  physics.

## Scope & constraints

- **`stereo_3d` remains the primary trajectory mode.** Ray modes stay
  comparison/fallback until validated with field recordings.
- **No calibration logic in `PipelineOrchestrator`** — calibration lives in
  Setup Doctor / tooling paths (per repo architecture rules).
- The new core must land **behind narrow service interfaces**, incrementally,
  each piece testable with synthetic geometry + labeled fixtures before wiring.
- Each subsystem PR must keep CI green (full flake8, tests, file-length, schema).

## Target core subsystems (rebuild order)

1. `calibration` — full intrinsic/extrinsic acceptance (coverage, residuals,
   field-scale plausibility); demote scalar fallback as a production path.
2. `sync` — measured skew, offset estimation, rejection gates.
3. `triangulation` — calibrated 3D with **populated covariance** and reprojection
   residuals (wire `contracts/evidence.py` + `stereo/uncertainty.py`).
4. `stereo_matching` — epipolar/radius/time/motion correspondence with ambiguity
   scoring and global temporal consistency.
5. `detection` evidence — motion/contrast/size/stereo-agreement components, not
   circularity alone.
6. `path_model` + `quality` — robust offline fit, physical plausibility, and
   machine-readable accept/reject reasons.

## Consequences

- **First milestone is a single validated accuracy number** against a reference
  (radar or measured field target), not new features.
- The loose strategy docs above are now **subordinate to this ADR**; future
  direction changes update this record rather than adding new top-level docs.
- New work that does not advance a target subsystem or its validation is out of
  scope until the accuracy baseline is published.

## References

- `docs/rewrite_decision.md`, `docs/architecture_audit.md`
- `.github/copilot-instructions.md` (architecture rules, conventions)
- Prior strategic review (session, 2026-06-29)

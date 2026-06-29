# Rewrite Decision

## Recommendation

`REWRITE_CORE_PIPELINE`

Do not perform a full rewrite. Do not keep incrementally patching the current vision core as if it is already production-grade. The right move is to preserve the service shell and replace the calibration-to-path core behind stable boundaries.

## Rationale

- Calibration reliability is the gating issue. The code has full matrix support, but scalar fallback and config-local calibration values can still drive bad triangulation.
- Geometry correctness is not enforced strongly enough at runtime. A production session should require validated full calibration, sync quality, and field-scale plausibility checks.
- Detection is too heuristic for outdoor use. Classical frame/blob filters are useful candidates, not reliable ball facts.
- Data models are underpowered. `StereoObservation` has a covariance field, but it is not populated; detection, matching, and rejection evidence are not durable enough.
- Observability is incomplete. The project logs and reports some metrics, but it does not yet produce the visual/numeric audit trail needed to explain bad pitches.
- Testability is good at service and unit levels, but core accuracy needs synthetic geometry, labeled video fixtures, and field target regression tests.
- Continuing incremental patches risks making the UI and workflow look finished while the physics output remains unvalidated.

## Preserve

- `PipelineOrchestrator`, service boundaries, event bus, and Qt adapter.
- Capture backends, camera manager, simulator, camera catalog, and capture stats.
- Rig profile service, active profile selection, profile validation, and production-ready concept.
- Setup wizard state machine and step view-model pattern.
- Sync check, overlap check, coarse rectification, focus/exposure lock, and quality report contracts.
- Recording service, manifests, session summaries, review UI, and export scaffolding.
- Trajectory failure-code pattern and existing fitters as candidate implementations.

## Discard Or Demote

- Repo-wide hardware-specific stereo fallback values.
- Scalar stereo fallback as a production path.
- Quick calibration as any kind of production-ready calibration.
- Circularity-only detector confidence.
- Pairwise stereo matching without global temporal consistency.
- Plate metrics based only on first/last observations.
- Any accuracy claim not backed by calibration, sync, reprojection, and field-target diagnostics.

## Target Architecture

- `capture`: reliable left/right acquisition, timestamps, frame references, camera stats, and hardware status.
- `sync`: session-level timestamp pairing, measured skew, offset estimation, and rejection gates.
- `calibration`: full intrinsic/extrinsic calibration, calibration metadata, coverage, residuals, and acceptance.
- `rectification`: generated maps and diagnostic rectified views, separate from calibration solving.
- `detection`: per-camera candidate generation with evidence and confidence components.
- `tracking`: per-camera candidate association, missed detections, false-positive rejection, and track hypotheses.
- `stereo_matching`: epipolar/radius/time/motion based correspondence with ambiguity scoring.
- `triangulation`: calibrated 3D reconstruction with covariance and reprojection residuals.
- `path_model`: robust offline fitting, physical plausibility checks, and plate/release estimates.
- `quality`: pitch/session acceptance decisions with machine-readable reasons.
- `visualization`: fitted path overlays, residual plots, and calibration diagnostics.
- `export`: durable JSON/CSV/video artifacts designed for replay and future analysis.
- `diagnostics`: command-line and UI report generation for calibration, sync, detection, stereo, and fit quality.
- `config`: product defaults separate from rig/session generated state.

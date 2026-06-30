# Core Pipeline Workback Plan

> **Superseded by [ADR-0001: Core-Pipeline Rewrite](decisions/0001-core-pipeline.md).** This document is background/rationale; the authoritative decision, scope, and rebuild order live in the ADR.


## Goal

Make PitchTracker's 3D pitch path credible before investing more in detector tuning or UI polish. The plan works backward from a field-usable result: a pitch is accepted only when calibration, sync, detections, stereo geometry, triangulation, and path fitting all provide enough evidence to explain the result.

Decision: `REWRITE_CORE_PIPELINE`, preserving the current service shell.

## Stage 0: Guardrails And Baseline

Purpose: stop avoidable regressions while the core is rebuilt.

Work:

- Keep repo-wide defaults free of local rig calibration.
- Keep quick calibration out of production runtime paths.
- Document current architecture risks and target architecture.
- Add focused tests around default config and runtime calibration status.

Definition of done:

- Shared `configs/default.yaml` uses generic scalar fallback only.
- Local rig state lives in rig profiles, generated calibration artifacts, or ignored runtime files.
- Architecture audit, calibration review, tracking review, modeling review, rewrite decision, and implementation plan exist.
- Focused config/calibration tests pass.

Status: mostly complete.

## Stage 1: Calibration Report And Runtime Truth

Purpose: make calibration quality explicit and machine-readable.

Work:

- Build a read-only calibration report command for `stereo_calibration.npz`.
- Report required matrix keys, production readiness, calibration mode, RMS, per-image RMS stats, baseline, image size, config compatibility, and measured-baseline plausibility.
- Emit pass/warn/fail status with explicit reasons.
- Add tests for full, quick, missing, invalid, poor RMS, and baseline mismatch cases.

Definition of done:

- `tools/calibration_report.py` can be run against a calibration file and config.
- The report returns JSON suitable for support bundles and CI fixtures.
- A missing/quick/invalid calibration is not reported as production-ready.
- Tests cover the main report verdicts.

Status: complete for the first read-only report slice. Visual artifacts and field-target validation remain future work.

## Stage 2: Production Geometry Gate

Purpose: prevent believable but wrong 3D output.

Work:

- Add an explicit runtime policy: production analysis requires a production-ready full matrix calibration.
- Keep scalar stereo fallback available only for simulator, diagnostics, or explicitly named dev mode.
- Surface actionable startup errors in `RigProfileService` / `PipelineOrchestrator`.
- Persist the calibration report snapshot into session manifests.

Definition of done:

- Starting a production recording with missing, quick, invalid, or poor calibration fails loudly.
- Simulator/dev paths still work through an explicit opt-in.
- Session artifacts record the calibration profile and report used.
- Integration tests prove both reject and allow paths.

Status: complete for the current scope. Production runtime gating is implemented in rig-profile validation for physical backends, and session manifests now persist the active calibration profile ID plus the calibration report snapshot.

## Stage 3: Synthetic Geometry Testbed

Purpose: prove camera math independent of real detector quality.

Work:

- Add synthetic calibrated stereo cameras.
- Project known 3D points at plate, 40 ft, 50 ft, 60.5 ft, and off-axis locations.
- Add controlled pixel noise, sync offsets, baseline perturbation, and calibration perturbation.
- Verify triangulation error and confidence degradation.

Definition of done:

- Tests fail on sign errors, unit mistakes, coordinate-frame swaps, bad projection matrices, and excessive noise sensitivity.
- Expected error budgets are documented in tests.
- Synthetic fixtures are reusable by triangulation, ray, and path-model tests.

Status: started. Reusable synthetic calibrated-stereo fixtures now project known pitch-lane 3D points into both cameras and run the production calibrated matcher/triangulator. The first tests cover noiseless reconstruction, half-pixel noise budgets, baseline-scale failure exposure, non-rectified camera perturbations, epipolar rejection, and configured timestamp offsets. Stereo uncertainty is now wired into simple and calibrated matcher observation quality/confidence, covariance, observation diagnostics, pitch summaries, pitch manifests, and recording performance metrics. Observation diagnostics now produce `PASS`, `WARN`, or `REJECT` with machine-readable reason codes for low confidence, high depth uncertainty, insufficient observations, missing observations, and large gaps. A synthetic stereo-to-path-model test now projects a ballistic pitch through calibrated cameras, triangulates it, and fits the physics model to a plate-plane crossing. Ray-mode reuse and hard pitch rejection based on the observation verdict remain future slices.

## Stage 4: Field Validation Dataset

Purpose: replace guesswork with repeatable real-world fixtures.

Work:

- Record paired clips of static known targets near plate and in the pitch lane.
- Record controlled moving-object clips and real baseball/softball pitches.
- Save camera settings, rig profile, calibration report, sync report, ROI files, and operator notes.
- Add golden expected outcomes: target reconstruction error, accepted/rejected pitches, and approximate plate crossing.

Definition of done:

- At least one checked-in lightweight fixture or documented external fixture package exists.
- A developer can run one command to validate geometry and path output against the fixture.
- Failures identify whether calibration, sync, detection, stereo, or path fitting is responsible.

Status: started. A field fixture manifest contract, validator, scaffold command, CLIs, tests, and operator documentation now exist. The validator covers static target reconstruction checks and pitch-manifest expectations for observation quality, trajectory mode, and plate crossing. Reports now include component-level attribution for calibration, sync, field targets, and pitch manifests. The scaffold command copies lightweight manifests/reports from a recorded session into a fixture package without copying videos. Real recorded fixture packages still need to be captured from the target rig before accuracy gates should become hard production rejection rules.

## Stage 5: Evidence Data Model

Purpose: separate observations from conclusions.

Work:

- Define durable records for 2D candidates, per-camera tracks, stereo matches, 3D observations, fitted paths, and quality decisions.
- Add IDs linking each layer back to frames and detections.
- Add rejection reasons and confidence components.
- Populate covariance or uncertainty placeholders before using them for scoring.

Definition of done:

- A pitch can be replayed from recorded artifacts without hidden in-memory state.
- Every accepted 3D point traces back to source detections and stereo match diagnostics.
- Every rejected candidate has a reason.

Status: started. Durable evidence contracts now exist for 2D candidates, stereo matches, 3D observations, and pitch verdicts. The contracts are JSON-compatible, versioned, and tested for round-trip behavior plus independent mutable defaults. Runtime recording still needs to populate these records from detector, matcher, triangulation, and path-model stages.

## Stage 6: Offline Tracking And Stereo Association

Purpose: make the ball path robust to false positives and missed detections.

Work:

- Treat classical/ML detector outputs as candidates.
- Build per-camera temporal tracks with missed detection handling and velocity/size priors.
- Match tracks across cameras with epipolar, time, radius, and motion costs.
- Preserve one-camera rays for fallback fitting instead of dropping them.

Definition of done:

- Labeled fixture tests show improved recall and lower false-positive paths versus current pairwise matching.
- One-camera dropouts no longer automatically destroy an otherwise usable pitch.
- Ambiguous matches produce warnings or rejection instead of quiet bad triangulation.

## Stage 7: Path Model And Quality Decision

Purpose: make final outputs credible and explainable.

Work:

- Fit offline paths using robust inlier selection and nonlinear refinement.
- Back-project fitted paths into both cameras and compute residuals.
- Use calibration, sync, triangulation, and fit diagnostics to produce pitch verdicts.
- Publish plate crossing, release estimate, velocity, residuals, confidence, and rejection reasons.

Definition of done:

- Bad sync, sparse observations, non-monotonic Z, no plate crossing, implausible velocity, and high residuals all reject pitches.
- Accepted pitches include 2D overlays, 3D path, residual summary, and confidence.
- Confidence degrades under synthetic noise and real fixture degradation.

## Stage 8: Product Integration And Release Gate

Purpose: expose the rebuilt core without hiding uncertainty.

Work:

- Wire reports and verdicts into Setup Doctor, recording, review UI, and support bundles.
- Update docs and operator workflow.
- Run full tests plus hardware/fixture validation.
- Only publish accuracy claims backed by fixture results.

Definition of done:

- Full test suite passes.
- Hardware validation checklist passes on the target Arducam rig.
- Release notes state supported conditions, required calibration workflow, and known limitations.
- No production workflow can produce a final path without a quality verdict.

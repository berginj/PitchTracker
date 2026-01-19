# Trajectory Estimation Prompt for ChatGPT

You are implementing the next-gen trajectory estimation layer for a Windows-first Python app (OpenCV + PySide6 UI). The core pipeline must be UI-agnostic (NO Qt types in core). We already have a stereo pipeline that outputs per-frame 3D observations:

StereoObservation: fields include t_ns, left, right, X,Y,Z (feet), quality, optional covariance, confidence.

Coordinate system: feet. Z along pitch direction. Plate plane at plate_plane_z_ft. Gravity is along -Y (Y up).

Existing: time offset estimator from fiducials, stereo pairing tolerance, strike zone logic, per-pitch summaries.

## Goal

Implement an upgraded trajectory module with:

- A shared trajectory contract that supports batch and incremental/streaming updates with standardized residual reporting.
- A physics-based fitter: ballistic + quadratic drag using MAP (priors), robust loss, and optional per-pitch time offset refinement (bounded).
- A radar-constrained variant using a mixture model (good reading vs outlier) + per-session radar bias estimator.
- An image-space (pixel) model: joint left/right association (epipolar + motion) and a reprojection-error EKF (online) + RTS smoother (offline optional).
- A confidence framework returning expected plate-crossing error (not vibes) and diagnostics; include hooks for offline calibration.
- An ensemble selector: start with guarded hard selection; add a “gating model” interface (simple learned regressor later) that picks best model based on diagnostics and predicted plate error.
- Tests and fixtures: synthetic simulator (project?noise/outliers/time offset) and regression tests.

## Constraints

- Python 3.11+ on Windows.
- Use numpy everywhere.
- scipy is allowed (optimize, linalg) and preferred. If you add SciPy, isolate it so the module degrades gracefully (clear error if unavailable).
- OpenCV allowed for projection utilities if needed, but keep pure-numpy where possible.
- Real-time-ish: provide “realtime” mode with bounded iteration counts and fast codepaths; allow optional offline refinement.
- Don’t modify UI. Provide core APIs callable from pipeline.
- Keep existing coordinate conventions: feet, plate plane plate_plane_z_ft.
- No heavy MHT; only consider multiple hypotheses if association ambiguous (but default is single best).

## Deliverables (code + structure)

Create a new package trajectory/ with:

### A) Core data contracts (no Qt)

Implement dataclasses with type hints:

- TrajectoryFitRequest
- TrajectoryDiagnostics
- TrajectoryFitResult
- ResidualReport (standardized per-observation residuals: 3D ft, reprojection px, normalized residual, inlier flag)
- FailureCode enum (INSUFFICIENT_POINTS, ILL_CONDITIONED, TIME_SYNC_SUSPECT, RADAR_OUTLIER, NO_PLATE_CROSSING, NON_MONOTONIC_Z, OPT_DID_NOT_CONVERGE, etc.)

Also implement a streaming interface:

- TrajectoryFitterBase
- reset(request: TrajectoryFitRequest)
- add_observation(obs: StereoObservation) (or add batch)
- maybe_fit() returns optional TrajectoryFitResult for realtime
- finalize_fit() returns final result (offline)

The batch API should also exist:

- fit_trajectory(request) -> TrajectoryFitResult

### B) Physics + drag fitter (3D residuals)

Implement PhysicsDragFitter.

Dynamics:

state x = [X,Y,Z,Vx,Vy,Vz]

accel = gravity + drag

drag: a_drag = -k * ||v_rel|| * v_rel, with optional wind. k >= 0.

Estimation:

Robust weighted least squares / MAP using scipy.optimize.least_squares with robust loss (Huber or Cauchy).

Include a prior on k: residual (k - k0)/sigma_k. Provide default k0, sigma_k; allow per-session tuning.

Include per-pitch time offset parameter ?t with strong prior: (?t - ?t_fid)/sigma_dt and bounded to small range (e.g., ±5 ms). This is optional but ON by default for offline; ON with tighter bounds for realtime.

Use RK4 integration with fixed dt in seconds (e.g., 1–2 ms) for smooth optimization. Ensure unit correctness in feet/s and feet/s^2.

Initialization:

seed from a quick polynomial fit to XYZ vs t (or use existing stereo points to estimate initial velocity).

k seed small.

Bounds/sanity:

Vz positive and within plausible range

k within [0, k_max]

enforce monotonic Z in predicted trajectory (as a post-check; if violated, fail or penalize confidence).

Output:

Dense trajectory sampled on a time grid spanning observations.

Plate crossing (interpolate crossing at plate_plane_z_ft).

ResidualReport per obs.

Diagnostics: rmse_3d_ft, inlier ratio, condition number (from Jacobian), drag_param, drag_param_ok, max_gap_ms, notes.

### C) Radar hybrid fitter (mixture + bias)

Implement PhysicsDragRadarFitter extending the physics fitter:

Add radar measurement residual using a mixture model:

with probability a: Gaussian residual on speed

with probability (1-a): uniform/outlier

Implement as robust negative log-likelihood term or equivalently robust residual with explicit outlier probability estimate.

Support uncertain radar reference:

If request.radar_speed_ref is "unknown", match radar speed to the speed curve via smooth min across a small set of candidate times/planes (use softmin / log-sum-exp).

Bias model:

Implement RadarBiasEstimator persisted per session (in memory; caller can serialize).

Update bias only when vision confidence high: b <- (1-?)b + ?(v_radar - v_predicted_at_ref)

Provide get_corrected_speed() and diagnostic outputs: radar_residual_mph, radar_inlier_probability.

Implement a compare strategy:

Fit vision-only and vision+radar.

Prefer radar fit only if overall score improves and radar_inlier_probability above threshold; otherwise return vision-only and mark radar as outlier.

### D) Joint multi-view association + reprojection EKF/RTS

Implement image-space tracker pipeline:

JointAssociator:

Inputs: per-frame detections from left and right with timestamps, plus camera models.

Build candidate edges between left and right detections with costs:

- epipolar distance (use fundamental matrix or rectified assumption)
- disparity plausibility from last known depth (optional)
- motion consistency from previous frame

Solve assignment (Hungarian) per frame or small sliding window.

Output matched 2D pairs and unmatched (for gap handling).

ReprojectionEKF:

State: position and velocity in 3D: [X,Y,Z,Vx,Vy,Vz] (optionally include drag k as constant).

Process model: constant-acceleration with gravity; optional drag as fixed k or learned offline.

Measurement: pixel coords in both cameras: z = [uL,vL,uR,vR].

Measurement function: project 3D point into both cameras (include distortion if camera model has it).

Use EKF update with Jacobians (compute numerically if needed but keep efficient).

Online: output best estimate each frame, with covariance.

RTSSmoother (optional/offline):

Given EKF forward pass, run RTS to smooth the 3D path.

Output dense smoothed trajectory and diagnostics.

Diagnostics:

- reprojection RMSE px (overall and per camera)
- inlier ratio (gated updates)
- max gap
- consistency checks (left vs right residual distribution)

### E) Confidence as expected plate-crossing error + calibration hooks

Implement ConfidenceScorer:

For each result, compute plate crossing point/time and approximate uncertainty:

- If fitter has covariance: propagate to plate plane crossing uncertainty (approx via Jacobian / sampling).
- If no covariance: estimate from residual scale and geometry.

Output:

- expected_plate_error_ft (or separate X/Y error)
- map to confidence in [0,1] via configurable function (exp(-err/tau) etc.)

Add a calibration hook:

CalibrationCollector stores (confidence, realized_error) pairs for offline calibration.

Provide method skeleton to fit isotonic/sigmoid calibration later (don’t implement ML training fully; just scaffold and CSV export).

### F) Ensemble selector (guarded + gating interface)

Implement:

TrajectoryEnsembler:

Accept candidate results from physics, radar, reprojection.

Apply hard guards: must cross plate plane once; monotonic Z; plausible speed/accel.

Choose lowest expected_plate_error_ft (or highest confidence) among guarded candidates.

If two candidates are compatible (plate crossing within threshold and both high confidence), allow optional fusion (weighted average) BUT only when compatible.

Add GatingModel interface:

predict_expected_error(diagnostics_dict) -> float

Provide a default rule-based implementation now; keep interface so a learned regressor can be dropped in later.

### G) Tests + fixtures

Use pytest.

Synthetic simulator:

Generate a physics trajectory with known parameters.

Project to both cameras with known intrinsics/extrinsics.

Add noise, missed frames, outliers, timestamp jitter, per-pitch ?t error, slight extrinsic drift option.

Produce synthetic detections and stereo 3D observations.

Unit tests:

- Integrator correctness: k=0 matches analytic ballistic within tolerance.
- Drag monotonic speed check (allow small numerical tolerance).
- Projection/triangulation consistency.
- Optimizer convergence under noise/outliers.
- Radar mixture: outlier radar doesn’t ruin trajectory; inlier radar improves speed estimate.
- Joint association: swaps are rare under moderate noise/outliers.
- EKF/RTS: smoothing reduces reprojection RMSE on held-out frames.

End-to-end metrics assertions:

- plate crossing error < threshold on synthetic
- expected_plate_error correlates with actual (basic monotonic check)

### H) Logging/diagnostics

Use standard logging module.

Add to_dict() methods for diagnostics and results for easy JSON export.

Camera model requirements:

Implement a small CameraModel class (or adapt existing) with:

- intrinsics: fx, fy, cx, cy
- distortion optional: k1,k2,p1,p2,k3
- extrinsics: R,t (world to cam)
- project(XYZ)->(u,v) and jacobian_project(XYZ)->2x3 (analytic if possible, else numeric)

## Acceptance criteria

- Running pytest passes on Windows.
- PhysicsDragFitter.fit_trajectory() returns stable results on synthetic data with outliers and small ?t error.
- Radar outliers do not degrade results (radar_inlier_probability low + vision-only preferred).
- Reprojection EKF runs fast enough for realtime mode (document iteration counts and complexity).
- Every result includes:
  - plate crossing solution
  - per-observation residual report
  - diagnostics with failure codes/notes
  - expected plate error and confidence
- Core package contains no Qt imports.

## Implementation notes / pitfalls to avoid

- Keep all units consistent (ft, s). Convert mph?ft/s carefully.
- Don’t let drag k absorb everything: use priors.
- Keep ?t bounded; don’t let it drift wildly.
- Don’t fuse incompatible models (averaging contradictions is bad).
- Robustly handle missing covariances (fallback to isotropic weights from quality).

## Output instructions

Implement the full module with clean code organization, docstrings, and type hints. Include example usage in a examples/trajectory_demo.py that runs synthetic simulation, fits all models, and prints a JSON-like summary.

# Workback List

## Prioritized Outcomes
1) Plate-crossing location accuracy (highest value; expected plate error).
2) Accurate near-plate path reconstruction (higher value closer to plate).
3) Full flight path from release to plate (lower value, still useful for coaching/visuals).

## Workback Milestones
- Define trajectory contracts + diagnostics + residual reporting.
- Build synthetic simulator + fixtures for plate-crossing accuracy.
- Implement physics+drag fitter with plate-crossing confidence.
- Add radar bias estimator + mixture model; ensure outlier handling.
- Implement image-space reprojection EKF/RTS for near-plate smoothing.
- Implement confidence scorer tied to expected plate error.
- Ensemble selector with guarded hard selection (plate-crossing first).
- Integrate into pipeline + JSON diagnostics export.
- Add regression tests for plate crossing and near-plate path quality.
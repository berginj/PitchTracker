# Path Modeling Review

## Verdict

The trajectory layer is more mature than the detection layer, but it is only as good as the measurements it receives. The current path model should be preserved as a candidate fitter, not treated as proof of accuracy. The missing pieces are uncertainty, outlier handling before fitting, field-coordinate validation, and pitch-level error budgets.

## Raw 3D Observation Handling

Current state:

- `StereoObservation` carries `X`, `Y`, `Z`, `quality`, optional `covariance`, and confidence.
- Current triangulators do not populate covariance.
- `PitchAnalyzer` passes stereo observations directly into trajectory fitting.
- Observation diagnostics summarize duration, rate, gaps, Z span, and mean confidence.

Risks:

- Bad stereo matches become 3D points before there is a robust temporal model.
- There is no measurement covariance from pixel localization, disparity, baseline, calibration residual, or sync skew.
- Outlier rejection largely happens inside the fitter through robust loss and residual checks, not as a structured observation-selection stage.
- Gaps and sparse observations are reported but not strongly tied to pitch acceptance.

Required rewrite behavior:

- Store raw detections, candidate tracks, stereo matches, triangulated observations, and fitted path as separate durable layers.
- Attach uncertainty and residual diagnostics to every accepted 3D observation.
- Reject physically impossible observation sequences before fitting.

## Physical Modeling

Current state:

- `trajectory/physics.py` fits a ballistic-plus-drag model using nonlinear least squares.
- Gravity is modeled as `-32.174 ft/s^2` on the Y axis.
- Drag is parameterized by a fitted scalar with bounds.
- Ray reprojection and ray graph modes exist in `trajectory/ray_fit.py`.

Strengths:

- The model is more defensible than a simple parabola.
- Failure codes exist for insufficient points, no plate crossing, non-monotonic Z, missing camera models, and optimization failure.
- Ray modes can fit directly against per-camera pixel observations when full camera models exist.

Weaknesses:

- Drag parameter bounds and priors are generic and not clearly validated for baseball vs softball.
- Spin/Magnus effects are not explicitly modeled, so break attribution can be misleading.
- The fitter has no direct knowledge of per-point covariance.
- The model can produce a confident-looking result if upstream observations are biased by bad calibration.

## Offline Fitting

The system does not need real-time path display. That is an advantage. The final pipeline should use offline processing:

- Generate candidates in each camera.
- Build per-camera tracks with missed-detection handling.
- Match tracks and rays across cameras.
- Triangulate with uncertainty.
- Fit path with robust loss, RANSAC or graph inlier selection, and nonlinear refinement.
- Back-project the fitted path to both camera videos and compute pixel residuals.
- Produce confidence intervals or at least a calibrated error band at plate crossing.

## Output Requirements

Current `PitchSummary` and manifests include plate crossing, model, expected error, confidence, comparison results, ray RMSE, estimated time offset, failure codes, and observation stats. That is a useful start.

Missing durable outputs:

- Accepted/rejected detection candidates by frame.
- Stereo match list with epipolar error, time delta, ambiguity, and triangulation residual.
- 3D observation covariance or uncertainty estimate.
- Fitted path samples at fixed time/depth intervals.
- Per-camera reprojection overlays and residual summary.
- Pitch acceptance decision with machine-readable reasons.
- Calibration/session quality snapshot used by the fit.

Minimum credible output:

- 3D fitted path in field coordinates.
- Plate crossing point and time.
- Release estimate and velocity estimate with source reference.
- 2D overlays for left and right videos.
- Confidence score tied to explicit residuals, sync quality, calibration quality, and track completeness.

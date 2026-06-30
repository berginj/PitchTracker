# Implementation Plan

> **Superseded by [ADR-0001: Core-Pipeline Rewrite](decisions/0001-core-pipeline.md).** This document is background/rationale; the authoritative decision, scope, and rebuild order live in the ADR.


## Minimal Viable Reliable System

Build the geometry truth path before optimizing ball detection.

1. Require production-ready full matrix calibration for any serious analysis run.
2. Remove repo-default hardware calibration state and keep local rig geometry in rig profiles.
3. Add synthetic stereo geometry tests that project known 3D points, triangulate them, and verify coordinates at 40 ft, 50 ft, 60.5 ft, and plate distance.
4. Add a calibration report command that emits numeric metrics and visual artifacts from a saved calibration.
5. Add a field-target validation workflow using known points near the plate and lane.
6. Only after geometry passes, upgrade candidate detection and offline tracking.

Defer:

- Spin/Magnus modeling.
- Fully trained ML detector.
- Real-time path display.
- Cloud upload or external analytics.

Do not build:

- Another UI-only calibration flow without numeric/visual acceptance gates.
- Any path summary that lacks calibration, sync, and residual context.
- Production reliance on quick calibration or scalar fallback.

## Calibration Workflow

Recommended target:

- Rigid ChArUco board or AprilTag grid on a flat matte backing.
- Large enough to localize corners reliably at setup distances.
- Board metadata saved with square size, marker dictionary, print scale, and target ID.

Capture procedure:

- Lock focus, exposure, gain, white balance, frame rate, resolution, and pixel format first.
- Capture at least 20 accepted stereo pairs.
- Cover image center, corners, near/far distance, yaw, pitch, and roll.
- Reject blurred, saturated, low-corner, mixed-type, or mismatched-corner captures.
- Save all accepted/rejected image paths and reasons.

Validation:

- Full matrix calibration only for production.
- RMS <= 1.0 px preferred, <= 2.0 px marginal, > 2.0 px fail.
- p95 epipolar error <= 2.0 px.
- Baseline must be plausible against measured camera spacing.
- Rectified visual pair must show horizontal alignment.
- Field target reconstruction error near plate should be <= 3 in for MVP.

Recalibrate when:

- Cameras, mount, lenses, focus, resolution, or field location changes.
- The rig is bumped.
- Sync/epipolar/field-target validation fails.
- Calibration age exceeds the configured interval and validation cannot prove stability.

Session report format:

- Camera serials, mode, controls, calibration profile ID, calibration age.
- Intrinsic/extrinsic metrics, board coverage, rejected captures.
- Sync stats and ball-travel equivalent.
- Field-target validation error.
- Pass/warn/fail verdict with explicit reasons.

## Capture Workflow

Setup checklist:

- Confirm left/right serials match active rig profile.
- Confirm mount is rigid, behind catcher, and not obstructed by netting/glove position.
- Confirm both cameras see mound-to-plate lane and plate region.
- Confirm exposure is short enough to limit motion blur.
- Confirm gain is not so high that noise dominates small-object detection.
- Confirm frame rate and resolution match calibration.

Per-session validation:

- Record a paired preview sample.
- Run sync check and reject poor skew.
- Save one diagnostic left/right frame pair.
- Confirm ROI overlays match current field view.
- Capture a short test clip with a known moving object or field target before pitch analysis.

## Data Model

Durable records should be layered:

- Camera intrinsics: matrix, distortion, image size, camera serial, focus/control state, RMS, per-image errors.
- Stereo extrinsics: `R`, `T`, `E`, `F`, baseline, calibration target metadata, acceptance verdict.
- Rectification maps: source calibration ID, image size, maps or reproducible parameters, rectified preview artifacts.
- Session metadata: rig profile, camera mode, sync stats, weather/lighting notes if available, operator notes.
- Frame references: camera ID, frame index, timestamp, video file, optional extracted key frame path.
- 2D detections: center, radius, confidence components, candidate source, ROI state, rejection flags.
- Stereo matches: left/right detection IDs, time delta, epipolar error, ambiguity score, match status.
- 3D observations: point, covariance/uncertainty, residuals, quality, source match IDs.
- Fitted path: model name, samples, plate/release estimates, velocity, residuals, confidence, failure codes.
- Quality metrics: pitch verdict, session verdict, reasons, thresholds, and diagnostics artifact paths.

## Test Strategy

- Unit tests for calibration report parsing, config validation, sync pairing, match scoring, and quality verdicts.
- Synthetic geometry tests with known cameras, known 3D points, projection, triangulation, and uncertainty checks.
- Calibration regression tests using saved small fixture sets with expected RMS and rejected image reasons.
- Triangulation tests for full matrix geometry, scalar diagnostic fallback, zero/negative disparity, and out-of-range points.
- Detection tests using labeled frames for ball, glove, bat, dirt, fence, and shadow false positives.
- End-to-end pitch fixture tests with golden videos and expected accepted/rejected pitch decisions.
- Error budget tests that inject pixel noise, calibration error, and sync skew to prove confidence degrades.

## Diagnostics

Required visual outputs:

- Calibration board coverage per camera.
- Projected corners on calibration images.
- Undistorted and rectified preview pairs.
- Epipolar line overlays.
- Detection candidate overlays.
- Fitted 3D path and per-camera reprojection overlays.
- Residual plots over time/depth.

Required numeric outputs:

- Intrinsic RMS, stereo RMS, epipolar p50/p95/max.
- Sync p50/p95/max and ball-travel inches.
- Detection counts, false-positive candidates, missed frames, one-camera dropout.
- Triangulation uncertainty by point.
- Fit RMSE, inlier ratio, max gap, plate crossing expected error.
- Machine-readable reject reasons.

Commands for developers:

- `python -m pytest tests/test_config.py tests/test_stereo_triangulation.py tests/test_quick_calibrate.py tests/test_sync_check.py tests/test_quality_report.py`
- `python -m pytest` for full validation after core changes.

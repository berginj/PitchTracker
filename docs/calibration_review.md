# Calibration And Stereo Geometry Review

## Verdict

The calibration stack contains useful pieces, but the production geometry path is not rigorous enough for a behind-catcher baseball/softball system. The biggest problem is not OpenCV itself. The problem is that calibrated matrix geometry and legacy scalar fallback geometry coexist, while runtime acceptance does not yet prove that a session is accurate at field distances.

## What Appears Salvageable

- Full matrix calibration in `calib/quick_calibrate.py` saves `mtx_left`, `dist_left`, `mtx_right`, `dist_right`, `R`, `T`, `E`, `F`, `img_size`, quality metrics, and `production_ready`.
- `PipelineInitializer.create_stereo_matcher()` correctly ignores quick-mode calibrations for live tracking unless explicitly allowed.
- `CalibratedStereoMatcher` uses calibrated projection matrices and a fundamental-matrix epipolar check.
- Rig profiles in `app/services/rig_profile.py` are the right place for camera serials, transforms, calibration file paths, ROI files, and quality metrics.
- Setup modules already include sync checking, focus/exposure lock contracts, overlap validation, coarse rectification, and quality report aggregation.

## What Is Brittle

- The repo-wide `configs/default.yaml` has been used as both product default and local rig state. That is unsafe. Hardware-specific baseline/focal/principal-point values must live in a rig profile or generated calibration artifact.
- Scalar fallback in `stereo/simple_stereo.py` assumes parallel rectified cameras. Behind-catcher cameras are often toe-in, rolled, vertically offset, or bumped. Scalar fallback should be treated as diagnostic only, not production tracking geometry.
- Quick calibration fixes principal point and sets distortion to zero. That may help setup feedback, but it is not an outdoor production calibration for fixed-lens cameras.
- Full calibration reports RMS and per-image errors, but the runtime does not require per-image distribution, board coverage, epipolar residual distribution, or field-scale target validation.
- Distortion is saved, but downstream uncertainty and rectification quality are not carried into each triangulated observation.
- Software timestamp pairing can pass under light testing but still corrupt geometry when independent USB cameras drift or jitter during a fast pitch.

## What Must Be Rewritten

- Runtime geometry acceptance: live tracking should require a production-ready rig profile with full matrix calibration, sync report, ROI report, and quality report. Scalar fallback should not silently drive serious analysis.
- Calibration report generation: reports must include per-camera RMS, per-image RMS, rejected images, board coverage, stereo epipolar statistics, baseline plausibility, and before/after visual artifacts.
- Triangulation contract: every 3D point should carry uncertainty, reprojection residuals, epipolar error, source detections, and rejection reasons when unavailable.
- Session validation: each session should run a short field validation clip or target check before pitches are accepted.

## Missing Diagnostics

Required numeric outputs:

- Per-camera intrinsic RMS and per-image reprojection RMS.
- Stereo RMS plus mean, median, p95, and max epipolar error.
- Baseline estimate in inches with expected/measured difference.
- Triangulation uncertainty at 40 ft, 50 ft, 60.5 ft, and plate distance.
- Sync p50/p95/max skew in milliseconds and ball-travel inches.
- Calibration age, camera serial match, resolution match, and focus/exposure lock status.

Required visual outputs:

- Calibration board coverage heatmaps for each camera.
- Rejected board image thumbnails with reason.
- Before/after undistortion examples.
- Rectified stereo pair with horizontal epipolar lines.
- Projected board corners over source images.
- Field validation overlay showing known target points and reconstructed error.

## Recommended Workflow

Use ChArUco or AprilTag-grid style targets, not plain checkerboard-only capture. The target must be rigid, flat, matte, high contrast, and large enough to produce reliable corner localization at the working distances used during setup.

Procedure:

- Lock focus, exposure, gain, white balance, resolution, frame rate, and pixel format before any calibration capture.
- Capture at least 20 stereo pairs for a full calibration, with the board visible in both cameras and covering corners, center, near/far portions, yaw, pitch, and roll variation.
- Reject captures with blur, saturation, low corner count, mixed detection types, or inconsistent left/right corner IDs.
- Use quick calibration only for setup feedback. Never mark it production-ready.
- Persist full calibration in a rig profile, not in the shared default config.
- Recalibrate when the cameras move, mount is bumped, focus changes, resolution changes, lens changes, or validation target error exceeds threshold.
- At session start, run sync validation and a short known-target or marked-field validation before accepting pitch data.

Acceptance defaults for MVP:

- Full matrix calibration required for production tracking.
- Overall RMS <= 1.0 px preferred, <= 2.0 px marginal, > 2.0 px fail.
- p95 epipolar error <= 2.0 px.
- Sync p95 ball-travel error <= 4 in at target speed; max <= 6 in.
- Field target reconstruction error at plate distance <= 3 in before claiming usable plate-location output.

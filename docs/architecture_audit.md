# PitchTracker Architecture Audit

> **Superseded by [ADR-0001: Core-Pipeline Rewrite](decisions/0001-core-pipeline.md).** This document is background/rationale; the authoritative decision, scope, and rebuild order live in the ADR.


## Summary

PitchTracker has a useful service-oriented shell, but the core vision pipeline is still a mix of production boundaries and prototype geometry. The event-driven runtime in `app/services/` is worth preserving. The highest risk is inside calibration, scalar stereo fallback, detection confidence, stereo correspondence, and path-quality semantics.

Recommendation from this audit: keep the orchestration/capture/recording/UI scaffolding, but rewrite the core calibration-to-path pipeline behind those boundaries before making outdoor accuracy claims.

## Current Architecture

The preferred runtime entry point is `app/services/orchestrator/pipeline_orchestrator.py`. It wires capture, detection, recording, analysis, and the pitch state machine through an in-process `EventBus`.

Main subsystems:

- Capture: `app/services/capture/implementation.py`, `app/pipeline/camera_management.py`, `capture/uvc_backend.py`, `capture/opencv_backend.py`, and `capture/simulated_camera.py`.
- Calibration/setup: `ui/setup/`, `calib/quick_calibrate.py`, `calib/stereo_setup/`, `calib/sync_check.py`, `app/services/tooling/`, and `app/services/rig_profile.py`.
- Detection/tracking: `app/services/detection/implementation.py`, `app/pipeline/detection/processor.py`, `detect/classical_detector.py`, `detect/modes.py`, `detect/filters.py`, and `track/trajectory_tracker.py`.
- Stereo geometry: `stereo/simple_stereo.py`, `stereo/calibrated_stereo.py`, `stereo/association.py`, and `app/pipeline/utils.py`.
- Pitch lifecycle: `app/pipeline/pitch_tracking_v2.py`.
- Path modeling: `trajectory/physics.py`, `trajectory/ray_fit.py`, `trajectory/registry.py`, and `trajectory/contracts.py`.
- Analysis/export/persistence: `app/pipeline/analysis/pitch_summary.py`, `app/services/analysis/implementation.py`, `app/pipeline/recording/`, `record/`, `visualization/`, and review UI modules.
- Config/persistence: `configs/default.yaml`, `configs/settings.py`, `configs/validator.py`, `calibration/stereo_calibration.npz`, `calibration/report.json`, `calibration/rigs/*/rig_profile.json`, recording manifests, summary JSON/CSV, videos, and timestamp CSVs.

The runtime flow is mostly sound: capture publishes frame events, detection consumes frames and publishes stereo/ray observations, the orchestrator feeds pitch state, analysis consumes finalized pitch data, and recording persists artifacts. This is a good skeleton.

## Current Assumptions

- Cameras are treated as a left/right stereo pair behind the catcher, with Z increasing toward home plate according to `metrics.coordinate_system`.
- If a production calibration NPZ is available, `CalibratedStereoMatcher` uses full matrices. If not, runtime falls back to scalar `baseline_ft`, `focal_length_px`, `cx`, and `cy` from config.
- The scalar fallback assumes rectified, parallel cameras with horizontal epipolar lines and a simple depth formula. That is not a safe model for a behind-catcher rig that may be yawed, rolled, shifted, or bumped.
- Full calibration uses OpenCV intrinsics, distortion, stereo extrinsics, and a fundamental matrix. Quick calibration fixes principal point, forces zero distortion, and is explicitly marked non-production.
- Frame sync is software timestamp based by default, with optional frame-index pairing. The code reports timing skew in ball-travel inches, but there is no hardware trigger model.
- Classical detection assumes the ball can be found by frame differencing, background differencing, edge/blob masks, area/circularity filters, and ROI gates.
- Baseball and softball are mostly represented by ball radius and default pitch-distance configuration. Detection thresholds and model fitting are not strongly ball-type specific.
- Strike-zone and plate metrics assume the configured field coordinate frame is correct. `compute_plate_from_observations()` derives run/rise from first and last observations, not from a robust plate-crossing model.

## Failure Modes

Calibration and geometry:

- A missing or rejected calibration file falls back to scalar geometry. This can silently produce physically wrong depth if config contains rig-specific or stale values.
- `SimpleStereoMatcher` clamps near-zero disparity to 0.5 px, which avoids a crash but can create a fake finite depth.
- `CalibratedStereoMatcher` returns a point and confidence but does not populate covariance or triangulation uncertainty.
- The current loaded calibration acceptance checks verify required arrays and a coarse production flag, but they do not prove field-scale accuracy, board coverage, epipolar residual distributions, or physical plausibility at mound/plate distances.
- The setup stack has sync, overlap, coarse rectification, and quality report pieces, but the runtime still permits legacy scalar fallback for the `legacy` profile.

Detection and tracking:

- Classical detection confidence is mostly circularity. It does not encode motion plausibility, contrast, stereo agreement, historical track consistency, or ball-size consistency.
- Multiple candidates per frame can produce O(n squared) stereo attempts. Matching uses epipolar checks but no global assignment, motion prior, or one-camera dropout model.
- False positives from glove, bat, catcher, dirt, uniforms, fence texture, and shadows are likely under outdoor conditions.
- The pitch state machine is structurally solid, but the orchestrator currently treats each stereo observation as activity. A bad false-positive stereo match can start or extend a pitch.
- The live `TimestampedTrajectoryTracker` fits short polynomial windows without robust outlier rejection. It is acceptable as a preview helper, not as a final path estimator.

Modeling and output:

- The drag fitter is a real nonlinear model, but it consumes observations with no covariance and limited outlier structure.
- Confidence is derived from fitted plate error estimates, but upstream measurement uncertainty is not carried through.
- Ray modes are promising, but they require full camera models and are still comparison/fallback oriented.
- Existing manifests include trajectory summaries but not enough diagnostics to replay why a pitch was accepted, rejected, or considered accurate.

## Salvageable Pieces

- Service boundaries and `EventBus` runtime flow.
- Capture service, camera stats, reconnection scaffolding, and simulator tests.
- Rig profile service, active profile selection, validation, and production-ready flag concept.
- Setup wizard state machine, sync check, overlap check, coarse rectification report, and quality report contracts.
- Recording service and durable artifact layout.
- Trajectory contract types and failure-code pattern.

## Rewrite Pressure

The project does not need a full rewrite. It does need a core-pipeline rewrite: calibration acceptance, geometry contracts, detection evidence, stereo matching, triangulation uncertainty, tracking, path fit, and quality scoring should be rebuilt as one testable pipeline. The current architecture can host that rewrite if the new core is kept behind narrow service interfaces.

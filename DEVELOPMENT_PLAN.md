# Controlled-pilot implementation plan

Updated 2026-09-08. Replaces the speculative queue, buffer, and calibration
rewrite proposals. See [current status](docs/CURRENT_STATUS.md) and
[roadmap](docs/ROADMAP.md) for release gates.

## Product decision

Target a controlled facility pilot with a fixed rig, trained operator, and an
independent calibrated reference. Software regression success is not physical
accuracy evidence. Keep `stereo_3d` primary and ray modes comparison-first.

## Implemented boundaries

- Undistort raw detections once before calibrated epipolar scoring and
  triangulation. Preserve raw pixels; propagate conditional XYZ covariance
  through the same pixel-to-world mapping.
- Check continuous swept-sphere strike geometry between samples, preserve
  feet/inch units, and report unavailable for unsupported gaps or coverage.
- Distinguish host receipt from verified acquisition timing in frames, setup,
  and timestamp artifacts. Legacy timing remains unknown.
- Whiten stereo residuals using covariance or explicitly assumed noise. The
  default drag value is a seed, not a prior penalty. Do not fit an unobservable
  global time shift alongside initial state.
- Reject failed, nonconverged, unidentifiable, and model-mismatched fits.
  Residual fit quality is not physical uncertainty or probability.
- Persist vision and external speed separately, with estimator, timestamp, and
  reference location. First-observed speed is not release speed. Physical
  speed validation requires independent vision at the matching reference plane.
- Use dedicated source/frozen worker entry points, never the GUI as a Python
  interpreter. Kill and reap timed-out numerical children; check reply IDs.
- Report analysis queue age, last queue wait, and handler p95 service latency
  over the most recent 256 items. Report retained pre-roll count, timestamp
  span, image bytes, configured window, and safety cap.

## Assumptions corrected

Production analysis already uses `max_queue=64`; eight is the worker-class
default. Preserve capacity pending measured arrival rate, latency, and drops.
Pitch-state pre-roll already trims by its configured time window with a
100-frame safety cap; do not substitute an arbitrary 30-frame limit.

A five-second proposed stereo deadline was too short for a cold numerical
worker under development load: one measured import-plus-fit took about 14.3 s.
The configurable end-to-end default is 15 s stereo and 10 s per ray fit,
including startup. These are fault-containment limits, not latency SLOs.
Sequential comparisons/fallback can consume multiple deadlines. Queue wait is
additional. Direct offline fitter APIs do not enforce process deadlines; the
event-driven analyzer does.

Analysis already runs off capture's critical path. Broader EventBus changes,
adaptive queues, and calibration UI consolidation remain deferred until
evidence shows they solve an operator or reliability problem.

## Validation order

1. Geometry, independent ODE truth, eligibility, timing/speed provenance,
   durable compatibility, process termination/recovery, and telemetry tests.
2. Full Windows suite; schema, docs, file length, Flake8, typing policy, mypy.
3. Separate pilot bundle and frozen worker smoke tests without cameras.
4. Execute [the pilot checklist](docs/CONTROLLED_PILOT_CHECKLIST.md) on the
   actual rig and clean Windows machine. Record the final commit and artifact
   hashes. These operator-collected gates are not completed by implementation.

## No promotion by synthetic success

Stereo models gravity and constant quadratic drag, not spin-induced transverse
acceleration. Current ray propagation is gravity-only. Short arcs can hide
model mismatch even with small residuals. Conditional velocity uncertainty
excludes timing, calibration, and omitted-force errors. Neither movement/spin
accuracy nor plate-error intervals are established. See
[trajectory model limits](docs/TRAJECTORY_PHYSICS.md).

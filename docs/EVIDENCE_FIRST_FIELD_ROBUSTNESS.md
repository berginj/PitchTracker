# Evidence-First Field Robustness

Implementation and test mapping: [PT-001–PT-015 traceability](PT_001_015_TRACEABILITY.md).

## Purpose

PitchTracker separates raw evidence, bounded corrections, inferred results, and
ground-truth validation. A result that looks plausible is not evidence that it
is accurate. Runtime code must preserve that distinction.

## Quality vocabulary

- `VALIDATED`: demonstrated against an identified ground-truth dataset.
- `ESTIMATED`: supported by available evidence and an error model.
- `DEGRADED`: available with a material, disclosed limitation.
- `UNAVAILABLE`: required evidence is missing.
- `REJECTED`: evidence exceeded a quality gate.

`VALIDATED` requires a `validation_dataset_id`. Missing values are represented
as unavailable, never as zero. Rejected pitches remain in validation and
operational-rate denominators.

## Evidence chain

The evidence chain is:

1. Camera frames and capture timestamps.
2. One `StereoFrameProcessedEvent` per processed pair, including empty pairs.
3. Pair timing/rejection evidence with raw and adjusted timestamps.
4. Raw camera-frame observations available during the active recording interval.
5. Field-frame observations plus a referenced transform.
6. Trajectory inputs, mode comparisons, and fit diagnostics.
7. Pitch measurements, quality status, and correction ledger.

Evidence packages use serialized, atomically published, content-addressed JSONL
generations and SHA-256 integrity records. Rig profiles
also hash calibration and ROI artifacts so an onsite edit cannot silently reuse
the old validation status.

The session decision journal preserves candidate lists, tracklet decisions,
association scores and gates, triangulation outcomes, unmatched single-camera
outcomes, and ramp-up observations. Replay verifies lineage, artifact bindings,
conservation, assignment, triangulation coverage, and exact denominators. This is
candidate-level decision replay, not pixel-to-detector bitwise replay.

## Correction policy

Software corrections are allowed only when the problem is observable and the
estimated correction is inside a configured bound. Each attempt records the
trigger, algorithm version, raw value, corrected value, policy range, reason
codes, and uncertainty before and after.

Examples of bounded corrections:

- Camera side swap or known image orientation.
- A measured camera time offset within the configured range.
- Rejection of an out-of-tolerance stereo pair.
- Robust fit treatment of isolated outliers.

Conditions requiring operator intervention include insufficient overlap,
unobservable timing error, severe blur, bandwidth saturation, unstable mounts,
and a missing field transform. The software must enter degraded/video-only mode
or block measurement mode instead of inventing a correction.

## Error-rate reporting

New runtime loss rates identify numerator and denominator and return unavailable
when no opportunity exists. Capture
qualification reports frame-drop and unmatched-frame rates, achieved FPS,
timestamp jitter, pair-skew percentiles, mode agreement, and control readback.
Runtime diagnostics report detector attempts/failures/queue drops, matched and
unmatched frame outcomes, tracklet decisions, worker drops/failures, complete
association-edge populations, triangulation outcomes, fit convergence,
uncertainty, and alternative-mode disagreement. Durable decision evidence and
live counters must reconcile exactly; inconsistency makes evidence incomplete.

Averages alone are insufficient for timing and geometry. Use p50/p95/p99 where
tail behavior can invalidate a pitch.

## Setup and runtime behavior

There is one canonical stereo setup entry point. A persisted `RigProfile` binds
camera identities, approved mode, manual controls, image transforms,
calibration, field transform, error budget, and artifact hashes. Physical
measurement mode refuses profiles without production geometry and field pose.

The final setup quality step blocks completion on failure, and profile setup is
not complete until persistence succeeds. In coaching, detailed diagnostics are
collapsed by default. The operator still sees the health state and one primary
action; expanded diagnostics expose the underlying evidence without cluttering
normal use.

## Trajectory promotion

Internal residuals can diagnose a fit but cannot establish physical accuracy.
`stereo_3d`, `ray_reprojection`, and `ray_graph` may be compared on identical
evidence. Operational eligibility is separate from accuracy-claim eligibility.
No physical mode may emit `VALIDATED` without an active v2 approval matching the
exact pipeline fingerprint, mode, rig revision, environment, protocol, dataset,
and claim-ready ground-truth report.

Ground-truth reports include sample count, rejected rate, speed bias/MAE/RMSE,
and plate-location error. A release claim must name the dataset, rig profile,
software version, environment, and predeclared acceptance thresholds.

## Metric semantics

`speed_mph` records its source. Operator/radar input is labeled
`manual_override` or `radar_measurement` according to its actual source; an
unclassified external caller is labeled `external_measurement`. A trajectory-derived release-speed estimate is labeled
`vision_fit`. The legacy `run_in` and `rise_in` fields currently contain raw
first-to-last observation displacement. They are not validated induced break,
and durable summaries declare `movement_basis=raw_observation_net_displacement`
and `movement_validated=false`. A future break model must use a separately
validated physical definition before changing those claims.

## Hardware validation boundary

The implementation protocol and v1-to-v2 claim migration are defined in
[Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md). This is
a workflow specification only; it does not mark any physical rig validated.

Simulator and fixture tests verify contracts, failure paths, replay integrity,
queue draining, and deterministic matching. They do not establish the accuracy
of the onsite cameras. The DirectShow adapter writes exposure using its common
`log2(seconds)` convention, converts the raw readback to microseconds, and
blocks setup if exposure/gain/auto-control readback does not agree. A physical
rig must still demonstrate mode/control readback, timing tails, calibration,
field transform, and ground-truth accuracy before any result is `VALIDATED`.

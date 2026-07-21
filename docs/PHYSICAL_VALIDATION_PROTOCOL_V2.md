# Physical Validation Protocol v2

## Status and non-claim boundary

This document defines the software and field procedure required before a
physical global-shutter rig may make a `VALIDATED` accuracy claim. It is a
protocol scaffold, not a validation result. No existing rig, recording,
fixture, or v1 approval is upgraded by this work.

Legacy `ground_truth_report.v1`, `field_fixture.v1`, and
`trajectory_mode_approval.v1` artifacts remain readable for regression and
operational compatibility. They are always ineligible for a v2 accuracy claim.

Operational eligibility and accuracy-claim eligibility are separate:

- **Operationally eligible** means the configured mode may run without
  violating setup, geometry, and legacy mode-safety gates.
- **Accuracy-claim eligible** means an exact v2 protocol, confirmation dataset,
  report, rig revision, measurement-pipeline fingerprint, artifacts, expiry,
  lifecycle state, and two independent trusted attestations all verify.
- A pitch can still be `DEGRADED`, `REJECTED`, or `UNAVAILABLE` even when the
  build has a valid accuracy approval.

## Software workflow

1. Freeze the measurement build, correction policy, rig revision, camera
   controls, calibration, field transform, ROI/detector settings, and supported
   environment.
2. Author `physical_validation_protocol.v2` with the exact trajectory mode,
   claim scope, planned strata,
   denominators, reference-capability gates, exclusion policy, correction
   policy hash, thresholds, and tail policy.
3. Lock and hash the protocol before capturing the first case.
4. Collect a `shadow` dataset for workflow/debugging. Shadow data may be used
   for tuning and can never become claim-ready.
5. Apply changes only through an explicit new rig revision. Tracker-derived
   online refinement creates a shadow proposal; it never mutates the approved
   configuration.
6. Freeze the revised build and collect a disjoint `confirmation` dataset.
7. Import independent reference records and bind every case to a unique
   reference record plus a PitchTracker evidence-package hash.
8. Run the process-backed physical-validation tool. Every independently valid
   opportunity must have one terminal system outcome. Rejections and
   unavailable outputs remain in the denominator.
9. An independent reviewer inspects source artifacts and the generated v2
   report. Collector and reviewer must be distinct trusted signers.
10. Issue an `ACTIVE` v2 approval only if the report is claim-ready. Runtime
    recomputes fingerprints, hashes, signatures, lifecycle state, and expiry.

## Independent reference capabilities

Capability requirements are claim-specific; no product is implied.

### Velocity reference

- Independent sensing path that does not consume PitchTracker detections,
  calibration, or fitted trajectory.
- Device identity and raw export are retained.
- Calibration certificate hash and validity interval are recorded.
- Speed and time uncertainty are declared with their confidence basis.
- Range, sampling behavior, and invalid-reading flags cover the claimed pitch
  envelope.

### Plate-location reference

- Independently measures horizontal and vertical position at the declared plate
  plane.
- Uses a separately surveyed field frame and holdout targets that were not used
  to fit PitchTracker's field transform.
- Records position and correlation-time uncertainty.
- Keeps the raw reference reading and quality state.

### Global-shutter and timing reference

- Independently timed optical pulses or coded fiducials are visible across
  image rows and in both cameras.
- A controlled moving edge or ball-sized target exposes rolling distortion,
  exposure duration, timestamp meaning, and inter-camera skew.
- The test records warm-up state, requested and negotiated modes, exposure and
  gain readback, frame loss, unmatched frames, and timing p50/p95/p99/max.
- Catalog recognition is a setup prerequisite, not proof of physical shutter
  behavior.

Reference uncertainty is never subtracted from observed error to make a gate
pass. The protocol must predeclare a maximum uncertainty materially below the
claim tolerance and block cases whose reference cannot meet it.

## Required case families

- Surveyed static holdout targets near the plate and at near/mid/far pitch-lane
  depths.
- Timing/global-shutter optical cases after warm-up.
- Controlled ball-sized motion across declared speed, depth, location, and
  image-edge strata.
- Thrown pitches covering every claimed operating stratum.
- Repeated runs after teardown/reinstall and across every supported environment
  class.

Sample counts must be predeclared per stratum. If there are too few evaluated
cases for the selected tail statistic, the result is a blocker rather than a
zero, warning-only result, or substituted percentile.

## Corrections and confirmation data

Reports retain raw and corrected measurements separately and bind the exact
correction-policy hash. Corrections may be learned only from development or
shadow data. Changing an algorithm, bound, offset, model parameter, threshold,
or correction after viewing confirmation results converts that confirmation
dataset into development evidence. A new disjoint confirmation dataset is then
required.

The same source artifact cannot be both the independent reference and the
PitchTracker evidence package. Scaffolded pitch outputs are stored under
`observed` and explicitly marked `validation_eligible=false`; they are never
copied into `expected` truth fields.

## Approval lifecycle and revalidation

Lifecycle states are `DRAFT`, `REVIEWED`, `ACTIVE`, `SUSPENDED`, `EXPIRED`,
`REVOKED`, and `SUPERSEDED`. Only `ACTIVE` is claim-eligible. Runtime never
reactivates an approval from improving residuals alone.

Revalidation or suspension is required after:

- camera, lens, mount, serial, firmware, driver, or capture-path changes;
- camera mode or control changes;
- rig movement, impact, calibration, ROI, detector/model, or field-transform
  changes;
- time offset, trajectory, correction-policy, or measurement-code changes;
- environment outside the approved scope;
- drift failure or approval expiry.

A session preflight may maintain an existing approval by checking exact
fingerprints, control readback, capture qualification, timing tails, and an
independent static anchor. It cannot create an approval or automatically undo a
revocation.

## Manual acceptance boundary

Automated tests verify schema rules, deterministic metrics, denominators,
tamper detection, signatures, lifecycle gates, and failure behavior. They
cannot establish actual shutter behavior, physical timestamp semantics,
reference-device calibration accuracy, field survey accuracy, mount stability,
environmental coverage, or evidence chain of custody.

The manual run must archive the protocol, rig snapshot, environment,
independent reference channels, cases, calibration and field artifacts, capture
qualification, v2 report, approval, and artifact inventory. Until that run is
completed and independently reviewed, the correct status is `ESTIMATED` or
diagnostic-only—not `VALIDATED`.

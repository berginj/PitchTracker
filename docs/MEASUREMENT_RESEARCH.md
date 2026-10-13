# Desktop measurement research

The current development priority is a repeatable speed and plate-location
baseline using a local Windows rig and independent reference instruments.
Setup, coaching capture, and Review remain the desktop entrypoints.

Use [Rig Validation Walkthrough](RIG_VALIDATION_WALKTHROUGH.md) to establish the
rig before field collection. Evaluator metrics include observed reference-residual
sample variance and plate X/Y covariance, overall and by stratum. They retain
reference noise and are not physical prediction uncertainty or a new approval.

## Desktop workflow

1. Complete setup and explicitly start a shadow recording with the operator
   present. End recording so the decision journal and manifests can drain.
2. Open Review, then **Tools > Measurement Validation**. Select the session
   directly if videos are missing or the session is too old for normal playback.
3. Choose **Inspect evidence**. Output lists metadata artifact hashes, pitch
   provenance, setup context, journal integrity, frame conservation, unmatched
   outcomes, and missing evidence. No video is uploaded or used as truth.
   Journal artifact bindings are compared with the recorded setup inventory.
4. Import a v2 protocol and dataset, or fill the Protocol and Dataset and
   references tabs. These tabs accept the existing contract's JSON fields.
   Required hashes, reference identities, calibration validity, tolerances,
   and uncertainty must come from the actual study. Blank fields are not proof.
5. In Cases, enter or correct shadow reference measurements. Text columns
   accept plain text. Numeric/boolean columns accept JSON values; position
   columns accept `[x, y]` in feet. Blank optional measurements mean unavailable.
   Preserve every attempt; reference status is `VALID` or `INVALID`, and system
   outcomes are `ACCEPTED`, `REJECTED`, or `UNAVAILABLE`.
6. Choose **Evaluate**. Inspect both the conditional evaluator output and
   workspace blockers. Speed bias, MAE, tail error, plate errors, reference
   validity, evaluated counts, and rejection denominators remain visible.
7. **Save study** saves protocol and dataset separately; **Save report** saves
   the workspace result. Choose new JSON files outside the recording directory.
   Existing files and imported source files cannot be overwritten.

Confirmation metadata and cases are read-only. Import a separate shadow dataset
to tune measurements. A report is diagnostic and never activates an accuracy
approval, even if its conditional evaluator passes. Editing invalidates results.

A blank shadow `protocol_sha256` is filled from the entered protocol during
evaluation. Nonblank hashes are checked unchanged; confirmation hashes are never
filled or rewritten. The resulting report displays the canonical protocol hash.

Use `vision_speed` and its estimator, timestamp and reference Z for comparisons.
Selected display speed may be manual or radar; it must not substitute for
independent vision. Reference speed must describe the same measurement plane.
Unknown planes remain unknown.

Legacy Replay Video is single-view detection inspection without acquisition
timestamps. Decision reconciliation checks recorded decisions; it does not rerun
the detector or prove accuracy.

## Protocol and reference inputs

Use [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md) and
`contracts/physical_validation.py` for field definitions. Required thresholds:

- `max_rejected_rate`
- `max_abs_speed_bias_mph`, `max_speed_mae_mph`, `max_speed_tail_error_mph`
- `max_plate_mae_ft`, `max_plate_tail_error_ft`
- `max_reference_speed_uncertainty_mph`, `max_reference_plate_uncertainty_ft`

Reference channels require device identity, certificate hash, validity dates,
uncertainty and units, confidence basis, timing uncertainty, and independence.
Retain raw reference records and hashes. Never copy system output into truth.

Case evidence hashes absent from the selected metadata inventory are flagged.
This is an artifact-presence check: review must still establish case-to-pitch
association, raw references, exact fingerprints, and chain of custody. Legacy
sessions lacking snapshots or journals remain inspectable with blockers.

## Operator-run baseline checklist

- Inventory independent speed, surveyed location, and optical timing references;
  verify calibration validity and uncertainty.
- Record camera/lens identities, negotiated modes, controls, firmware/driver
  availability, USB path, warm-up, and mount geometry.
- Run optical exposure/skew tests and static holdout targets at near, middle,
  and plate depths. Targets used for fitting are not holdouts.
- Exercise swaps, USB contention, reconnect, pause/stop, and repeated closure;
  preserve recovery outcomes and timing/drop denominators.
- Freeze software, rig revision, controls, calibration, ROI, and setup snapshot.
- Collect **100 shadow attempts across at least three sessions**, one ball type
  and environment, spanning achievable speeds and plate regions. This diagnostic
  starting point does not establish a confirmation sample-size requirement.
- Retain every attempt and reference failure. Rank errors and unavailable results.
- Change one subsystem per experiment. Keep stereo primary and spin unavailable.
- Lock scope, strata, exclusions, counts, tolerances, and uncertainty limits
  before disjoint confirmation; obtain independent review afterward.

Physical qualification, collection, approval, signing, and clean-machine
qualification remain operator tasks. See [the acceptance ledger](review/RESEARCH_ACCEPTANCE_LEDGER.md).
